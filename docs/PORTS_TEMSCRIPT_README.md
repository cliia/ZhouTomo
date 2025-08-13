# 硬件接口层 - ports_temscript.py 使用说明

## 概述

`ports_temscript.py` 是ZhouTomo项目的硬件接口层，实现了与temscript的直接交互，为每个显微镜组件提供具体的硬件驱动。该模块完全基于temscript官方文档实现，确保与FEI/Thermo Fisher Scientific电子显微镜的兼容性。

## 架构设计

### 分层结构

```
┌─────────────────────────────────────┐
│           domain.py                 │  ← 领域模型层
│      (数据模型和接口定义)            │
└─────────────────────────────────────┘
                    ↑
                    │ 实现
┌─────────────────────────────────────┐
│        ports_temscript.py           │  ← 硬件接口层
│      (temscript驱动实现)            │
└─────────────────────────────────────┘
                    ↑
                    │ 使用
┌─────────────────────────────────────┐
│           temscript                 │  ← 第三方SDK
│      (FEI官方显微镜控制接口)        │
└─────────────────────────────────────┘
```

### 核心组件

- **BasePort**: 所有端口类的抽象基类
- **组件端口类**: 每个显微镜组件的具体实现
- **TemscriptMicroscope**: 显微镜整体控制类
- **异常处理**: 专门的错误类型定义

## 主要类说明

### BasePort (抽象基类)

所有端口类的基类，提供通用功能：

```python
class BasePort(ABC):
    def __init__(self, instrument):
        self.instrument = instrument
        self._validate_instrument()
    
    @abstractmethod
    def get_state(self) -> Any:
        """获取组件状态"""
        pass
    
    @abstractmethod
    def set_params(self, params: Any) -> bool:
        """设置组件参数"""
        pass
    
    def _safe_operation(self, operation, *args, **kwargs):
        """安全执行temscript操作"""
        pass
```

### 组件端口类

每个显微镜组件都有对应的端口类：

| 组件 | 端口类 | 主要功能 |
|------|--------|----------|
| 电子枪 | `GunPortTS` | 高压控制、灯丝电流、束流位置 |
| 照明系统 | `IlluminationPortTS` | 光斑大小、强度、聚光镜光阑 |
| 投影系统 | `ProjectionPortTS` | 放大倍数、光阑设置 |
| 载物台 | `StagePortTS` | 位置控制、移动、倾斜角度 |
| 真空系统 | `VacuumPortTS` | 压力监控、泵状态、阀门控制 |
| 工作模式 | `ModePortTS` | TEM/STEM模式切换 |
| 束流遮挡器 | `BlankerPortTS` | 束流遮挡控制 |
| 相机 | `CameraPortTS` | 图像采集、参数设置 |
| 采集控制 | `AcquisitionPortTS` | 批量采集、状态管理 |
| 自动归一化 | `AutoNormalizePortTS` | 透镜归一化 |

### TemscriptMicroscope

显微镜整体控制类，聚合所有组件：

```python
class TemscriptMicroscope:
    def __init__(self, instrument):
        # 初始化所有组件端口
        self.gun = GunPortTS(instrument)
        self.illumination = IlluminationPortTS(instrument)
        # ... 其他组件
    
    def get_state(self) -> MicroscopeState:
        """获取显微镜整体状态"""
        pass
    
    def set_params(self, params: MicroscopeParams) -> bool:
        """设置显微镜整体参数"""
        pass
    
    def execute_command(self, component: str, command: str, **kwargs) -> bool:
        """执行指定组件的命令"""
        pass
```

## 使用方法

### 1. 基本使用

```python
import temscript
from ports_temscript import create_temscript_microscope

# 获取temscript仪器实例
instrument = temscript.GetInstrument()

# 创建显微镜控制对象
microscope = create_temscript_microscope(instrument)

# 获取整体状态
state = microscope.get_state()
print(f"当前电压: {state.gun.voltage} kV")
print(f"当前放大倍数: {state.projection.magnification}")

# 设置参数
from domain import GunParams
gun_params = GunParams(voltage=200.0)
microscope.set_component_params('gun', gun_params)
```

