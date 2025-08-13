# Wiring.py 模块使用说明

## 概述

`wiring.py` 是ZhouTomo项目的装配层模块，负责：
1. 决定使用哪种显微镜实现（local/remote/null）
2. 把所有组件的Port实例化，组合成MicroscopeAggregate
3. 提供工厂模式创建不同类型的显微镜实例

## 核心概念

### 1. 显微镜模式 (Microscope Mode)

- **local**: 本地直接使用temscript控制显微镜
- **remote**: 连接远程temscript服务器
- **null**: 使用模拟器（用于离线调试）

### 2. 工厂模式 (Factory Pattern)

使用工厂模式来创建不同类型的显微镜实例，确保代码的可扩展性和可维护性。

### 3. 装配类 (MicroscopeWiring)

主要的装配类，负责管理显微镜连接和组件聚合。

## 使用方法

### 基本使用

```python
from wiring import create_microscope_wiring

# 创建本地显微镜装配
wiring = create_microscope_wiring("local")

# 连接到显微镜
if wiring.connect():
    print("连接成功！")
    
    # 获取状态快照
    snapshot = wiring.get_snapshot()
    
    # 设置组件参数
    wiring.set_component_params("camera", camera_params)
    
    # 执行命令
    wiring.execute_command("stage", "move_to", x=100, y=200)
    
    # 断开连接
    wiring.disconnect()
else:
    print("连接失败！")
```

### 便捷函数

```python
from wiring import (
    create_local_wiring,
    create_null_wiring,
    create_remote_wiring,
    create_default_wiring
)

# 创建本地装配
local_wiring = create_local_wiring()

# 创建空装配（模拟器）
null_wiring = create_null_wiring()

# 创建远程装配
remote_wiring = create_remote_wiring("http://remote-server:8080")

# 创建默认装配（从环境变量读取配置）
default_wiring = create_default_wiring()
```

### 环境变量配置

```bash
# 设置默认模式
export ZHOUTOMO_MODE=local

# 设置远程服务器地址（仅在remote模式下需要）
export ZHOUTOMO_SERVER_URL=http://remote-server:8080
```

## 类结构

### MicroscopeFactory (抽象基类)

所有显微镜工厂的基类，定义了创建显微镜的标准接口。

### LocalTemscriptFactory

本地temscript显微镜工厂：
- 检查temscript模块是否可用
- 创建本地temscript显微镜实例
- 提供本地显微镜信息

### RemoteTemscriptFactory

远程temscript服务器工厂：
- 连接到远程temscript服务器
- 创建远程显微镜实例
- 提供远程连接信息

### NullMicroscopeFactory

空显微镜工厂（模拟器）：
- 总是可用
- 创建模拟显微镜实例
- 用于离线调试和测试

### MicroscopeWiring

主要的装配类：
- 管理显微镜连接状态
- 提供统一的接口访问显微镜功能
- 管理组件聚合根

## 主要方法

### 连接管理

- `connect()`: 连接到显微镜
- `disconnect()`: 断开显微镜连接
- `is_connected()`: 检查连接状态

### 状态管理

- `get_snapshot()`: 获取显微镜状态快照
- `get_info()`: 获取显微镜信息

### 参数和命令

- `set_component_params()`: 设置组件参数
- `execute_command()`: 执行组件命令

## 错误处理

模块定义了以下异常类：

- `MicroscopeFactoryError`: 显微镜工厂错误
- `MicroscopeConnectionError`: 显微镜连接错误

所有操作都包含适当的错误处理和日志记录。

## 日志配置

模块使用Python标准logging模块，可以通过以下方式配置日志级别：

```python
import logging
logging.getLogger('wiring').setLevel(logging.DEBUG)
```

## 测试

运行测试文件来验证模块功能：

```bash
python test_wiring.py
```

## 扩展性

要添加新的显微镜类型：

1. 继承`MicroscopeFactory`类
2. 实现所有抽象方法
3. 在`MicroscopeWiring._create_factory()`中添加新的模式处理
4. 更新`get_available_modes()`函数

## 注意事项

1. **本地模式**: 需要安装temscript模块并确保显微镜硬件可用
2. **远程模式**: 目前未完全实现，需要进一步开发
3. **空模式**: 模拟器功能需要实现NullMicroscope类
4. **连接管理**: 始终在完成后调用`disconnect()`来清理资源

## 依赖关系

- `domain.py`: 领域模型和接口定义
- `ports_temscript.py`: temscript硬件驱动实现
- `temscript`: 第三方temscript模块（本地模式需要）

## 版本信息

- 创建日期: 2025-08-10
- 版本: 1.0.0
- 状态: 基础功能完成，远程模式和模拟器待实现
