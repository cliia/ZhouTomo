"""
硬件接口层 - temscript驱动实现

本模块实现了与temscript的直接交互，为每个显微镜组件提供具体的硬件驱动。
所有Port类都实现了domain.py中定义的接口，确保可复用性和可读性。

参考文档: https://temscript.readthedocs.io/en/latest/instrument.html
"""

import logging
from typing import Optional, Tuple, List, Any, Dict
from abc import ABC, abstractmethod

# 导入domain.py中定义的数据模型
from domain import (
    GunState, GunParams,
    IlluminationState, IlluminationParams,
    ProjectionState, ProjectionParams,
    StageState, StageParams, StagePosition,
    VacuumState, VacuumParams,
    ModeState, ModeParams,
    BlankerState, BlankerParams,
    CameraState, CameraParams,
    AcquisitionState, AcquisitionParams,
    AutoNormalizeState, AutoNormalizeParams,
    MicroscopeState, MicroscopeParams,
    MicroscopeMode, VacuumStatus, CameraStatus
)

# 配置日志
logger = logging.getLogger(__name__)


class TemscriptConnectionError(Exception):
    """temscript连接错误"""
    pass


class TemscriptOperationError(Exception):
    """temscript操作错误"""
    pass


class BasePort(ABC):
    """端口基类，定义通用接口"""
    
    def __init__(self, instrument):
        """
        初始化端口
        
        Args:
            instrument: temscript.Instrument实例
        """
        try:
            self.instrument = instrument
            self._validate_instrument()
        except Exception as e:
            logger.error(f"Failed to initialize BasePort: {e}")
            raise
    
    def _validate_instrument(self):
        """验证instrument对象是否有效"""
        if not self.instrument:
            raise TemscriptConnectionError("Instrument object is None")
        
        try:
            # 尝试访问一个基本属性来验证连接
            self.instrument.Configuration
        except Exception as e:
            raise TemscriptConnectionError(f"Failed to validate instrument connection: {e}")
    
    @abstractmethod
    def get_state(self) -> Any:
        """获取组件状态"""
        pass
    
    @abstractmethod
    def set_params(self, params: Any) -> bool:
        """设置组件参数"""
        pass
    
    def _safe_operation(self, operation, *args, **kwargs):
        """
        安全执行temscript操作
        
        Args:
            operation: 要执行的操作函数
            *args, **kwargs: 操作参数
            
        Returns:
            操作结果
            
        Raises:
            TemscriptOperationError: 操作失败时抛出
        """
        try:
            result = operation(*args, **kwargs)
            logger.debug(f"Operation {operation.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Operation {operation.__name__} failed: {e}")
            raise TemscriptOperationError(f"Operation failed: {e}")


class GunPortTS(BasePort):
    """
    电子枪端口 - temscript实现
    
    电子枪状态不允许修改
    
    """
    
    def get_state(self) -> GunState:
        """获取电子枪状态"""
        return GunState()
    
    def set_params(self, params: GunParams) -> bool:
        """设置电子枪参数"""
        return True


class IlluminationPortTS(BasePort):
    """
    聚光镜系统端口 - temscript 实现

    本系统管理两个重要参数：

    STEM 放大倍数： stem_magnification
    STEM 旋转角度： stem_rotation

    其余参数参见 https://temscript.readthedocs.io/en/latest/instrument.html#temscript.Illumination
    暂时不支持设置其余参数
    
    """
    
    
    def get_state(self) -> IlluminationState:
        """获取照明系统状态"""
        try:
            # STEM 放大倍数
            stem_magnification = self.instrument.Illumination.StemMagnification
            
            # STEM 旋转角度
            stem_rotation = self.instrument.Illumination.StemRotation
            
            return IlluminationState(
                stem_magnification=stem_magnification,
                stem_rotation=stem_rotation,
            )
        except Exception as e:
            logger.error(f"Failed to get illumination state: {e}")
            raise TemscriptOperationError(f"Failed to get illumination state: {e}")
    
    def set_params(self, params: IlluminationParams) -> bool:
        """设置照明系统参数"""
        try:
            if hasattr(params, 'stem_magnification') and params.stem_magnification > 0:
                self.instrument.Illumination.StemMagnification = params.stem_magnification
                logger.info(f"Set stem magnification to {params.stem_magnification}")
            
            if hasattr(params, 'stem_rotation') and params.stem_rotation > 0:
                self.instrument.Illumination.StemRotation = params.stem_rotation
                logger.info(f"Set stem rotation to {params.stem_rotation}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set illumination params: {e}")
            raise TemscriptOperationError(f"Failed to set illumination params: {e}")


