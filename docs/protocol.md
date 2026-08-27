# Protocol 说明

## 1. 作用

`zhoutomo-protocol` 是 ZhouTomo Client 与 Server 共享的协议 package。

它不负责网络传输本身，也不负责 GUI 或硬件控制，而是定义：

- 双方都能理解的数据模型；
- API request / response schema；
- 事件模型；
- 错误码；
- state / params 序列化规则。

可以把它理解为：

> **Client 和 Server 之间的共享语言。**

## 2. 依赖规则

Protocol 应保持平台无关和轻量。

允许依赖：

- Python 标准库；
- Pydantic；
- 与协议建模直接相关的轻量依赖。

不应依赖：

- PyQt5；
- qasync；
- FastAPI；
- uvicorn；
- aiohttp；
- temscript；
- 厂商 SDK；
- `zhoutomo_client`；
- `zhoutomo_server`。

依赖方向只能是：

```text
Client  ─────► Protocol ◄───── Server
```

不能反过来。

## 3. Package 结构

```text
protocol/src/zhoutomo_protocol/
├── __init__.py
├── models.py
├── api.py
├── errors.py
├── events.py
├── serialization.py
├── version.py
└── py.typed
```

## 4. Models

共享显微镜状态和参数位于 `models.py`。

当前包括：

- `MicroscopeMode`；
- `VacuumStatus`；
- `CameraStatus`；
- Gun state / params；
- Illumination state / params；
- Projection state / params；
- Stage state / params / position；
- Vacuum state / params；
- Mode state / params；
- Blanker state / params；
- Camera state / params；
- Acquisition state / params；
- AutoNormalize state / params；
- `MicroscopeState`；
- `MicroscopeParams`。

### 单位

共享模型中的单位必须明确并保持稳定。

例如 `StagePosition` 当前约定：

```text
x / y / z -> metre
alpha / beta -> radian
```

UI 可以显示 µm、nm 或 degree，但跨 Client / Server 的协议层不要因为显示需求而随意改变基本单位。

## 5. API 模型

`api.py` 定义双方共用的 API payload，例如：

- `HealthResponse`；
- `ErrorResponse`；
- `ComponentParamsRequest`；
- `CommandRequest`；
- `CommandResponse`；
- `FrameData`。

如果 request / response 同时被 Client 与 Server 使用，应优先放到这里，而不是在 FastAPI router 和 AgentClient 各自维护一份重复定义。

## 6. 错误码

共享错误类型位于 `errors.py`。

当前 `ErrorCode` 包括：

```text
invalid_argument
device_busy
hardware_error
not_connected
timeout
internal_error
```

错误码用于跨进程稳定表达错误类别；具体日志文本可以更详细，但 Client 不应依赖某段自然语言错误消息做业务判断。

## 7. Events

`events.py` 定义可序列化事件，例如：

- `Event`；
- `FrameEvent`。

未来如果 WebSocket 事件类型增加，优先扩展 Protocol，而不是只在 Client 或 Server 私下约定 JSON 字段。

## 8. Serialization

`serialization.py` 负责共享模型到可传输字典的转换，例如：

```python
state_to_dict(...)
params_to_dict(...)
create_default_state()
create_default_params()
```

Client 和 Server 应使用相同序列化规则，避免字段名或嵌套结构漂移。

## 9. `__init__.py` 公共 API

推荐从 package 顶层导入稳定的共享对象：

```python
from zhoutomo_protocol import AcquisitionParams
from zhoutomo_protocol import MicroscopeState
from zhoutomo_protocol import params_to_dict
```

新增公共模型时，应确认顶层 export 是否需要同步更新。

## 10. 什么应该放入 Protocol

应该：

- 跨 Client / Server 传输的状态；
- 跨进程 command 参数；
- 共享 API request / response；
- 共享错误码；
- 共享事件 schema。

不应该：

- MainWindow 的 UI model；
- Autofocus 内部临时优化变量；
- FastAPI dependency；
- aiohttp session；
- temscript instrument object；
- NumPy 大型内部计算对象，除非明确设计了传输格式。

## 11. 修改 Protocol 的注意事项

Protocol 改动通常具有更大的兼容影响。

修改前应考虑：

1. 旧 Client 是否还能读取新 Server response；
2. Server 是否能接受旧 Client payload；
3. 是否需要默认值以保持兼容；
4. 单位是否改变；
5. 字段重命名是否会破坏序列化；
6. Integration test 是否覆盖变化。

## 12. 测试

```powershell
cd protocol
uv sync --extra dev
uv run pytest tests
```

Protocol 修改完成后，还应运行 Server、Client 和跨项目集成测试。