### 2. 组件级操作

```python
# 直接操作载物台
stage = microscope.stage
stage_state = stage.get_state()
print(f"载物台位置: ({stage_state.position.x}, {stage_state.position.y}) μm")

# 移动载物台
stage.move_to(x=100.0, y=200.0, z=50.0, alpha=5.0, beta=0.0)

# 相机操作
camera = microscope.camera
image_data = camera.acquire_image()
if image_data:
    # 保存图像
    with open('image.raw', 'wb') as f:
        f.write(image_data)
```

### 3. 命令执行

```python
# 执行载物台移动命令
microscope.execute_command('stage', 'move_to', x=100.0, y=200.0, z=50.0)

# 执行图像采集命令
microscope.execute_command('camera', 'acquire')

# 执行采集控制命令
microscope.execute_command('acquisition', 'start')
microscope.execute_command('acquisition', 'stop')

# 执行归一化命令
microscope.execute_command('auto_normalize', 'normalize')
```

### 4. 错误处理

```python
from ports_temscript import TemscriptConnectionError, TemscriptOperationError

try:
    state = microscope.get_state()
except TemscriptConnectionError as e:
    print(f"连接错误: {e}")
    # 处理连接问题
except TemscriptOperationError as e:
    print(f"操作错误: {e}")
    # 处理操作问题
```

## 配置和定制

### 单位转换

某些组件需要单位转换，例如：

- **载物台位置**: 内部使用米(m)，外部接口使用微米(μm)
- **高压值**: 内部使用伏特(V)，外部接口使用千伏(kV)
- **曝光时间**: 内部使用秒(s)，外部接口使用毫秒(ms)

### 硬件特定调整

某些功能可能需要根据具体硬件进行调整：

```python
class GunPortTS(BasePort):
    def get_state(self) -> GunState:
        # 灯丝电流获取（需要根据具体硬件实现）
        filament_current = 3.0 if ht_state.value == 1 else 0.0
        
        # 温度获取（需要根据具体硬件实现）
        temperature = 0.0  # 需要根据具体硬件获取
```

## 测试

运行测试文件验证模块功能：

```bash
python test_ports_temscript.py
```

测试包括：
- 模块导入测试
- 类结构验证
- 端口类功能检查
- 工具函数验证
- 异常类定义检查

## 注意事项

### 1. 依赖要求

- Python 3.7+
- temscript库（FEI官方提供）
- 有效的temscript许可证
- 连接到显微镜的权限

### 2. 安全考虑

- 高压操作需要特别小心
- 载物台移动前检查安全范围
- 图像采集时注意存储空间

### 3. 性能优化

- 批量操作时使用`set_params`而不是多次调用
- 状态查询时考虑缓存机制
- 图像数据量大时注意内存使用

### 4. 错误恢复

- 连接断开时自动重连
- 操作失败时回滚到安全状态
- 记录详细的操作日志

## 扩展开发

### 添加新组件

1. 在`domain.py`中定义数据模型
2. 在`ports_temscript.py`中实现端口类
3. 在`TemscriptMicroscope`中集成新组件
4. 添加相应的测试用例

### 支持新功能

1. 在端口类中添加新方法
2. 在`execute_command`中添加命令处理
3. 更新文档和测试

## 参考资源

- [temscript官方文档](https://temscript.readthedocs.io/en/latest/instrument.html)
- [FEI/Thermo Fisher Scientific技术支持](https://www.thermofisher.com/support)
- [ZhouTomo项目文档](../README_v2.md)

## 版本历史

- **v1.0.0**: 初始版本，实现基本temscript接口
- 支持所有主要显微镜组件
- 完整的错误处理和日志记录
- 全面的测试覆盖