class ProjectionPortTS(BasePort):
    """
    投影系统端口 - temscript实现

    本系统管理一个重要参数：

    离焦量： defocus

    其余参数参见 https://temscript.readthedocs.io/en/latest/instrument.html#temscript.Projection
    暂时不支持设置其余参数
    
    """
    
    def get_state(self) -> ProjectionState:
        """获取投影系统状态"""
        try:
            # 获取离焦量
            # ! Unit: m
            defocus = self.instrument.Projection.Defocus
            
            return ProjectionState(
                defocus=defocus
            )
        except Exception as e:
            logger.error(f"Failed to get projection state: {e}")
            raise TemscriptOperationError(f"Failed to get projection state: {e}")
    
    def set_params(self, params: ProjectionParams) -> bool:
        """设置投影系统参数"""
        try:
            if hasattr(params, 'defocus') and params.defocus > 0:
                self.instrument.Projection.Defocus = params.defocus
                logger.info(f"Set defocus to {params.defocus}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set projection params: {e}")
            raise TemscriptOperationError(f"Failed to set projection params: {e}")


class StagePortTS(BasePort):
    """载物台端口 - temscript实现 - READY"""
    
    def get_state(self) -> StageState:
        """获取载物台状态"""
        try: 
            # 获取载物台位置
            # ! Unit: um, um, um, rad, rad
            stage_position = self.instrument.Stage.Position
            
            # 运动状态（IntEnum）
            #     READY = 0
            #     DISABLED = 1
            #     NOT_READY = 2
            #     GOING = 3
            #     MOVING = 4
            #     WOBBLING = 5
            #     DISABLE = 1         # Misnaming in temscript 1.X
            stage_status = self.instrument.Stage.Status
            is_ready = stage_status == 0
            # AxisData
            limits = {}
            limits['x'] = self.instrument.Stage.AxisData('x')
            limits['y'] = self.instrument.Stage.AxisData('y')
            limits['z'] = self.instrument.Stage.AxisData('z')
            limits['a'] = self.instrument.Stage.AxisData('a')
            limits['b'] = self.instrument.Stage.AxisData('b')

            return StageState(
                position=stage_position,
                is_ready=is_ready,
                limits=limits  # 需要根据具体硬件获取
            )
        except Exception as e:
            logger.error(f"Failed to get stage state: {e}")
            raise TemscriptOperationError(f"Failed to get stage state: {e}")
    
    def set_params(self, params: StageParams) -> bool:
        """设置载物台参数"""
        try:
            # 有 position 参数，则移动到该位置
            if hasattr(params, 'position') and params.position > 0:
                self.instrument.Stage.GoTo(
                    x=params.position.x,
                    y=params.position.y,
                    z=params.position.z,
                    a=params.position.a,
                    b=params.position.b
                )
            return True
        except Exception as e:
            logger.error(f"Failed to set stage params: {e}")
            raise TemscriptOperationError(f"Failed to set stage params: {e}")


class VacuumPortTS(BasePort):
    """
    真空系统端口 - temscript实现
    
    没有需要获取和修改的参数

    """
    
    def get_state(self) -> VacuumState:
        """获取真空系统状态"""
        return VacuumState()

    def set_params(self, params: VacuumParams) -> bool:
        """设置真空系统参数"""
        return True


class ModePortTS(BasePort):
    """工作模式端口 - temscript实现"""
    
    def get_state(self) -> ModeState:
        return ModeState()
    
    def set_params(self, params: ModeParams) -> bool:
        return True


class BlankerPortTS(BasePort):
    """束流遮挡器端口 - temscript实现"""
    
    def get_state(self) -> BlankerState:
        return BlankerState()
    
    def set_params(self, params: BlankerParams) -> bool:
        """设置束流遮挡器参数"""
        return True


class CameraPortTS(BasePort):
    """相机端口 - temscript实现"""
    
    def get_state(self) -> CameraState:
        """获取相机状态"""
        return CameraState()
    
    def set_params(self, params: CameraParams) -> bool:
        """设置相机参数"""
        return True


