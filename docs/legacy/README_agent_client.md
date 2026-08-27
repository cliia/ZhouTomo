# AgentClient - 远程显微镜代理客户端

## 概述

`AgentClient` 是 ZhouTomo 项目的远程客户端 SDK，用于与本地电脑的显微镜代理服务器通信。它提供了完整的 HTTP API 和 WebSocket 接口封装，支持显微镜状态获取、参数设置、命令执行和实时图像流订阅等功能。

## 主要特性

- **完整的 HTTP API 支持**：状态获取、参数设置、命令执行
- **WebSocket 实时通信**：图像帧流订阅、心跳检测
- **异步编程支持**：基于 `asyncio` 的异步接口
- **错误处理**：完善的异常处理和重试机制
- **连接管理**：自动连接管理和资源清理
- **类型提示**：完整的 Python 类型注解

## 安装依赖

```bash
pip install aiohttp websockets
```

## 快速开始

### 基本使用

```python
import asyncio
from agent_client import AgentClient

async def main():
    # 创建客户端实例
    client = AgentClient("http://localhost:8000")
    
    try:
        # 连接服务器
        await client.connect()
        
        # 获取服务器健康状态
        health = await client.get_health()
        print(f"服务器状态: {health['status']}")
        
        # 获取显微镜状态
        state = await client.get_state()
        print(f"显微镜状态: {state}")
        
    finally:
        # 断开连接
        await client.disconnect()

# 运行
asyncio.run(main())
```

### 使用异步上下文管理器

```python
async def main():
    async with AgentClient("http://localhost:8000") as client:
        # 自动连接和断开
        health = await client.get_health()
        state = await client.get_snapshot()
        print(f"健康状态: {health}, 显微镜状态: {state}")
```

## API 参考

### 构造函数

```python
AgentClient(base_url: str, timeout: float = 30.0, max_retries: int = 3)
```

**参数：**
- `base_url`: 代理服务器基础URL (如: "http://localhost:8000")
- `timeout`: 请求超时时间(秒)，默认30秒
- `max_retries`: 最大重试次数，默认3次

### 系统信息方法

#### `get_health() -> Dict[str, Any]`
获取服务器健康状态

#### `get_version() -> Dict[str, Any]`
获取API版本信息

#### `get_info() -> Dict[str, Any]`
获取系统信息

### 显微镜控制方法

#### `get_snapshot() -> Dict[str, Any]`
获取显微镜完整状态快照

#### `get_component_state(component: str) -> Dict[str, Any]`
获取指定组件的状态

#### `get_params() -> Dict[str, Any]`
获取显微镜参数配置

#### `set_params(component: str, params: Dict[str, Any]) -> Dict[str, Any]`
设置指定组件的参数

#### `execute_command(component: str, command: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`
执行指定组件的命令

### 采集控制方法

#### `start_acquisition() -> Dict[str, Any]`
开始图像采集

#### `stop_acquisition() -> Dict[str, Any]`
停止图像采集

#### `get_acquisition_status() -> Dict[str, Any]`
获取采集状态

### WebSocket 方法

#### `stream_frames(component: str = "camera") -> AsyncGenerator[Dict[str, Any], None]`
订阅图像帧流

#### `send_websocket_ping() -> bool`
发送WebSocket心跳

### 工具方法

#### `is_connected() -> bool`
检查与服务器的连接状态

#### `ping() -> float`
测试连接延迟（毫秒）

#### `get_components() -> Dict[str, Any]`
获取可用组件列表

## 使用示例

### 1. 基本状态监控

```python
async def monitor_microscope():
    async with AgentClient("http://localhost:8000") as client:
        # 获取状态
        state = await client.get_snapshot()
        print(f"显微镜状态: {state}")
        
        # 获取组件列表
        components = await client.get_components()
        print(f"可用组件: {components['components']}")
        
        # 获取相机状态
        camera_state = await client.get_component_state("camera")
        print(f"相机状态: {camera_state}")
```

### 2. 参数设置

