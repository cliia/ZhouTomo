# ZhouTomo

ZhouTomo 是一个面向电子显微镜自动控制与断层倾转序列采集的桌面应用。项目采用 **Client / Server / Protocol** 三项目单仓库结构：Client 负责界面和实验流程，Server 负责电镜状态、硬件操作与服务接口，Protocol 负责双方共享的数据模型与 API 契约。

> 当前代码仍处于架构重构阶段。无真实电镜时，推荐使用 `null` 模式进行开发和回归测试；真实 `temscript` 驱动暂不进行大规模行为重构。

## 仓库结构

```text
ZhouTomo/
├── client/      # PyQt 桌面客户端、实验流程、图像处理
├── server/      # FastAPI 电镜控制服务、状态、驱动与硬件接入
├── protocol/    # Client / Server 共享的数据模型与协议
├── tests/       # 跨项目黑盒集成测试
├── docs/        # 当前有效文档
└── scripts/     # 独立辅助脚本
```

三个 Python 项目独立使用 `uv` 管理环境，仓库根目录**不是** uv workspace，也不应创建一个覆盖全部项目的共享 `.venv`。

依赖方向：

```text
Client ───────► Protocol ◄─────── Server
  │                                  │
  └─ UI / Workflow / Processing      └─ API / Service / Driver
```

核心原则：

> **Client 决定要执行什么实验流程；Server 决定硬件操作是否允许，以及如何安全执行。**

## 环境要求

- Windows
- Python `>=3.10,<3.11`，仓库 `.python-version` 当前为 `3.10.17`
- [uv](https://docs.astral.sh/uv/)
- 真实电镜 Server 额外需要 `temscript` 和对应显微镜运行环境

## 快速开始

### 1. 启动 Null Server

```powershell
cd server
uv sync --extra dev
uv run zhoutomo-server --mode null
```

默认监听：

```text
http://127.0.0.1:9000   # 本机访问
http://<server-ip>:9000 # 局域网访问，默认绑定 0.0.0.0
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9000/health
```

### 2. 启动 Client

另开一个终端：

```powershell
cd client
uv sync --extra dev
uv run zhoutomo-client
```

Client 与 Server 是两个独立进程。GUI 启动后，通过连接界面连接 Server；本地 Null Server 推荐使用：

```text
http://127.0.0.1:9000
```

### 3. 真实电镜 Server

仅在真实电镜控制电脑上安装硬件依赖：

```powershell
cd server
uv sync --extra hardware
uv run zhoutomo-server --mode local
```

`local` 模式依赖 `temscript`，没有真实运行环境时请使用 `null`。`remote` 模式目前尚未实现。

## 测试

分别运行各项目测试：

```powershell
cd protocol
uv sync --extra dev
uv run pytest tests
```

```powershell
cd server
uv sync --extra dev
uv run pytest tests
```

```powershell
cd client
uv sync --extra dev
uv run pytest tests
```

GitHub Actions 还会启动真实的 `zhoutomo-server --mode null` 进程，并使用 Client 的 `AgentClient` 通过 `localhost:9000` 运行黑盒联调测试。

## 文档

完整文档入口见 [`docs/README.md`](docs/README.md)：

- [`docs/architecture.md`](docs/architecture.md)：总体架构、职责边界与依赖规则
- [`docs/development.md`](docs/development.md)：开发环境、常用命令与贡献流程
- [`docs/server.md`](docs/server.md)：Server 模式、配置与目录说明
- [`docs/client.md`](docs/client.md)：Client、GUI、Workflow 与 AgentClient
- [`docs/protocol.md`](docs/protocol.md)：共享协议模型与设计约束
- [`docs/api.md`](docs/api.md)：当前 HTTP / WebSocket API
- [`docs/testing.md`](docs/testing.md)：测试体系、Null 模式与 CI
- [`docs/refactoring.md`](docs/refactoring.md)：重构状态、已完成工作与后续计划

历史实现说明统一放在 `docs/legacy/`。这些文件仅用于追溯旧代码，不作为当前目录结构、API 或开发规范的依据。