class AcquisitionPortTS(BasePort):
    """采集端口 - temscript实现"""
    
    def __init__(self, instrument):
        super().__init__(instrument)
        self._is_running = False
        self._acquired_frames = []

        self._acq_image_size = 1
        self._dwell_time = 2
        self._brightness = 45.0
        self._contrast = 45.0
        self._binnings = 4
        self._frames = 1
    
    def get_state(self) -> AcquisitionState:
        """获取采集状态"""
        return AcquisitionState(
            acq_image_size=self.instrument.Acquisition.StemAcqParams.AcqImageSize,
            dwell_time=self.instrument.Acquisition.StemAcqParams.DwellTime,
            brightness=self.instrument.Acquisition.STEMDetectorInfo.Brightness,
            contrast=self.instrument.Acquisition.STEMDetectorInfo.Contrast,
            binnings=self.instrument.Acquisition.STEMDetectorInfo.Binnings,
            frames=self._frames
        )
    
    def set_params(self, params: AcquisitionParams) -> bool:
        """设置采集参数"""
        logger.info(f"=== AcquisitionPortTS.set_params 开始 ===")
        logger.info(f"接收到的参数: {params}")
        logger.info(f"参数类型: {type(params)}")
        
        try:
            # 改进参数验证逻辑
            if hasattr(params, 'acq_image_size'):
                if params.acq_image_size >= 0:  # 允许0值
                    self._acq_image_size = params.acq_image_size
                    self.instrument.Acquisition.StemAcqParams.AcqImageSize = params.acq_image_size
                    logger.info(f"Set acq_image_size to {params.acq_image_size}")
                else:
                    logger.warning(f"Invalid acq_image_size: {params.acq_image_size}, keeping current value: {self._acq_image_size}")
            
            if hasattr(params, 'dwell_time'):
                if params.dwell_time > 0:
                    self._dwell_time = params.dwell_time
                    self.instrument.Acquisition.StemAcqParams.DwellTime = params.dwell_time
                    logger.info(f"Set dwell_time to {params.dwell_time}")
                else:
                    logger.warning(f"Invalid dwell_time: {params.dwell_time}, keeping current value: {self._dwell_time}")
            
            if hasattr(params, 'brightness'):
                if params.brightness >= 0:  # 允许0值
                    self._brightness = params.brightness
                    self.instrument.Acquisition.STEMDetectorInfo.Brightness = params.brightness
                    logger.info(f"Set brightness to {params.brightness}")
                else:
                    logger.warning(f"Invalid brightness: {params.brightness}, keeping current value: {self._brightness}")
            
            if hasattr(params, 'contrast'):
                if params.contrast >= 0:  # 允许0值
                    self._contrast = params.contrast
                    self.instrument.Acquisition.STEMDetectorInfo.Contrast = params.contrast
                    logger.info(f"Set contrast to {params.contrast}")
                else:
                    logger.warning(f"Invalid contrast: {params.contrast}, keeping current value: {self._contrast}")
            
            if hasattr(params, 'binnings'):
                if params.binnings > 0:
                    self._binnings = params.binnings
                    self.instrument.Acquisition.STEMDetectorInfo.Binnings = params.binnings
                    logger.info(f"Set binnings to {params.binnings}")
                else:
                    logger.warning(f"Invalid binnings: {params.binnings}, keeping current value: {self._binnings}")
            
            if hasattr(params, 'frames'):
                if params.frames > 0:
                    self._frames = params.frames
                    logger.info(f"Set frames to {params.frames}")
                else:
                    logger.warning(f"Invalid frames: {params.frames}, keeping current value: {self._frames}")
            
            logger.info(f"=== AcquisitionPortTS.set_params 完成，返回True ===")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set acquisition params: {e}")
            logger.error(f"异常类型: {type(e)}")
            logger.error(f"异常详情: {str(e)}")
            
            # 获取更详细的错误信息
            import traceback
            logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
            
            raise TemscriptOperationError(f"Failed to set acquisition params: {e}")
    
    def start_acquisition(self) -> List[bytes]:
        """开始采集"""
        try:
            self._is_running = True
            self._acquired_frames = []
            logger.info("Started acquisition")
            self.instrument.Acquisition.RemoveAllAcqDevices()
            self.instrument.Acquisition.AddAcqDeviceByName('HAADF')

            for _ in range(self._frames):
                self._acquired_frames.append(self.instrument.Acquisition.AcquireImages()[0].Array.tobytes())
            
            self._is_running = False
            return self._acquired_frames
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            self._is_running = False
            raise TemscriptOperationError(f"Failed to start acquisition: {e}")
        
    def stop_acquisition(self) -> bool:
        """停止采集"""
        raise NotImplementedError("AcquisitionPortTS does not support stop_acquisition")

