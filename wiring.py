"""
装配层 - 显微镜实现选择和组件装配

本模块负责：
1. 决定使用哪种显微镜实现（local/remote/null）
2. 把所有组件的Port实例化，组合成MicroscopeAggregate
3. 提供工厂模式创建不同类型的显微镜实例

参考文档: https://temscript.readthedocs.io/en/latest/instrument.html
"""

import logging
import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

# 导入领域模型和接口
from domain import (
    MicroscopeInterface, MicroscopeAggregate,
    MicroscopeState, MicroscopeParams
)

# 导入temscript实现
from ports_temscript import (
    TemscriptMicroscope, create_temscript_microscope,
    validate_temscript_connection
)

# 配置日志
logger = logging.getLogger(__name__)


class MicroscopeFactoryError(Exception):
    """显微镜工厂错误"""
    pass


class MicroscopeConnectionError(Exception):
    """显微镜连接错误"""
    pass


class MicroscopeFactory(ABC):
    """显微镜工厂抽象基类"""
    
    @abstractmethod
    def create_microscope(self) -> MicroscopeInterface:
        """创建显微镜实例"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """获取显微镜信息"""
        pass


class LocalTemscriptFactory(MicroscopeFactory):
    """本地temscript显微镜工厂"""
    
    def __init__(self):
        self._instrument = None
        self._microscope = None
    
    def is_available(self) -> bool:
        """检查本地temscript是否可用"""
        try:
            # 尝试导入temscript
            import temscript
            return True
        except ImportError:
            logger.warning("temscript module not available")
            return False
    
    def create_microscope(self) -> MicroscopeInterface:
        """创建本地temscript显微镜实例"""
        if not self.is_available():
            logger.error("temscript not available")
            raise MicroscopeFactoryError("temscript not available")
        
        try:
            # 导入temscript并获取仪器实例
            import temscript
            self._instrument = temscript.GetInstrument()
            
            # 验证连接
            if not validate_temscript_connection(self._instrument):
                logger.error("temscript connection validation failed")
                raise MicroscopeConnectionError("Failed to connect to local microscope")
            
            # 创建显微镜实例
            self._microscope = create_temscript_microscope(self._instrument)
            logger.info("Local temscript microscope created successfully")
            return self._microscope
            
        except Exception as e:
            logger.error(f"Failed to create local microscope: {e}")
            raise MicroscopeFactoryError(f"Failed to create local microscope: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """获取本地显微镜信息"""
        if not self._instrument:
            return {"type": "local", "status": "not_connected"}
        
        try:
            config = self._instrument.Configuration
            return {
                "type": "local",
                "status": "connected",
                "product_family": str(config.ProductFamily),
                "connection_type": "direct_temscript"
            }
        except Exception as e:
            logger.warning(f"Failed to get local microscope info: {e}")
            return {"type": "local", "status": "connected", "info_error": str(e)}


class RemoteTemscriptFactory(MicroscopeFactory):
    """远程temscript服务器显微镜工厂"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._microscope = None
    
    def is_available(self) -> bool:
        """检查远程服务器是否可用"""
        try:
            # 这里应该实现远程连接检查
            # 暂时返回True，实际实现中需要ping服务器
            return True
        except Exception:
            return False
    
    def create_microscope(self) -> MicroscopeInterface:
        """创建远程显微镜实例"""
        if not self.is_available():
            raise MicroscopeFactoryError(f"Remote server {self.server_url} not available")
        
        try:
            # 这里应该实现远程显微镜连接
            # 暂时抛出异常，实际实现中需要实现远程连接逻辑
            raise NotImplementedError("Remote microscope connection not yet implemented")
            
        except Exception as e:
            logger.error(f"Failed to create remote microscope: {e}")
            raise MicroscopeFactoryError(f"Failed to create remote microscope: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """获取远程显微镜信息"""
        return {
            "type": "remote",
            "status": "not_implemented",
            "server_url": self.server_url,
            "connection_type": "remote_temscript_server"
        }


class NullMicroscopeFactory(MicroscopeFactory):
    """空显微镜工厂（模拟器）"""
    
    def __init__(self):
        self._microscope = None
    
    def is_available(self) -> bool:
        """空显微镜总是可用"""
        return True
    
    def create_microscope(self) -> MicroscopeInterface:
        """创建空显微镜实例"""
        try:
            from ports_temscript import NullMicroscope
            self._microscope = NullMicroscope()
            logger.info("Null microscope simulator created successfully")
            return self._microscope
            
        except Exception as e:
            logger.error(f"Failed to create null microscope: {e}")
            raise MicroscopeFactoryError(f"Failed to create null microscope: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """获取空显微镜信息"""
        return {
            "type": "null",
            "status": "available",
            "connection_type": "simulator",
            "description": "Null microscope simulator for testing"
        }


class MicroscopeWiring:
    """显微镜装配类"""
    
    def __init__(self, mode: str = "local", server_url: str = None):
        """
        初始化显微镜装配
        
        Args:
            mode: 显微镜模式 ("local", "remote", "null")
            server_url: 远程模式时的服务器地址
        """
        self.mode = mode
        self.server_url = server_url
        self.factory = self._create_factory()
        self.microscope = None
        self.aggregate = None
    
    def _create_factory(self) -> MicroscopeFactory:
        """根据模式创建相应的工厂"""
        try:
            if self.mode == "local":
                factory = LocalTemscriptFactory()
                logger.info("LocalTemscriptFactory created")
                return factory
            elif self.mode == "remote":
                if not self.server_url:
                    logger.error("Server URL required for remote mode")
                    raise MicroscopeFactoryError("Server URL required for remote mode")
                factory = RemoteTemscriptFactory(self.server_url)
                logger.info("RemoteTemscriptFactory created")
                return factory
            elif self.mode == "null":
                factory = NullMicroscopeFactory()
                logger.info("NullMicroscopeFactory created")
                return factory
            else:
                logger.error(f"Unknown mode: {self.mode}")
                raise MicroscopeFactoryError(f"Unknown mode: {self.mode}")
        except Exception as e:
            logger.error(f"Failed to create factory: {e}")
            raise
    
    def connect(self) -> bool:
        """连接到显微镜"""
        try:
            if not self.factory.is_available():
                logger.error(f"Microscope factory {self.mode} is not available")
                return False
            
            self.microscope = self.factory.create_microscope()
            self.aggregate = MicroscopeAggregate(self.microscope)
            
            logger.info(f"Successfully connected to {self.mode} microscope")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to microscope: {e}")
            return False
    
    def disconnect(self):
        """断开显微镜连接"""
        if self.microscope and hasattr(self.microscope, 'instrument'):
            try:
                # 清理资源
                self.microscope = None
                self.aggregate = None
                logger.info("Microscope disconnected")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        if self.microscope is None or self.aggregate is None:
            return False
        
        try:
            return self.microscope.is_connected()
        except Exception as e:
            logger.error(f"Error checking connection: {e}")
            return False
    
    def get_microscope(self) -> Optional[MicroscopeInterface]:
        """获取显微镜实例"""
        return self.microscope
    
    def get_aggregate(self) -> Optional[MicroscopeAggregate]:
        """获取显微镜聚合根"""
        return self.aggregate
    
    def get_info(self) -> Dict[str, Any]:
        """获取显微镜信息"""
        info = self.factory.get_info()
        info.update({
            "mode": self.mode,
            "connected": self.is_connected()
        })
        return info
    
    def get_snapshot(self) -> Optional[MicroscopeState]:
        """获取显微镜状态快照"""
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return None
        
        try:
            return self.aggregate.get_snapshot()
        except Exception as e:
            logger.error(f"Failed to get snapshot: {e}")
            return None
    
    def set_component_params(self, component: str, params: Any) -> bool:
        """设置组件参数"""
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return False
        
        try:
            if not self.aggregate:
                logger.error("Aggregate not available")
                return False
            
            return self.aggregate.set_component_params(component, params)
        except Exception as e:
            logger.error(f"Error setting component params: {e}")
            return False
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行组件命令"""
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return False
        
        try:
            return self.aggregate.execute_command(component, command, **kwargs)
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return False


def create_microscope_wiring(mode: str = "local", server_url: str = None) -> MicroscopeWiring:
    """
    创建显微镜装配实例
    
    Args:
        mode: 显微镜模式 ("local", "remote", "null")
        server_url: 远程模式时的服务器地址
        
    Returns:
        MicroscopeWiring实例
    """
    return MicroscopeWiring(mode, server_url)


def get_available_modes() -> Dict[str, bool]:
    """
    获取可用的显微镜模式
    
    Returns:
        可用模式字典
    """
    modes = {}
    
    # 检查本地模式
    local_factory = LocalTemscriptFactory()
    modes["local"] = local_factory.is_available()
    
    # 空模式总是可用
    modes["null"] = True
    
    # 远程模式需要网络检查，暂时设为False
    modes["remote"] = False
    
    return modes


def validate_mode(mode: str) -> bool:
    """
    验证显微镜模式是否有效
    
    Args:
        mode: 要验证的模式
        
    Returns:
        模式是否有效
    """
    available_modes = get_available_modes()
    return mode in available_modes and available_modes[mode]


# 环境变量配置
def get_default_mode() -> str:
    """从环境变量获取默认模式"""
    return os.getenv("ZHOUTOMO_MODE", "local")


def get_default_server_url() -> str:
    """从环境变量获取默认服务器地址"""
    return os.getenv("ZHOUTOMO_SERVER_URL", "")


# 便捷函数
def create_default_wiring() -> MicroscopeWiring:
    """创建默认的显微镜装配"""
    mode = get_default_mode()
    server_url = get_default_server_url() if mode == "remote" else None
    
    return create_microscope_wiring(mode, server_url)


def create_local_wiring() -> MicroscopeWiring:
    """创建本地显微镜装配"""
    return create_microscope_wiring("local")


def create_null_wiring() -> MicroscopeWiring:
    """创建空显微镜装配"""
    return create_microscope_wiring("null")


def create_remote_wiring(server_url: str) -> MicroscopeWiring:
    """创建远程显微镜装配"""
    return create_microscope_wiring("remote", server_url)
