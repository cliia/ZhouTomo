# ZhouTomo Server

ZhouTomo 电镜控制服务，负责显微镜连接、状态、参数、command、acquisition，以及后续 safety / interlock 和真实硬件驱动。

## Null 开发模式

```powershell
uv sync --extra dev
uv run zhoutomo-server --mode null
```

默认监听：

```text
0.0.0.0:9000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9000/health
```

## 真实硬件

仅在电镜控制电脑上：

```powershell
uv sync --extra hardware
uv run zhoutomo-server --mode local
```

`local` 模式依赖 `temscript`。`remote` 模式当前尚未实现。

## 目录

```text
src/zhoutomo_server/
├── api/          # FastAPI app 和 routers
├── services/     # API 业务协调
├── state/        # Server runtime state
├── drivers/      # Null / temscript 驱动入口
├── safety/       # 安全策略预留
├── domain.py
├── wiring.py
└── main.py       # CLI / Server 入口
```

## 测试

```powershell
uv run pytest tests
```

普通开发测试不需要安装 `temscript`。

更完整说明见 [`../docs/server.md`](../docs/server.md)、[`../docs/api.md`](../docs/api.md) 和 [`../docs/testing.md`](../docs/testing.md)。