class AutoNormalizePortTS(BasePort):
    """自动归一化端口 - temscript实现"""
    
    def get_state(self) -> AutoNormalizeState:
        """获取自动归一化状态"""
        try:
            # 检查是否启用自动归一化
            is_enabled = self.instrument.AutoNormalizeEnabled
            
            return AutoNormalizeState(
                is_enabled=is_enabled,
                is_running=False,
                last_normalized=0.0,
                normalization_factor=1.0
            )
        except Exception as e:
            logger.error(f"Failed to get auto normalize state: {e}")
            raise TemscriptOperationError(f"Failed to get auto normalize state: {e}")
    
    def set_params(self, params: AutoNormalizeParams) -> bool:
        """设置自动归一化参数"""
        try:
            if hasattr(params, 'is_enabled'):
                self.instrument.AutoNormalizeEnabled = params.is_enabled
                logger.info(f"Set auto normalize enabled to {params.is_enabled}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set auto normalize params: {e}")
            raise TemscriptOperationError(f"Failed to set auto normalize params: {e}")
    
    def normalize_all(self) -> bool:
        """执行归一化"""
        try:
            self.instrument.NormalizeAll()
            logger.info("Normalized all lenses")
            return True
        except Exception as e:
            logger.error(f"Failed to normalize all: {e}")
            raise TemscriptOperationError(f"Failed to normalize all: {e}")


