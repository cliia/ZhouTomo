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
from typing import Optional

from wiring import (
    MicroscopeWiring,
    create_microscope_wiring,
    get_available_modes,
    validate_mode,
)
from server_fastapi import create_app, ServerState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
    force=True,
)
logger = logging.getLogger(__name__)


class AgentConfig:
    """代理配置管理。优先级：CLI > 环境变量 > 代码默认值。"""

    def __init__(self):
        self.mode: str = "local"
        self.server_url: Optional[str] = None
        self.host: str = "0.0.0.0"
        self.port: int = 9000
        self.reload: bool = False
        self.log_level: str = "INFO"
        self.config_file: Optional[str] = None
        self.info: bool = False

    def load_from_env(self):
        """从环境变量加载配置。"""
        self.mode = os.getenv("AGENT_MODE", self.mode)
        self.server_url = os.getenv("AGENT_SERVER_URL", self.server_url)
        self.host = os.getenv("AGENT_HOST", self.host)
        self.port = int(os.getenv("AGENT_PORT", str(self.port)))
        self.reload = os.getenv("AGENT_RELOAD", str(self.reload)).lower() == "true"
        self.log_level = os.getenv("AGENT_LOG_LEVEL", self.log_level)

    def validate(self) -> bool:
        """验证配置有效性。"""
        if not validate_mode(self.mode):
            logger.error("Invalid mode: %s", self.mode)
            return False

        if self.mode == "remote" and not self.server_url:
            logger.error("Remote mode requires server_url")
            return False

        if self.port < 1 or self.port > 65535:
            logger.error("Invalid port: %s", self.port)
            return False

        return True

    def __str__(self) -> str:
        return (
            f"AgentConfig(mode={self.mode}, "
            f"server_url={self.server_url}, "
            f"host={self.host}, port={self.port})"
        )


class AgentManager:
    """代理管理器。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.wiring: Optional[MicroscopeWiring] = None
        self.server_state: Optional[ServerState] = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self) -> bool:
        try:
            logger.info("Initializing agent...")
            self.wiring = create_microscope_wiring(
                mode=self.config.mode,
                server_url=self.config.server_url,
            )

            if not self._connect_microscope():
                logger.error("Failed to connect to microscope")
                return False

            self.server_state = ServerState()
            logger.info("Agent initialized successfully")
            return True
        except Exception as exc:
            logger.error("Failed to initialize agent: %s", exc)
            return False

    def _connect_microscope(self) -> bool:
        try:
            if not self.wiring:
                return False

            if not self.wiring.connect():
                logger.error("Failed to connect to microscope")
                return False

            if not self.wiring.is_connected():
                logger.error("Microscope not connected")
                return False

            info = self.wiring.get_info()
            logger.info("Connected to microscope: %s", info.get("name", "Unknown"))
            return True
        except Exception as exc:
            logger.error("Error connecting to microscope: %s", exc)
            return False

    async def shutdown(self):
        try:
            logger.info("Shutting down agent...")
            self.shutdown_event.set()
            if self.wiring:
                self.wiring.disconnect()
            logger.info("Agent shutdown completed")
        except Exception as exc:
            logger.error("Error during shutdown: %s", exc)


def parse_arguments() -> AgentConfig:
    """解析命令行参数。

    argparse 中可由环境变量提供的参数使用 ``None`` 作为默认值，避免
    argparse 自己的默认值覆盖已经由 ``AgentConfig.load_from_env`` 读取的配置。
    """
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
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["local", "remote", "null"],
        default=None,
        help="运行模式（默认: AGENT_MODE 或 local）",
    )
    parser.add_argument(
        "--server_url",
        default=None,
        help="远程模式时的temscript服务器地址",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="服务器监听地址（默认: AGENT_HOST 或 0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="服务器监听端口（默认: AGENT_PORT 或 9000）",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="启用/禁用自动重载（默认: AGENT_RELOAD 或 false）",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="日志级别（默认: AGENT_LOG_LEVEL 或 INFO）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ZhouTomo Agent v1.0.0",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="显示系统信息并退出",
    )

    args = parser.parse_args()

    config = AgentConfig()
    config.load_from_env()

    if args.mode is not None:
        config.mode = args.mode
    if args.server_url is not None:
        config.server_url = args.server_url
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.reload is not None:
        config.reload = args.reload
    if args.log_level is not None:
        config.log_level = args.log_level
    if args.config is not None:
        config.config_file = args.config
    config.info = args.info

    return config


def setup_logging(config: AgentConfig):
    log_level = getattr(logging, config.log_level.upper())
    logging.getLogger().setLevel(log_level)

    if config.mode == "null":
        logging.getLogger("wiring").setLevel(logging.DEBUG)

    logger.info("Log level set to: %s", config.log_level)


def show_system_info():
    print("ZhouTomo 显微镜代理系统")
    print("=" * 40)

    available_modes = get_available_modes()
    print("\n可用运行模式:")
    for mode, available in available_modes.items():
        status = "✓" if available else "✗"
        print(f"  {status} {mode}")

    print(f"\nPython版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print("环境变量:")
    env_vars = ["AGENT_MODE", "AGENT_SERVER_URL", "AGENT_HOST", "AGENT_PORT"]
    for var in env_vars:
        value = os.getenv(var, "未设置")
        print(f"  {var}: {value}")


def setup_signal_handlers(agent_manager: AgentManager):
    def signal_handler(signum, frame):
        logger.info("Received signal %s, initiating shutdown...", signum)
        asyncio.create_task(agent_manager.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)


async def main():
    try:
        config = parse_arguments()

        if config.info:
            show_system_info()
            return

        setup_logging(config)

        if not config.validate():
            logger.error("Configuration validation failed")
            sys.exit(1)

        logger.info("Starting agent with config: %s", config)

        agent_manager = AgentManager(config)
        if not await agent_manager.initialize():
            logger.error("Failed to initialize agent")
            sys.exit(1)

        setup_signal_handlers(agent_manager)
        app = create_app()

        from server_fastapi import set_microscope_wiring

        set_microscope_wiring(agent_manager.wiring)

        import uvicorn

        config_dict = uvicorn.Config(
            app=app,
            host=config.host,
            port=config.port,
            reload=config.reload,
            log_level=config.log_level.lower(),
            access_log=True,
            http="h11",
        )
        server = uvicorn.Server(config_dict)

        logger.info("Starting server on %s:%s", config.host, config.port)
        logger.info("Mode: %s", config.mode)
        if config.server_url:
            logger.info("Remote server: %s", config.server_url)

        await server.serve()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        sys.exit(1)
    finally:
        if "agent_manager" in locals():
            await agent_manager.shutdown()


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as exc:
        print(f"程序异常退出: {exc}")
        sys.exit(1)
