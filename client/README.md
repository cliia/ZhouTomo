# ZhouTomo Client

ZhouTomo 桌面客户端，负责 PyQt GUI、实验流程、图像处理以及通过 `AgentClient` 与 Server 通信。

## 安装

```powershell
uv sync --extra dev
```

## 启动

```powershell
uv run zhoutomo-client
```

本地开发建议先启动 Null Server：

```powershell
cd ..\server
uv run zhoutomo-server --mode null --host 127.0.0.1 --port 9000
```

Client 连接地址：

```text
http://127.0.0.1:9000
```

## 目录

```text
src/zhoutomo_client/
├── api/          # AgentClient，HTTP / WebSocket SDK
├── ui/           # PyQt UI
├── workflows/    # Autofocus / AutoTilt
├── models/       # Client-local 数据模型
├── processing/   # 图像处理
├── strategies/   # 历史策略代码
├── config/
├── resources/
└── main.py       # GUI 入口
```

## 测试

```powershell
uv run pytest tests
```

更完整说明见 [`../docs/client.md`](../docs/client.md) 和 [`../docs/testing.md`](../docs/testing.md)。