class TemscriptMicroscope:
    """temscript显微镜实现类"""
    
    def __init__(self, instrument):
        """
        初始化temscript显微镜
        
        Args:
            instrument: temscript.Instrument实例
        """
        try:
            self.instrument = instrument
            
            # 初始化所有组件端口
            self.gun = GunPortTS(instrument)
            self.illumination = IlluminationPortTS(instrument)
            self.projection = ProjectionPortTS(instrument)
            self.stage = StagePortTS(instrument)
            self.vacuum = VacuumPortTS(instrument)
            self.mode = ModePortTS(instrument)
            self.blanker = BlankerPortTS(instrument)
            self.camera = CameraPortTS(instrument)
            self.acquisition = AcquisitionPortTS(instrument)
            self.auto_normalize = AutoNormalizePortTS(instrument)
            
        except Exception as e:
            logger.error(f"Failed to initialize TemscriptMicroscope: {e}")
            raise
    
    def get_state(self) -> MicroscopeState:
        """获取显微镜整体状态"""
        try:
            return MicroscopeState(
                gun=self.gun.get_state(),
                illumination=self.illumination.get_state(),
                projection=self.projection.get_state(),
                stage=self.stage.get_state(),
                vacuum=self.vacuum.get_state(),
                mode=self.mode.get_state(),
                blanker=self.blanker.get_state(),
                camera=self.camera.get_state(),
                acquisition=self.acquisition.get_state(),
                auto_normalize=self.auto_normalize.get_state(),
                timestamp=0.0,  # 需要添加时间戳
                system_status="connected"
            )
        except Exception as e:
            logger.error(f"Failed to get microscope state: {e}")
            raise TemscriptOperationError(f"Failed to get microscope state: {e}")
    
    def set_params(self, params: MicroscopeParams) -> bool:
        """设置显微镜整体参数"""
        try:
            # 设置各个组件的参数
            if params.gun:
                self.gun.set_params(params.gun)
            if params.illumination:
                self.illumination.set_params(params.illumination)
            if params.projection:
                self.projection.set_params(params.projection)
            if params.stage:
                self.stage.set_params(params.stage)
            if params.vacuum:
                self.vacuum.set_params(params.vacuum)
            if params.mode:
                self.mode.set_params(params.mode)
            if params.blanker:
                self.blanker.set_params(params.blanker)
            if params.camera:
                self.camera.set_params(params.camera)
            if params.acquisition:
                self.acquisition.set_params(params.acquisition)
            if params.auto_normalize:
                self.auto_normalize.set_params(params.auto_normalize)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set microscope params: {e}")
            raise TemscriptOperationError(f"Failed to set microscope params: {e}")
    
    def get_component_state(self, component: str) -> Any:
        """获取指定组件的状态"""
        component_map = {
            'gun': self.gun,
            'illumination': self.illumination,
            'projection': self.projection,
            'stage': self.stage,
            'vacuum': self.vacuum,
            'mode': self.mode,
            'blanker': self.blanker,
            'camera': self.camera,
            'acquisition': self.acquisition,
            'auto_normalize': self.auto_normalize
        }
        
        if component not in component_map:
            raise ValueError(f"Unknown component: {component}")
        
        return component_map[component].get_state()
    
    def set_component_params(self, component: str, params: Any) -> bool:
        """设置指定组件的参数"""
        logger.info(f"=== TemscriptMicroscope.set_component_params 开始 ===")
        logger.info(f"组件: {component}")
        logger.info(f"参数: {params}")
        logger.info(f"参数类型: {type(params)}")
        logger.info(f"可用组件: {list(self._components.keys())}")
        
        component_map = {
            'gun': self.gun,
            'illumination': self.illumination,
            'projection': self.projection,
            'stage': self.stage,
            'vacuum': self.vacuum,
            'mode': self.mode,
            'blanker': self.blanker,
            'camera': self.camera,
            'acquisition': self.acquisition,
            'auto_normalize': self.auto_normalize
        }
        
        logger.info(f"组件映射: {component_map}")
        
        if component not in component_map:
            logger.error(f"未知组件: {component}")
            raise ValueError(f"Unknown component: {component}")
        
        try:
            logger.info(f"组件 {component} 存在，获取对应的Port对象...")
            port_object = component_map[component]
            logger.info(f"Port对象类型: {type(port_object)}")
            logger.info(f"Port对象: {port_object}")
            
            if port_object is None:
                logger.error(f"组件 {component} 的Port对象为None")
                return False
            
            # 特殊处理acquisition组件
            if component == 'acquisition':
                logger.info(f"处理acquisition组件，参数详情:")
                if hasattr(params, '__dict__'):
                    for key, value in params.__dict__.items():
                        logger.info(f"  {key}: {value} (类型: {type(value)})")
                else:
                    logger.info(f"  参数不是对象: {params}")
            
            logger.info(f"调用Port对象的set_params方法...")
            result = port_object.set_params(params)
            logger.info(f"Port.set_params 结果: {result}")
            
            if result is False:
                logger.warning(f"Port.set_params 返回False，这可能表示参数设置失败")
            
            return result
        except Exception as e:
            logger.error(f"设置组件参数时发生异常: {e}")
            logger.error(f"异常类型: {type(e)}")
            logger.error(f"异常详情: {str(e)}")
            
            # 获取更详细的错误信息
            import traceback
            logger.error(f"完整堆栈跟踪:\n{traceback.format_exc()}")
            
            raise
        finally:
            logger.info(f"=== TemscriptMicroscope.set_component_params 完成 ===")
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行指定组件的命令"""
        try:
            if component == 'stage' and command == 'move_to':
                x = kwargs.get('x', 0.0)
                y = kwargs.get('y', 0.0)
                z = kwargs.get('z', 0.0)
                alpha = kwargs.get('alpha', 0.0)
                beta = kwargs.get('beta', 0.0)
                return self.stage.move_to(x, y, z, alpha, beta)
            
            elif component == 'camera' and command == 'acquire':
                return self.camera.acquire_image() is not None
            elif component == 'camera' and command == 'capture':
                # capture命令等同于acquire，但支持更多参数
                return self.camera.acquire_image() is not None
            
            elif component == 'acquisition' and command == 'start':
                return self.acquisition.start_acquisition()
            
            elif component == 'acquisition' and command == 'stop':
                return self.acquisition.stop_acquisition()
            
            elif component == 'auto_normalize' and command == 'normalize':
                return self.auto_normalize.normalize_all()
            
            else:
                raise ValueError(f"Unknown command: {command} for component: {component}")
        
        except Exception as e:
            logger.error(f"Failed to execute command {command} on {component}: {e}")
            raise TemscriptOperationError(f"Failed to execute command: {e}")
    
    def start_acquisition(self) -> bool:
        """开始图像采集"""
        return self.acquisition.start_acquisition()
    
    def stop_acquisition(self) -> bool:
        """停止图像采集"""
        return self.acquisition.stop_acquisition()
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        try:
            # 尝试访问一个基本属性来验证连接
            _ = self.instrument.Configuration
            return True
        except Exception:
            return False


def create_temscript_microscope(instrument) -> TemscriptMicroscope:
    """
    创建temscript显微镜实例
    
    Args:
        instrument: temscript.Instrument实例
        
    Returns:
        TemscriptMicroscope实例
    """
    try:
        microscope = TemscriptMicroscope(instrument)
        return microscope
        
    except Exception as e:
        logger.error(f"Failed to create TemscriptMicroscope: {e}")
        raise


def validate_temscript_connection(instrument) -> bool:
    """
    验证temscript连接是否有效
    
    Args:
        instrument: temscript.Instrument实例
        
    Returns:
        连接是否有效
    """
    try:
        # 尝试访问配置信息
        instrument.Configuration
        return True
        
    except Exception as e:
        logger.error(f"temscript connection validation failed: {e}")
        return False


class NullMicroscope:
    """空显微镜模拟器，用于测试和开发"""
    
    def __init__(self):
        """初始化空显微镜模拟器"""
        self._connected = True
        self._components = {
            'gun': NullGunPort(),
            'illumination': NullIlluminationPort(),
            'projection': NullProjectionPort(),
            'stage': NullStagePort(),
            'vacuum': NullVacuumPort(),
            'mode': NullModePort(),
            'blanker': NullBlankerPort(),
            'camera': NullCameraPort(),
            'acquisition': NullAcquisitionPort(),
            'auto_normalize': NullAutoNormalizePort()
        }
        logger.info("Null microscope simulator initialized")
    
    def get_state(self) -> MicroscopeState:
        """获取模拟器状态"""
        return MicroscopeState(
            gun=self._components['gun'].get_state(),
            illumination=self._components['illumination'].get_state(),
            projection=self._components['projection'].get_state(),
            stage=self._components['stage'].get_state(),
            vacuum=self._components['vacuum'].get_state(),
            mode=self._components['mode'].get_state(),
            blanker=self._components['blanker'].get_state(),
            camera=self._components['camera'].get_state(),
            acquisition=self._components['acquisition'].get_state(),
            auto_normalize=self._components['auto_normalize'].get_state()
        )
    
    def set_params(self, params: MicroscopeParams) -> bool:
        """设置模拟器参数"""
        try:
            for component, component_params in params.dict(exclude_unset=True).items():
                if component in self._components:
                    self._components[component].set_params(component_params)
            return True
        except Exception as e:
            logger.error(f"Failed to set params: {e}")
            return False
    
    def get_component_state(self, component: str) -> Any:
        """获取指定组件状态"""
        if component in self._components:
            return self._components[component].get_state()
        return None
    
    def set_component_params(self, component: str, params: Any) -> bool:
        """设置指定组件参数"""
        component_map = {
            'gun': self._components['gun'],
            'illumination': self._components['illumination'],
            'projection': self._components['projection'],
            'stage': self._components['stage'],
            'vacuum': self._components['vacuum'],
            'mode': self._components['mode'],
            'blanker': self._components['blanker'],
            'camera': self._components['camera'],
            'acquisition': self._components['acquisition'],
            'auto_normalize': self._components['auto_normalize']
        }
        
        if component not in component_map:
            logger.error(f"Unknown component: {component}")
            raise ValueError(f"Unknown component: {component}")
        
        try:
            port_object = component_map[component]
            
            if port_object is None:
                logger.error(f"Port object for component {component} is None")
                return False
            
            return port_object.set_params(params)
        except Exception as e:
            logger.error(f"Error setting component params: {e}")
            raise
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行指定组件的命令"""
        try:
            if component == 'stage' and command == 'move_to':
                # 模拟载物台移动
                return True
            
            elif component == 'camera' and command == 'capture':
                # 模拟相机采集
                return True
            
            elif component == 'acquisition' and command == 'start':
                return self._components['acquisition'].start_acquisition()
            
            elif component == 'acquisition' and command == 'stop':
                return self._components['acquisition'].stop_acquisition()
            
            elif component == 'auto_normalize' and command == 'normalize':
                # 模拟自动归一化
                return True
            
            else:
                logger.warning(f"Unknown command: {command} for component: {component}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to execute command {command} on {component}: {e}")
            return False
    
    def start_acquisition(self) -> bool:
        """开始采集（一次性，返回帧列表）"""
        return self._components['acquisition'].start_acquisition()
    
    def stop_acquisition(self) -> bool:
        """停止采集"""
        return self._components['acquisition'].stop_acquisition()
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected


