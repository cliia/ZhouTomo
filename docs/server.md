# Server 说明

## 1. 作用

`zhoutomo-server` 是 ZhouTomo 的电镜控制服务。它运行在能够访问显微镜控制环境的 Windows 电脑上，并向 Client 提供 HTTP / WebSocket 接口。

Server 是硬件状态的权威端，负责：

- 连接显微镜；
- 提供当前状态 snapshot；
- 读写 component 参数；
- 执行硬件 command；
- acquisition；
- 后续 safety / interlock；
- 封装 temscript 等厂商 SDK。

Client 不应绕过 Server 直接调用真实电镜 SDK。

## 2. 安装

开发 / Null 模式：

```powershell
cd server
uv sync --extra dev
```

真实硬件：

```powershell
uv sync --extra hardware
```

`hardware` extra 当前包含：

```text
temscript>=1.0.0
```

## 3. 启动

### Null 模式

```powershell
uv run zhoutomo-server --mode null
```

推荐用于日常开发、CI 和无真机环境。

### Local 模式

```powershell
uv run zhoutomo-server --mode local
```

要求真实 `temscript` 环境可用，并能够通过 `temscript.GetInstrument()` 访问仪器。

### Remote 模式

CLI 中保留了：

```text
--mode remote
```

但当前 `RemoteTemscriptFactory` 尚未实现，`get_available_modes()` 也将 remote 标记为不可用。因此 **remote 目前不是可用运行模式**。

## 4. 默认网络配置

代码默认：

```text
host = 0.0.0.0
port = 9000
```

其中 `0.0.0.0` 表示监听所有网卡。只在本机调试时可以：

```powershell
uv run zhoutomo-server --mode null --host 127.0.0.1 --port 9000
```

## 5. 配置优先级

```text
CLI > 环境变量 > 代码默认值
```

| 参数 | CLI | 环境变量 | 默认 |
|---|---|---|---|
| mode | `--mode` | `AGENT_MODE` | `local` |
| server URL | `--server_url` | `AGENT_SERVER_URL` | 无 |
| host | `--host` | `AGENT_HOST` | `0.0.0.0` |
| port | `--port` | `AGENT_PORT` | `9000` |
| reload | `--reload` | `AGENT_RELOAD` | `false` |
| log level | `--log-level` | `AGENT_LOG_LEVEL` | `INFO` |

查看运行环境：

```powershell
uv run zhoutomo-server --info
```

## 6. Package 结构

```text
server/src/zhoutomo_server/
├── api/
│   ├── app.py
│   ├── dependencies.py
│   └── routers/
│       ├── system.py
│       ├── microscope.py
│       ├── acquisition.py
│       ├── diagnostics.py
│       └── websocket.py
├── services/
│   ├── microscope.py
│   └── acquisition.py
├── state/
│   └── server.py
├── drivers/
│   ├── temscript.py
│   └── _legacy_temscript.py
├── safety/
├── domain.py
├── wiring.py
└── main.py
```

`server/src/` 根目录不应再出现 `domain.py`、`wiring.py`、`server_fastapi.py` 等顶层兼容模块。

## 7. 启动链

```text
zhoutomo-server
      │
      ▼
zhoutomo_server.main:main
      │
      ▼
AgentConfig
      │
      ▼
MicroscopeWiring
      │
      ├─ local -> temscript driver
      └─ null  -> NullMicroscope
      │
      ▼
ServerState + FastAPI app
      │
      ▼
uvicorn
```

## 8. Wiring

`wiring.py` 是 Server 的 composition root。

它负责根据 mode 创建 factory：

```text
local  -> LocalTemscriptFactory
null   -> NullMicroscopeFactory
remote -> RemoteTemscriptFactory（未实现）
```

Wiring 不负责 GUI，也不应实现高层实验 workflow。

## 9. API / Service 分层

Router 只做 transport 层工作：

- request 解析；
- FastAPI dependency；
- HTTP status；
- response。

Service 负责操作协调。

例如：

```text
PATCH /components/stage/params
          │
          ▼
microscope router
          │
          ▼
MicroscopeService
          │
          ▼
MicroscopeAggregate
          │
          ▼
Driver
```

不要把 temscript property 访问直接写回 router。

## 10. Driver 状态

当前：

```text
drivers/temscript.py
```

是正式入口；原大型 `ports_temscript.py` 实现被原样保存在：

```text
drivers/_legacy_temscript.py
```

这是有意的过渡结构。

原因：目前缺少真实电镜回归条件。贸然把驱动拆成 stage / camera / optics 等模块，可能在 CI 全绿的情况下引入真实硬件行为变化。

真机恢复前，优先改 API / service / Null / package，不深拆 temscript 实现。

## 11. 日志

Server 当前会输出 stdout 日志，并在工作目录写：

```text
agent.log
```

`.gitignore` 会忽略 `*.log`，日志文件不应提交到仓库。

## 12. 测试

```powershell
cd server
uv run pytest tests
```

Server 测试默认不需要真实硬件。

CI 还会运行：

```python
import zhoutomo_server
from zhoutomo_server.api import create_app
create_app()
```

以及跨项目的 Client + Null Server 黑盒测试。