```python
async def configure_camera():
    async with AgentClient("http://localhost:8000") as client:
        # 设置相机参数
        camera_params = {
            "exposure_time": 100.0,
            "gain": 1.5,
            "resolution": "1024x1024"
        }
        
        result = await client.set_params("camera", camera_params)
        print(f"参数设置结果: {result}")
```

### 3. 命令执行

```python
async def control_stage():
    async with AgentClient("http://localhost:8000") as client:
        # 移动样品台
        result = await client.execute_command(
            "stage", 
            "move_to", 
            {"x": 100.0, "y": 200.0, "z": 50.0}
        )
        print(f"样品台移动结果: {result}")
```

### 4. 图像流订阅

```python
async def stream_frames():
    async with AgentClient("http://localhost:8000") as client:
        print("开始订阅图像帧流...")
        
        frame_count = 0
        async for frame in client.stream_frames():
            frame_count += 1
            print(f"接收到第 {frame_count} 帧: {frame}")
            
            # 处理帧数据
            process_frame(frame)
            
            # 限制帧数（示例）
            if frame_count >= 100:
                break
```

### 5. 批量操作

```python
async def batch_operations():
    async with AgentClient("http://localhost:8000") as client:
        # 并行执行多个操作
        tasks = [
            client.get_health(),
            client.get_version(),
            client.get_snapshot(),
            client.get_params()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"操作 {i} 失败: {result}")
            else:
                print(f"操作 {i} 成功: {result}")
```

## 错误处理

### 异常类型

- `AgentClientError`: 基础异常类
- `ConnectionError`: 连接错误
- `AuthenticationError`: 认证错误
- `APIError`: API调用错误
- `WebSocketError`: WebSocket错误

### 错误处理示例

```python
async def robust_operation():
    try:
        async with AgentClient("http://localhost:8000") as client:
            # 检查连接
            if not await client.is_connected():
                print("无法连接到服务器")
                return
            
            # 执行操作
            result = await client.get_snapshot()
            print(f"操作成功: {result}")
            
    except ConnectionError as e:
        print(f"连接错误: {e}")
    except APIError as e:
        print(f"API错误: {e}")
    except WebSocketError as e:
        print(f"WebSocket错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")
```

## 配置选项

### 超时设置

```python
# 设置较长的超时时间
client = AgentClient("http://localhost:8000", timeout=60.0)

# 设置较短的重试间隔
client = AgentClient("http://localhost:8000", max_retries=5)
```

### 日志配置

```python
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

# 或者只设置AgentClient的日志
logger = logging.getLogger("agent_client")
logger.setLevel(logging.DEBUG)
```

## 性能优化

### 1. 连接复用

```python
# 重用客户端实例，避免重复连接
client = AgentClient("http://localhost:8000")
await client.connect()

# 执行多个操作
for i in range(100):
    result = await client.get_snapshot()
    # 处理结果...

await client.disconnect()
```

### 2. 批量请求

```python
# 并行执行多个请求
async with AgentClient("http://localhost:8000") as client:
    tasks = [
        client.get_component_state("camera"),
        client.get_component_state("stage"),
        client.get_component_state("gun")
    ]
    
    results = await asyncio.gather(*tasks)
```

### 3. 异步迭代器

```python
# 高效处理图像流
async with AgentClient("http://localhost:8000") as client:
    async for frame in client.stream_frames():
        # 立即处理帧数据，不阻塞
        await process_frame_async(frame)
```

## 测试

### 运行单元测试

```bash
python test_agent_client.py
```

### 测试覆盖率

```bash
# 安装coverage
pip install coverage

# 运行测试并生成覆盖率报告
coverage run test_agent_client.py
coverage report
coverage html
```

## 故障排除

### 常见问题

1. **连接超时**
   - 检查服务器是否运行
   - 验证网络连接
   - 调整超时设置

2. **WebSocket连接失败**
   - 确认WebSocket端点可用
   - 检查防火墙设置
   - 验证URL格式

3. **认证错误**
   - 检查API密钥
   - 验证用户权限
   - 确认认证头设置

### 调试模式

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

# 创建客户端时启用调试
client = AgentClient("http://localhost:8000")
client.debug = True
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进 AgentClient！

## 许可证

本项目采用 MIT 许可证。