class NullPort:
    """空端口基类"""
    
    def __init__(self):
        self._state = self._get_default_state()
    
    def _get_default_state(self):
        """获取默认状态，子类需要重写"""
        return None
    
    def get_state(self):
        """获取状态"""
        return self._state
    
    def set_params(self, params):
        """设置参数"""
        logger.info(f"=== NullPort.set_params 开始 ===")
        logger.info(f"参数: {params}")
        logger.info(f"参数类型: {type(params)}")
        
        # 模拟器模式下，参数设置总是成功
        logger.info(f"✓ 模拟器模式，参数设置成功")
        return True
    
    def execute_command(self, component: str, command: str, **kwargs):
        """执行命令"""
        # 模拟器模式下，命令执行总是成功
        # 注意：这里接收component参数以保持接口一致性
        # 记录接收到的命令和参数（用于调试）
        logger.debug(f"NullPort executing command: {command} on component: {component} with kwargs: {kwargs}")
        return True


class NullGunPort(NullPort):
    """空枪端口"""
    
    def _get_default_state(self):
        return GunState(
            status=None
        )


class NullIlluminationPort(NullPort):
    """空照明端口"""
    
    def _get_default_state(self):
        return IlluminationState(
            stem_magnification=5000,
            stem_rotation=-5.7
        )


