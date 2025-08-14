"""
显微镜领域模型定义

本模块定义了显微镜系统的核心领域模型，包括各个功能组件的状态和参数。
所有模型都使用dataclass来确保类型安全和代码可读性。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import json
import logging
import traceback


logger = logging.getLogger(__name__)


class MicroscopeMode(Enum):
    """显微镜工作模式"""
    IMAGING = "imaging"           # 成像模式
    DIFFRACTION = "diffraction"   # 衍射模式
    STEM = "stem"                 # 扫描透射模式
    EELS = "eels"                 # 电子能量损失谱模式


class VacuumStatus(Enum):
    """真空状态"""
    VACUUM = "vacuum"             # 真空状态
    AIR = "air"                   # 大气状态
    VENTING = "venting"           # 正在放气
    PUMPING = "pumping"           # 正在抽气


class CameraStatus(Enum):
    """相机状态"""
    IDLE = "idle"                 # 空闲
    ACQUIRING = "acquiring"       # 正在采集
    PROCESSING = "processing"     # 正在处理
    ERROR = "error"               # 错误状态


@dataclass
class GunState:
    """电子枪状态"""
    status: None = None


@dataclass
class GunParams:
    """电子枪可设置参数"""
    status: None = None


@dataclass
class IlluminationState:
    """照明系统状态"""
    stem_magnification: float = 5000 # STEM 放大倍数
    stem_rotation: float = -5.7      # STEM 旋转角度


@dataclass
class IlluminationParams:
    """照明系统可设置参数"""
    stem_magnification: float = 5000 # STEM 放大倍数
    stem_rotation: float = -5.7      # STEM 旋转角度


@dataclass
class ProjectionState:
    """投影系统状态"""
    defocus: float = 0.0          # 离焦量 (m)


@dataclass
class ProjectionParams:
    """投影系统可设置参数"""
    defocus: float = 0.0          # 离焦量 (m)
    magnification: float = 1000.0 # 放大倍数
    objective_aperture: int = 1   # 物镜光阑索引
    intermediate_aperture: int = 1 # 中间镜光阑索引
    selected_aperture: int = 1    # 选择光阑索引
    min_magnification: float = 100.0  # 最小放大倍数
    max_magnification: float = 1000000.0  # 最大放大倍数


@dataclass
class StagePosition:
    """载物台位置"""
    x: float = 0.0               # X轴位置 (m)
    y: float = 0.0               # Y轴位置 (m)
    z: float = 0.0               # Z轴位置 (m)
    a: float = 0.0            # 倾斜角 (rad)
    b: float = 0.0            # 旋转角 (rad)


@dataclass
class StageState:
    """载物台状态"""
    position: StagePosition = field(default_factory=StagePosition)
    is_ready: bool = False       # 是否准备好
    limits: Dict[str, tuple] = field(default_factory=dict)  # 各轴限制 (min, max, unit)


@dataclass
class StageParams:
    """载物台可设置参数"""
    position: StagePosition = field(default_factory=StagePosition)


@dataclass
class VacuumState:
    """真空系统状态"""
    status: None = None


@dataclass
class VacuumParams:
    """真空系统可设置参数"""
    status: None = None


@dataclass
class ModeState:
    """工作模式状态"""
    status: None = None


@dataclass
class ModeParams:
    status: None = None


@dataclass
class BlankerState:
    """束流遮挡器状态"""
    status: None = None


@dataclass
class BlankerParams:
    """束流遮挡器可设置参数"""
    status: None = None


@dataclass
class CameraState:
    """相机状态"""
    status: None = None


@dataclass
class CameraParams:
    """相机可设置参数"""
    status: None = None


@dataclass
class AcquisitionState:
    """采集状态"""
    acq_image_size: int = 1  # IntEnum: 0 (Full), 1 (Half), 2 (Quarter)
    dwell_time: float = 2    # 帧间隔 (us)
    brightness: float = 45.0  # 亮度 (%)
    contrast: float = 45.0  # 对比度 (%)
    binnings: int = 4         # 合并度: 1 (2048x2048), 2 (1024x1024), 4 (512x512)
    frames: int = 1  # 帧数

@dataclass
class AcquisitionParams:
    """采集可设置参数"""
    acq_image_size: int = 1  # IntEnum: 0 (Full), 1 (Half), 2 (Quarter)
    dwell_time: float = 2    # 帧间隔 (us)
    brightness: float = 45.0  # 亮度 (%)
    contrast: float = 45.0  # 对比度 (%)
    binnings: int = 4         # 合并度: 1 (2048x2048), 2 (1024x1024), 4 (512x512)
    frames: int = 1  # 帧数


@dataclass
class AutoNormalizeState:
    """自动归一化状态"""
    is_enabled: bool = False      # 是否启用
    is_running: bool = False      # 是否正在运行
    last_normalized: float = 0.0  # 上次归一化时间
    normalization_factor: float = 1.0  # 归一化因子


@dataclass
class AutoNormalizeParams:
    """自动归一化可设置参数"""
    is_enabled: bool = False      # 是否启用
    interval: float = 60.0        # 归一化间隔 (秒)
    threshold: float = 0.1        # 归一化阈值


@dataclass
class MicroscopeState:
    """显微镜整体状态"""
    gun: GunState = field(default_factory=GunState)
    illumination: IlluminationState = field(default_factory=IlluminationState)
    projection: ProjectionState = field(default_factory=ProjectionState)
    stage: StageState = field(default_factory=StageState)
    vacuum: VacuumState = field(default_factory=VacuumState)
    mode: ModeState = field(default_factory=ModeState)
    blanker: BlankerState = field(default_factory=BlankerState)
    camera: CameraState = field(default_factory=CameraState)
    acquisition: AcquisitionState = field(default_factory=AcquisitionState)
    auto_normalize: AutoNormalizeState = field(default_factory=AutoNormalizeState)
    timestamp: float = 0.0        # 状态时间戳
    system_status: str = "unknown" # 系统状态


@dataclass
class MicroscopeParams:
    """显微镜整体可设置参数"""
    gun: GunParams = field(default_factory=GunParams)
    illumination: IlluminationParams = field(default_factory=IlluminationParams)
    projection: ProjectionParams = field(default_factory=ProjectionParams)
    stage: StageParams = field(default_factory=StageParams)
    vacuum: VacuumParams = field(default_factory=VacuumParams)
    mode: ModeParams = field(default_factory=ModeParams)
    blanker: BlankerParams = field(default_factory=BlankerParams)
    camera: CameraParams = field(default_factory=CameraParams)
    acquisition: AcquisitionParams = field(default_factory=AcquisitionParams)
    auto_normalize: AutoNormalizeParams = field(default_factory=AutoNormalizeParams)


class MicroscopeInterface:
    """显微镜接口抽象类"""
    
    def get_state(self) -> MicroscopeState:
        """获取显微镜当前状态"""
        raise NotImplementedError
    
    def set_params(self, params: MicroscopeParams) -> bool:
        """设置显微镜参数"""
        raise NotImplementedError
    
    def get_component_state(self, component: str) -> Any:
        """获取指定组件的状态"""
        raise NotImplementedError
    
    def set_component_params(self, component: str, params: Any) -> bool:
        """设置指定组件的参数"""
        raise NotImplementedError
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行指定组件的命令"""
        raise NotImplementedError
    
    def start_acquisition(self) -> bool:
        """开始图像采集"""
        raise NotImplementedError
    
    def stop_acquisition(self) -> bool:
        """停止图像采集"""
        raise NotImplementedError
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        raise NotImplementedError


