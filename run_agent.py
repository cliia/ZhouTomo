#!/usr/bin/env python3
"""
显微镜代理启动入口 - run_agent.py

本模块是ZhouTomo显微镜代理系统的主要启动入口，负责：
1. 命令行参数解析（--mode, --server_url等）
2. 配置管理和验证
3. 显微镜连接初始化
4. FastAPI服务启动
5. WebSocket推流准备

参考文档: https://temscript.readthedocs.io/en/latest/instrument.html

使用方法:
    python run_agent.py --mode local
    python run_agent.py --mode remote --server_url http://localhost:8080
    python run_agent.py --mode null
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

# 导入项目模块
from domain import MicroscopeState, MicroscopeParams
from wiring import (
    MicroscopeWiring, create_microscope_wiring,
    get_available_modes, validate_mode
)
from server_fastapi import create_app, ServerState

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('agent.log', encoding='utf-8')
    ],
    force=True
)
logger = logging.getLogger(__name__)


class AgentConfig:
    """代理配置管理"""
    
    def __init__(self):
        self.mode: str = "local"
        self.server_url: Optional[str] = None
        self.host: str = "0.0.0.0"
        self.port: int = 9000
        self.reload: bool = False
        self.log_level: str = "INFO"
        self.config_file: Optional[str] = None
        
    def load_from_env(self):
        """从环境变量加载配置"""
        self.mode = os.getenv("AGENT_MODE", "local")
        self.server_url = os.getenv("AGENT_SERVER_URL")
        self.host = os.getenv("AGENT_HOST", "0.0.0.0")
        self.port = int(os.getenv("AGENT_PORT", "9000"))
        self.reload = os.getenv("AGENT_RELOAD", "false").lower() == "true"
        self.log_level = os.getenv("AGENT_LOG_LEVEL", "INFO")
        
    def validate(self) -> bool:
        """验证配置有效性"""
        if not validate_mode(self.mode):
            logger.error(f"Invalid mode: {self.mode}")
            return False
            
        if self.mode == "remote" and not self.server_url:
            logger.error("Remote mode requires server_url")
            return False
            
        if self.port < 1 or self.port > 65535:
            logger.error(f"Invalid port: {self.port}")
            return False
            
        return True
        
    def __str__(self) -> str:
        return (f"AgentConfig(mode={self.mode}, "
                f"server_url={self.server_url}, "
                f"host={self.host}, port={self.port})")


class AgentManager:
    """代理管理器"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.wiring: Optional[MicroscopeWiring] = None
        self.server_state: Optional[ServerState] = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self) -> bool:
        """初始化代理"""
        try:
            logger.info("Initializing agent...")
            
            # 创建显微镜装配
            self.wiring = create_microscope_wiring(
                mode=self.config.mode,
                server_url=self.config.server_url
            )
            
            # 连接显微镜
            if not self._connect_microscope():
                logger.error("Failed to connect to microscope")
                return False
                
            # 创建服务器状态
            self.server_state = ServerState()
            
            logger.info("Agent initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            return False
            
    def _connect_microscope(self) -> bool:
        """连接显微镜"""
        try:
            if not self.wiring:
                return False
                
            # 尝试连接
            if not self.wiring.connect():
                logger.error("Failed to connect to microscope")
                return False
                
            # 验证连接状态
            if not self.wiring.is_connected():
                logger.error("Microscope not connected")
                return False
                
            # 获取显微镜信息
            info = self.wiring.get_info()
            logger.info(f"Connected to microscope: {info.get('name', 'Unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to microscope: {e}")
            return False
            
    async def shutdown(self):
        """关闭代理"""
        try:
            logger.info("Shutting down agent...")
            
            # 设置关闭事件
            self.shutdown_event.set()
            
            # 断开显微镜连接
            if self.wiring:
                self.wiring.disconnect()
                
            logger.info("Agent shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def parse_arguments() -> AgentConfig:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ZhouTomo显微镜代理启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  local    - 本地temscript模式（默认）
  remote   - 远程temscript服务器模式
  null     - 模拟器模式（用于测试）

示例:
  python run_agent.py --mode local
  python run_agent.py --mode remote --server_url http://localhost:8080
  python run_agent.py --mode null --port 9000
        """
    )
    
    # 基本参数
    parser.add_argument(
        "--mode",
        choices=["local", "remote", "null"],
        default="local",
        help="运行模式 (默认: local)"
    )
    
    parser.add_argument(
        "--server_url",
        help="远程模式时的temscript服务器地址"
    )
    
    # 服务器参数
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="服务器监听地址 (默认: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="服务器监听端口 (默认: 8000)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载（开发模式）"
    )
    
    # 配置参数
    parser.add_argument(
        "--config",
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )
    
    # 信息参数
    parser.add_argument(
        "--version",
        action="version",
        version="ZhouTomo Agent v1.0.0"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="显示系统信息并退出"
    )
    
    args = parser.parse_args()
    
    # 创建配置对象
    config = AgentConfig()
    
    # 从环境变量加载配置（作为默认值）
    config.load_from_env()
    
    # 命令行参数覆盖环境变量
    if args.mode:
        config.mode = args.mode
    if args.server_url:
        config.server_url = args.server_url
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.reload:
        config.reload = args.reload
    if args.log_level:
        config.log_level = args.log_level
    if args.config:
        config.config_file = args.config
    
    return config


def setup_logging(config: AgentConfig):
    """设置日志配置"""
    # 设置根日志级别
    log_level = getattr(logging, config.log_level.upper())
    logging.getLogger().setLevel(log_level)
    
    # 设置特定模块的日志级别
    if config.mode == "null":
        logging.getLogger("wiring").setLevel(logging.DEBUG)
    
    logger.info(f"Log level set to: {config.log_level}")


def show_system_info():
    """显示系统信息"""
    print("ZhouTomo 显微镜代理系统")
    print("=" * 40)
    
    # 显示可用模式
    available_modes = get_available_modes()
    print("\n可用运行模式:")
    for mode, available in available_modes.items():
        status = "✓" if available else "✗"
        print(f"  {status} {mode}")
    
    # 显示Python版本
    print(f"\nPython版本: {sys.version}")
    
    # 显示工作目录
    print(f"工作目录: {os.getcwd()}")
    
    # 显示环境信息
    print(f"环境变量:")
    env_vars = ["AGENT_MODE", "AGENT_SERVER_URL", "AGENT_HOST", "AGENT_PORT"]
    for var in env_vars:
        value = os.getenv(var, "未设置")
        print(f"  {var}: {value}")


def setup_signal_handlers(agent_manager: AgentManager):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(agent_manager.shutdown())
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Windows支持
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)


async def main():
    """主函数"""
    try:
        # 解析命令行参数
        config = parse_arguments()
        
        # 显示系统信息
        if hasattr(config, 'info') and config.info:
            show_system_info()
            return
        
        # 设置日志
        setup_logging(config)
        
        # 验证配置
        if not config.validate():
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        logger.info(f"Starting agent with config: {config}")
        
        # 创建代理管理器
        agent_manager = AgentManager(config)
        
        # 初始化代理
        if not await agent_manager.initialize():
            logger.error("Failed to initialize agent")
            sys.exit(1)
        
        # 设置信号处理器
        setup_signal_handlers(agent_manager)
        
        # 创建FastAPI应用
        app = create_app()
        
        # 将显微镜装配传递给服务器状态
        from server_fastapi import set_microscope_wiring
        set_microscope_wiring(agent_manager.wiring)
        
        # 启动服务器
        import uvicorn
        config_dict = uvicorn.Config(
            app=app,
            host=config.host,
            port=config.port,
            reload=config.reload,
            log_level=config.log_level.lower(),
            access_log=True
        )
        
        server = uvicorn.Server(config_dict)
        
        logger.info(f"Starting server on {config.host}:{config.port}")
        logger.info(f"Mode: {config.mode}")
        if config.server_url:
            logger.info(f"Remote server: {config.server_url}")
        
        # 启动服务器
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        # 确保代理正确关闭
        if 'agent_manager' in locals():
            await agent_manager.shutdown()


if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 运行主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序异常退出: {e}")
        sys.exit(1)