class NullProjectionPort(NullPort):
    """空投影端口"""
    
    def _get_default_state(self):
        return ProjectionState(
            defocus=0.0
        )


class NullStagePort(NullPort):
    """载物台端口 - temscript实现 - READY"""
    def __init__(self):
        super().__init__()
        self._performance = {
            'xyz_precision': 0.1,  # ! Unit: um
            'ab_precision': 0.5,  # ! Unit: deg
        }

    def _get_default_state(self):
        return StageState(
            position=StagePosition(x=0.0, y=0.0, z=0.0, a=0.0, b=0.0),
            is_ready=True,
            limits={}
        )
        
    def get_state(self) -> StageState:
        """获取载物台状态"""
        try: 
            # 获取载物台位置
            # ! Unit: um, um, um, rad, rad
            stage_position = self._state.position  
            
            # 运动状态
            is_ready = self._state.is_ready
            
            # AxisData
            limits = {}
            limits['x'] = (-0.001, 0.001, 'METERS')
            limits['y'] = (-0.001, 0.001, 'METERS')
            limits['z'] = (-0.001, 0.001, 'METERS')
            limits['a'] = (-1.5795, 1.5795, 'RADIANS')
            limits['b'] = (0, 0, 'UNKNOWN')

            return StageState(
                position=stage_position,
                is_ready=is_ready,
                limits=limits  # 需要根据具体硬件获取
            )
        except Exception as e:
            logger.error(f"Failed to get stage state: {e}")
            raise TemscriptOperationError(f"Failed to get stage state: {e}")
    
    def set_params(self, params: StageParams) -> bool:
        """设置载物台参数"""
        try:
            # 有 position 参数，则移动到该位置
            if hasattr(params, 'position') and params.position > 0:
                self._state.position = params.position
                logger.info(f"Stage: position set to {params.position}")
                import time
                time.sleep(1)
                
            if hasattr(params, 'is_ready') and params.is_ready:
                # 警告为只读
                logger.warning("Stage: parameter `is_ready` is read-only")
            if hasattr(params, 'limits') and params.limits > 0:
                # 警告为只读
                logger.warning("Stage: parameter `limits` is read-only")
            return True
        except Exception as e:
            logger.error(f"Failed to set stage params: {e}")
            raise TemscriptOperationError(f"Failed to set stage params: {e}")


class NullVacuumPort(NullPort):
    """空真空端口"""
    
    def _get_default_state(self):
        return VacuumState(
            status=None
        )


