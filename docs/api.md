# API 说明

本文档记录当前 `zhoutomo-server` 对外暴露的主要 HTTP / WebSocket 接口。接口仍在重构阶段，修改 API 时应同步更新本文件和跨项目集成测试。

默认本地地址：

```text
http://127.0.0.1:9000
```

## 1. System

### `GET /health`

用于健康检查。

返回示例：

```json
{
  "status": "healthy",
  "timestamp": "2026-08-27T12:00:00",
  "version": "...",
  "microscope_connected": true,
  "uptime": 10.5
}
```

Null Server 启动后，CI 会轮询该接口，直到 `status == "healthy"`。

### `GET /version`

返回 Server 版本和时间戳。

### `GET /info`

返回 Server 名称、版本、uptime 和电镜连接状态等信息。

## 2. Microscope

### `GET /snapshot`

返回完整显微镜状态快照。

这是 Client 获取 Server 当前权威状态的主要接口之一。

### `GET /components`

返回当前可用 component 列表。

示例结构：

```json
{
  "components": ["stage", "camera", "acquisition"]
}
```

实际列表以 Server 当前实现为准。

### `GET /components/{component}/state`

读取指定 component 的当前状态。

例如：

```text
GET /components/stage/state
GET /components/acquisition/state
```

不存在的 component 返回 `404`。

### `GET /params`

返回 Server 当前参数 schema / 参数描述。

### `PATCH /components/{component}/params`

修改某个 component 的参数。

Request：

```json
{
  "params": {
    "key": "value"
  }
}
```

共享 request 模型为：

```python
zhoutomo_protocol.ComponentParamsRequest
```

Server 会把参数更新交给 `MicroscopeService` 和 domain/driver 层处理。

### `POST /components/{component}/commands/{command}`

执行 component command。

Request：

```json
{
  "parameters": {}
}
```

Response 使用：

```python
zhoutomo_protocol.CommandResponse
```

Client 不应自行拼接大量 command URL，优先通过 `AgentClient` 的对应方法访问。

## 3. Acquisition

Acquisition router 使用 `/acquisition` prefix。

### `POST /acquisition/start`

执行一次 acquisition。

当前 Server 会通过 `AcquisitionService` 调用 wiring / microscope，并返回采集结果。

### `POST /acquisition/stop`

停止当前 acquisition。

### `GET /acquisition/status`

返回 acquisition 是否 active 以及时间戳。

示例：

```json
{
  "active": false,
  "timestamp": "2026-08-27T12:00:00"
}
```

## 4. WebSocket

Server 还提供 WebSocket 接口，用于帧数据 / 事件通信。

Client 的正式访问入口是：

```python
from zhoutomo_client.api import AgentClient
```

`AgentClient` 会根据 HTTP URL 自动构造 WebSocket URL，例如：

```text
http://127.0.0.1:9000
        ↓
ws://127.0.0.1:9000/ws/frames
```

如果 Server 使用 HTTPS，则 Client 对应使用 `wss://`。

## 5. AgentClient

推荐业务代码通过 `AgentClient` 访问 Server，而不是直接使用 `aiohttp`。

示例：

```python
import asyncio

from zhoutomo_client.api import AgentClient


async def main():
    async with AgentClient("http://127.0.0.1:9000") as client:
        health = await client.get_health()
        snapshot = await client.get_snapshot()
        print(health)
        print(snapshot)


asyncio.run(main())
```

`AgentClient` 的价值在于统一处理：

- base URL；
- aiohttp session 生命周期；
- timeout；
- retry；
- API error；
- WebSocket URL；
- Client / Server 协议调用。

## 6. API 设计规则

新增或修改 API 时遵循：

```text
Protocol schema
      ↓
Server router
      ↓
Server service
      ↓
AgentClient
      ↓
Integration test
      ↓
本 API 文档
```

### Router 不应做什么

Router 不应该：

- 直接 import temscript；
- 写复杂 Autofocus / AutoTilt 流程；
- 复制一套和 Protocol 不同的共享 schema；
- 把真实硬件安全规则只放在 HTTP handler 中。

### 错误处理

当前常见 HTTP 行为包括：

- `400`：参数或操作失败；
- `404`：component 不存在；
- `500`：Server 内部执行异常；
- `503`：例如 acquisition 时显微镜不可用。

随着共享 `ErrorCode` 使用范围扩大，应逐步减少 Client 根据自然语言错误字符串判断逻辑的情况。

## 7. 兼容性

API 是 Client / Server 的跨进程边界。

如果修改：

- URL；
- HTTP method；
- JSON 字段；
- 字段单位；
- WebSocket message schema；

必须同步更新 Client 和集成测试。

单独保证 Server pytest 通过并不足以证明 API 没有被破坏。