class MicroscopeAggregate(object):
    """显微镜聚合根，管理所有组件"""
    
    def __init__(self, microscope: MicroscopeInterface):
        self.microscope = microscope
        
        # 检查microscope是否有_components属性（如NullMicroscope）
        if hasattr(microscope, '_components'):
            # 对于NullMicroscope等使用_components字典的实现
            self._components = microscope._components
        else:
            # 对于直接有gun、illumination等属性的实现
            self._components = {
                'gun': microscope.gun if hasattr(microscope, 'gun') else None,
                'illumination': microscope.illumination if hasattr(microscope, 'illumination') else None,
                'projection': microscope.projection if hasattr(microscope, 'projection') else None,
                'stage': microscope.stage if hasattr(microscope, 'stage') else None,
                'vacuum': microscope.vacuum if hasattr(microscope, 'vacuum') else None,
                'mode': microscope.mode if hasattr(microscope, 'mode') else None,
                'blanker': microscope.blanker if hasattr(microscope, 'blanker') else None,
                'camera': microscope.camera if hasattr(microscope, 'camera') else None,
                'acquisition': microscope.acquisition if hasattr(microscope, 'acquisition') else None,
                'auto_normalize': microscope.auto_normalize if hasattr(microscope, 'auto_normalize') else None,
            }
    
    def get_snapshot(self) -> MicroscopeState:
        """获取显微镜状态快照"""
        return self.microscope.get_state()
    
    def get_component_state(self, component: str) -> Any:
        """获取指定组件状态"""
        if component not in self._components:
            raise ValueError(f"Unknown component: {component}")
        return self.microscope.get_component_state(component)
    
    def set_component_params(self, component: str, params: Any) -> bool:
        """设置指定组件参数"""
        if component not in self._components:
            logger.error(f"Unknown component: {component}")
            raise ValueError(f"Unknown component: {component}")
        
        try:
            return self.microscope.set_component_params(component, params)
        except Exception as e:
            logger.error(f"Error setting component params: {e}")
            raise
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行指定组件命令"""
        if component not in self._components:
            raise ValueError(f"Unknown component: {component}")
        # 确保kwargs作为关键字参数传递
        return self.microscope.execute_command(component, command, **kwargs)
    
    def list_components(self) -> List[str]:
        """列出所有可用组件"""
        return list(self._components.keys())
    
    def has_component(self, component: str) -> bool:
        """检查是否有指定组件"""
        return component in self._components
    
    def get_available_components(self) -> List[str]:
        """获取可用组件列表"""
        return [comp for comp, impl in self._components.items() if impl is not None]


# 工具函数
def state_to_dict(state: MicroscopeState) -> Dict[str, Any]:
    """将状态对象转换为字典"""
    def convert_value(value):
        # 检查是否是dataclass对象
        if hasattr(value, '__dataclass_fields__'):
            result = {}
            for k, v in value.__dict__.items():
                result[k] = convert_value(v)
            return result
        # 检查是否是Enum
        elif isinstance(value, Enum):
            return value.value
        # 检查是否是列表或元组
        elif isinstance(value, (list, tuple)):
            return [convert_value(v) for v in value]
        # 检查是否是其他有__dict__的对象
        elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, bytes)):
            result = {}
            for k, v in value.__dict__.items():
                result[k] = convert_value(v)
            return result
        # 基本类型直接返回
        else:
            return value
    
    # 直接转换整个state对象，而不是它的__dict__
    return convert_value(state)


def params_to_dict(params: MicroscopeParams) -> Dict[str, Any]:
    """将参数对象转换为字典"""
    def convert_value(value):
        # 检查是否是dataclass对象
        if hasattr(value, '__dataclass_fields__'):
            result = {}
            for k, v in value.__dict__.items():
                result[k] = convert_value(v)
            return result
        # 检查是否是Enum
        elif isinstance(value, Enum):
            return value.value
        # 检查是否是列表或元组
        elif isinstance(value, (list, tuple)):
            return [convert_value(v) for v in value]
        # 检查是否是其他有__dict__的对象
        elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, bytes)):
            result = {}
            for k, v in value.__dict__.items():
                result[k] = convert_value(v)
            return result
        # 基本类型直接返回
        else:
            return value
    
    # 直接转换整个params对象，而不是它的__dict__
    return convert_value(params)


def create_default_state() -> MicroscopeState:
    """创建默认的显微镜状态"""
    return MicroscopeState()


def create_default_params() -> MicroscopeParams:
    """创建默认的显微镜参数"""
    return MicroscopeParams()


def validate_params(params: MicroscopeParams) -> List[str]:
    """验证参数有效性，返回错误信息列表"""
    errors = []
    
    # 验证电子枪参数
    if params.gun.voltage < params.gun.min_voltage or params.gun.voltage > params.gun.max_voltage:
        errors.append(f"Gun voltage must be between {params.gun.min_voltage} and {params.gun.max_voltage} kV")
    
    # 验证相机参数
    if params.camera.exposure_time < params.camera.min_exposure_time or params.camera.exposure_time > params.camera.max_exposure_time:
        errors.append(f"Camera exposure time must be between {params.camera.min_exposure_time} and {params.camera.max_exposure_time} ms")
    
    # 验证投影参数
    if params.projection.magnification < params.projection.min_magnification or params.projection.magnification > params.projection.max_magnification:
        errors.append(f"Projection magnification must be between {params.projection.min_magnification} and {params.projection.max_magnification}")
    
    return errors
