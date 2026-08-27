# ZhouTomo Protocol

ZhouTomo Client 与 Server 共享的协议 package，负责数据模型、API schema、事件、错误码和序列化规则。

## 安装

```powershell
uv sync --extra dev
```

## 测试

```powershell
uv run pytest tests
```

## 设计约束

Protocol 必须保持轻量和平台无关，不应依赖：

- PyQt / qasync；
- FastAPI / uvicorn；
- aiohttp；
- temscript / 厂商 SDK；
- `zhoutomo_client`；
- `zhoutomo_server`。

依赖方向固定为：

```text
Client ───► Protocol ◄─── Server
```

跨 Client / Server 传输的数据类型应优先定义在这里。

更完整说明见 [`../docs/protocol.md`](../docs/protocol.md) 和 [`../docs/architecture.md`](../docs/architecture.md)。