class NullModePort(NullPort):
    """空模式端口"""
    
    def _get_default_state(self):
        return ModeState(
            status=None
        )


class NullBlankerPort(NullPort):
    """空消隐器端口"""
    
    def _get_default_state(self):
        return BlankerState(
            status=None
        )


class NullCameraPort(NullPort):
    """空相机端口"""
    
    def _get_default_state(self):
        return CameraState(
            status=None
        )

    def acquire_image(self) -> Optional[bytes]:
        """采集一帧模拟图像数据
        返回任意字节串即可，当前上层仅使用元数据进行演示。
        """
        try:
            # 简单递增帧计数
            if hasattr(self, "_state") and hasattr(self._state, "frame_count"):
                self._state.frame_count = (self._state.frame_count or 0) + 1
                self._state.status = CameraStatus.ACQUIRING
            # 返回占位字节数据
            return b"mock_frame_data"
        except Exception:
            return None


class NullAcquisitionPort(NullPort):
    """空采集端口"""
    def __init__(self):
        self._is_running = False
        self._acquired_frames = []
        self._acq_image_size = 1
        self._dwell_time = 2
        self._brightness = 45.0
        self._contrast = 45.0
        self._binnings = 4
        self._frames = 1
        super().__init__()

        self._real_size_dict = {
            1: 2048,
            2: 1024,
            4: 512,
            8: 256,
            16: 128,
            32: 64,
            64: 16,
        }
    
    def _get_default_state(self):
        return AcquisitionState(
            acq_image_size=self._acq_image_size,
            dwell_time=self._dwell_time,
            brightness=self._brightness,
            contrast=self._contrast,
            binnings=self._binnings,
            frames=self._frames
        )
    
    def get_state(self) -> AcquisitionState:
        """获取采集状态"""
        return AcquisitionState(
            acq_image_size=self._acq_image_size,
            dwell_time=self._dwell_time,
            brightness=self._brightness,
            contrast=self._contrast,
            binnings=self._binnings,
            frames=self._frames
        )

    def set_params(self, params: AcquisitionParams) -> bool:
        """设置模拟采集参数，保持与 AcquisitionPortTS 相同接口"""
        try:
            if hasattr(params, 'acq_image_size') and params.acq_image_size > 0:
                self._acq_image_size = params.acq_image_size
                logger.info(f"Set acq_image_size to {params.acq_image_size}")
            if hasattr(params, 'dwell_time') and params.dwell_time > 0:
                self._dwell_time = params.dwell_time
                logger.info(f"Set dwell_time to {params.dwell_time}")
            if hasattr(params, 'brightness') and params.brightness > 0:
                self._brightness = params.brightness
                logger.info(f"Set brightness to {params.brightness}")
            if hasattr(params, 'contrast') and params.contrast > 0:
                self._contrast = params.contrast
                logger.info(f"Set contrast to {params.contrast}")
            if hasattr(params, 'binnings') and params.binnings > 0:
                self._binnings = params.binnings
                logger.info(f"Set binnings to {params.binnings}")
            if hasattr(params, 'frames') and params.frames > 0:
                self._frames = params.frames
                logger.info(f"Set frames to {params.frames}")
            return True
        except Exception as e:
            logger.error(f"Failed to set acquisition params (null): {e}")
            return False

    def start_acquisition(self) -> List[bytes]:
        """开始模拟采集，返回字节帧列表"""
        try:
            import numpy as np
            self._is_running = True
            self._acquired_frames = []
            logger.info("Started acquisition")
            for _ in range(self._frames):
                # 生成随机图像 -> 转为bytes存储
                real_size = self._real_size_dict[self._acq_image_size]
                arr = np.random.randint(0, 65535, (real_size, real_size), dtype=np.uint16)
                self._acquired_frames.append(arr.tobytes())
                import time
            self._is_running = False
            return self._acquired_frames
        
        except Exception as e:
            logger.error(f"Failed to start acquisition (null): {e}")
            self._is_running = False
            return []

    def stop_acquisition(self) -> bool:
        raise NotImplementedError("NullAcquisitionPort does not support stop_acquisition")
    

class NullAutoNormalizePort(NullPort):
    """空自动归一化端口"""
    
    def _get_default_state(self):
        return AutoNormalizeState(
            is_enabled=False,
            is_running=False,
            last_normalized=0.0,
            normalization_factor=1.0
        )
