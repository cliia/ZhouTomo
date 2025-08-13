# Domain.py 使用说明

## 概述

`domain.py` 是 ZhouTomo 项目的领域模型定义模块，包含了显微镜系统的所有核心数据模型和接口定义。该模块具有高度的可复用性和可读性，为整个系统提供了统一的数据结构。

## 主要特性

- **类型安全**: 使用 Python dataclass 和类型注解确保类型安全
- **可复用性**: 所有模型都可以独立使用，支持组合和扩展
- **可读性**: 清晰的命名规范和详细的文档注释
- **验证支持**: 内置参数验证功能
- **序列化支持**: 提供对象到字典的转换功能

## 核心组件

### 1. 枚举类型

#### MicroscopeMode
显微镜工作模式
- `IMAGING`: 成像模式
- `DIFFRACTION`: 衍射模式  
- `STEM`: 扫描透射模式
- `EELS`: 电子能量损失谱模式

#### VacuumStatus
真空状态
- `VACUUM`: 真空状态
- `AIR`: 大气状态
- `VENTING`: 正在放气
- `PUMPING`: 正在抽气

#### CameraStatus
相机状态
- `IDLE`: 空闲
- `ACQUIRING`: 正在采集
- `PROCESSING`: 正在处理
- `ERROR`: 错误状态

### 2. 状态类 (State Classes)

所有状态类都继承自 `@dataclass`，包含组件的当前状态信息：

- `GunState`: 电子枪状态
- `IlluminationState`: 照明系统状态
- `ProjectionState`: 投影系统状态
- `StageState`: 载物台状态
- `VacuumState`: 真空系统状态
- `ModeState`: 工作模式状态
- `BlankerState`: 束流遮挡器状态
- `CameraState`: 相机状态
- `AcquisitionState`: 采集状态
- `AutoNormalizeState`: 自动归一化状态

### 3. 参数类 (Params Classes)

所有参数类都继承自 `@dataclass`，包含组件的可设置参数：

- `GunParams`: 电子枪参数
- `IlluminationParams`: 照明系统参数
- `ProjectionParams`: 投影系统参数
- `StageParams`: 载物台参数
- `VacuumParams`: 真空系统参数
- `ModeParams`: 工作模式参数
- `BlankerParams`: 束流遮挡器参数
- `CameraParams`: 相机参数
- `AcquisitionParams`: 采集参数
- `AutoNormalizeParams`: 自动归一化参数

### 4. 聚合类

#### MicroscopeState
显微镜整体状态，聚合所有组件的状态。

#### MicroscopeParams
显微镜整体参数，聚合所有组件的参数。

### 5. 接口类

#### MicroscopeInterface
显微镜接口抽象类，定义了显微镜系统的基本操作：

```python
class MicroscopeInterface:
    def get_state(self) -> MicroscopeState: ...
    def set_params(self, params: MicroscopeParams) -> bool: ...
    def get_component_state(self, component: str) -> Any: ...
    def set_component_params(self, component: str, params: Any) -> bool: ...
    def execute_command(self, component: str, command: str, **kwargs) -> bool: ...
    def start_acquisition(self) -> bool: ...
    def stop_acquisition(self) -> bool: ...
    def is_connected(self) -> bool: ...
```

#### MicroscopeAggregate
显微镜聚合根，管理所有组件，提供统一的访问接口。

## 使用示例

### 基本使用

```python
from domain import (
    MicroscopeState, MicroscopeParams, 
    GunState, GunParams, CameraState, CameraParams
)

# 创建默认状态
state = MicroscopeState()
print(f"电子枪电压: {state.gun.voltage} kV")
print(f"相机状态: {state.camera.status.value}")

# 创建自定义参数
gun_params = GunParams(
    voltage=120.0,
    filament_current=3.2
)

camera_params = CameraParams(
    exposure_time=500.0,
    gain=2.0,
    binning=2
)
```

### 参数验证

```python
from domain import validate_params

# 验证参数
errors = validate_params(params)
if errors:
    print("参数验证失败:")
    for error in errors:
        print(f"  - {error}")
else:
    print("参数验证通过")
```

### 对象转换

```python
from domain import state_to_dict, params_to_dict

# 转换为字典
state_dict = state_to_dict(state)
params_dict = params_to_dict(params)

# 可以用于JSON序列化
import json
state_json = json.dumps(state_dict, indent=2)
```

### 实现接口

```python
from domain import MicroscopeInterface, MicroscopeState

class MyMicroscope(MicroscopeInterface):
    def get_state(self) -> MicroscopeState:
        # 实现获取状态的逻辑
        return MicroscopeState()
    
    def set_params(self, params: MicroscopeParams) -> bool:
        # 实现设置参数的逻辑
        return True
    
    # 实现其他方法...
```

## 扩展指南

### 添加新组件

1. 定义状态类：
```python
@dataclass
class NewComponentState:
    value: float = 0.0
    is_active: bool = False
```

2. 定义参数类：
```python
@dataclass
class NewComponentParams:
    target_value: float = 0.0
    auto_control: bool = True
```

3. 添加到聚合类：
```python
@dataclass
class MicroscopeState:
    # ... 其他组件
    new_component: NewComponentState = field(default_factory=NewComponentState)
```

### 添加验证规则

在 `validate_params` 函数中添加新的验证逻辑：

```python
def validate_params(params: MicroscopeParams) -> List[str]:
    errors = []
    
    # 现有验证...
    
    # 新组件验证
    if params.new_component.target_value < 0:
        errors.append("New component target value must be positive")
    
    return errors
```

## 最佳实践

1. **类型注解**: 始终使用类型注解来提高代码可读性和IDE支持
2. **默认值**: 为所有字段提供合理的默认值
3. **文档**: 为所有类和方法添加详细的文档字符串
4. **验证**: 在设置参数前始终进行验证
5. **不可变性**: 状态对象应该是不可变的，参数对象可以修改
6. **错误处理**: 使用适当的异常类型和错误消息

## 注意事项

1. 所有状态类和参数类都使用 `field(default_factory=...)` 来避免可变默认值问题
2. 枚举类型在序列化时会自动转换为字符串值
3. 转换函数会递归处理所有嵌套的 dataclass 对象
4. 验证函数返回错误消息列表，空列表表示验证通过

## 依赖关系

- Python 3.7+ (支持 dataclass)
- 标准库: `dataclasses`, `typing`, `enum`, `json`

## 测试

模块包含完整的测试覆盖，确保所有功能正常工作。运行测试：

```bash
python -m pytest test_domain.py
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个模块。请确保：

1. 遵循现有的代码风格
2. 添加适当的测试
3. 更新文档
4. 通过所有测试
