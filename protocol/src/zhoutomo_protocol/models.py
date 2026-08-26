"""Platform-independent microscope state and parameter models.

These dataclasses are the shared vocabulary between ZhouTomo client and server.
Units intentionally match the legacy ZhouTomo domain model.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MicroscopeMode(Enum):
    IMAGING = "imaging"
    DIFFRACTION = "diffraction"
    STEM = "stem"
    EELS = "eels"


class VacuumStatus(Enum):
    VACUUM = "vacuum"
    AIR = "air"
    VENTING = "venting"
    PUMPING = "pumping"


class CameraStatus(Enum):
    IDLE = "idle"
    ACQUIRING = "acquiring"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class GunState:
    status: Any = None


@dataclass
class GunParams:
    status: Any = None


@dataclass
class IlluminationState:
    stem_magnification: float = 5000
    stem_rotation: float = -5.7


@dataclass
class IlluminationParams:
    stem_magnification: float = 5000
    stem_rotation: float = -5.7


@dataclass
class ProjectionState:
    defocus: float = 0.0


@dataclass
class ProjectionParams:
    defocus: float = 0.0
    magnification: float = 1000.0
    objective_aperture: int = 1
    intermediate_aperture: int = 1
    selected_aperture: int = 1
    min_magnification: float = 100.0
    max_magnification: float = 1_000_000.0


@dataclass
class StagePosition:
    """Stage position: x/y/z in metres, a/b in radians."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0


@dataclass
class StageState:
    position: StagePosition = field(default_factory=StagePosition)
    is_ready: bool = False
    limits: dict[str, tuple] = field(default_factory=dict)


@dataclass
class StageParams:
    position: StagePosition = field(default_factory=StagePosition)


@dataclass
class VacuumState:
    status: Any = None


@dataclass
class VacuumParams:
    status: Any = None


@dataclass
class ModeState:
    status: Any = None


@dataclass
class ModeParams:
    status: Any = None


@dataclass
class BlankerState:
    status: Any = None


@dataclass
class BlankerParams:
    status: Any = None


@dataclass
class CameraState:
    status: Any = None


@dataclass
class CameraParams:
    status: Any = None


@dataclass
class AcquisitionState:
    acq_image_size: int = 1
    dwell_time: float = 2
    brightness: float = 45.0
    contrast: float = 45.0
    binnings: int = 4
    frames: int = 1


@dataclass
class AcquisitionParams:
    acq_image_size: int = 1
    dwell_time: float = 2
    brightness: float = 45.0
    contrast: float = 45.0
    binnings: int = 4
    frames: int = 1


@dataclass
class AutoNormalizeState:
    is_enabled: bool = False
    is_running: bool = False
    last_normalized: float = 0.0
    normalization_factor: float = 1.0


@dataclass
class AutoNormalizeParams:
    is_enabled: bool = False
    interval: float = 60.0
    threshold: float = 0.1


@dataclass
class MicroscopeState:
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
    timestamp: float = 0.0
    system_status: str = "unknown"


@dataclass
class MicroscopeParams:
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
