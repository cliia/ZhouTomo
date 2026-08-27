# ZhouTomo 架构设计

## 1. 总体目标

ZhouTomo 用于电子显微镜自动控制与断层倾转序列采集。系统采用 Client / Server 分离架构，避免 GUI、图像处理、实验流程与真实硬件 SDK 直接耦合。

核心原则：

> **Client 决定要执行什么实验；Server 决定硬件操作是否允许，以及如何安全执行。**

这意味着实验流程可以在 Client 侧快速演化，而真实电镜状态、硬件生命周期和安全约束由 Server 统一管理。

## 2. 三项目单仓库

```text
ZhouTomo/
├── client/
│   └── src/zhoutomo_client/
├── server/
│   └── src/zhoutomo_server/
└── protocol/
    └── src/zhoutomo_protocol/
```

三个子项目是独立 Python 项目，各自拥有 `pyproject.toml` 和 `.venv`。仓库根目录只负责 Git 协作，不是一个 Python package，也不是 uv workspace。

### 为什么不使用一个共享环境

Client 和 Server 的运行环境并不相同：

- Client 依赖 PyQt、图像处理和 GUI 组件；
- Server 依赖 FastAPI，并可能只在电镜控制电脑上安装 `temscript`；
- Protocol 应保持轻量、跨平台，不依赖任何 GUI 或硬件 SDK。

独立环境可以降低依赖冲突，并确保“只运行 Server”不需要安装 Client 的 GUI 依赖。

## 3. 依赖方向

```text
                 ┌─────────────────────┐
                 │ zhoutomo_protocol   │
                 │ models / API schema │
                 └─────────▲───────────┘
                           │
             ┌─────────────┴─────────────┐
             │                           │
┌────────────┴────────────┐  ┌───────────┴─────────────┐
│ zhoutomo_client         │  │ zhoutomo_server         │
│                         │  │                         │
│ UI                      │  │ API routers             │
│ Workflow                │  │ Services                │
│ Processing              │  │ Domain / State          │
│ API Client              │  │ Safety                  │
└────────────┬────────────┘  │ Drivers                 │
             │ HTTP / WS      └───────────┬─────────────┘
             └────────────────────────────►│
                                          ▼
                                  Microscope SDK
```

禁止形成以下反向依赖：

```text
protocol -> client
protocol -> server
server   -> client
hardware driver -> Qt UI
AgentClient -> Qt UI
```

## 4. Protocol：共享契约

`zhoutomo_protocol` 是 Client 和 Server 的共同语言。

它负责：

- 电镜状态和参数数据模型；
- Client / Server 共用 API request / response 模型；
- 共享错误码和事件模型；
- 状态与参数的序列化。

它不应导入：

- PyQt / qasync；
- FastAPI / uvicorn；
- temscript / COM / 厂商 SDK；
- Client 或 Server 的具体实现。

Protocol 的修改等价于“修改双方契约”，因此需要同时考虑 Client、Server 和集成测试。

## 5. Server：硬件权威端

Server 是真实电镜状态的 source of truth。

主要层次：

```text
HTTP / WebSocket
      │
      ▼
API Router
      │
      ▼
Service
      │
      ▼
Domain / Wiring / State
      │
      ▼
Safety
      │
      ▼
Driver
      │
      ▼
Microscope SDK
```

### API 层

`zhoutomo_server.api` 负责：

- FastAPI app 组装；
- 参数解析；
- HTTP 状态码；
- WebSocket 连接；
- 把请求交给 service。

Router 不应包含复杂实验流程或硬件 SDK 调用。

### Service 层

Service 负责一次 API 操作内部的业务协调，例如：

- 获取完整 snapshot；
- 更新某个 component 参数；
- 执行 command；
- 启动或停止 acquisition。

### Domain / Wiring

`domain.py` 定义抽象的显微镜能力和聚合逻辑。

`wiring.py` 是 composition root，选择：

- `local`：真实 temscript；
- `null`：模拟显微镜；
- `remote`：预留，目前未实现。

### Driver

Driver 封装厂商 SDK。当前真实 temscript 实现仍保留 legacy 内部结构，主要原因是目前缺乏真实电镜回归条件。

在真机测试恢复前，不应仅为了目录美观而大规模改写驱动行为。

## 6. Client：实验与交互端

Client 主要包括：

```text
zhoutomo_client/
├── main.py
├── api/
├── ui/
├── workflows/
├── models/
├── processing/
├── strategies/
├── config/
└── resources/
```

### `main.py`

`main.py` 是桌面程序入口，只负责应用生命周期：

- 创建 `QApplication`；
- 创建 qasync event loop；
- 创建 SplashScreen；
- 创建 MainWindow；
- 启动 GUI。

它不应直接实现 Server API 或实验算法。

### `AgentClient`

`zhoutomo_client.api.AgentClient` 是 Client 到 Server 的 HTTP / WebSocket SDK。

它可以脱离 GUI 独立使用，因此不能依赖 MainWindow、QObject 或其他 UI 对象。

### UI

`zhoutomo_client.ui` 负责 Qt widget、panel、dialog 和用户交互。

UI 可以调用 workflow 或 API 层，但实验算法不应长期写死在 Qt controller 内。

### Workflow

Workflow 表达高层实验意图，例如 Autofocus 和 AutoTilt。

目标结构是：

```text
UI
 │
 ▼
Qt Controller
 │
 ▼
Pure Python Workflow
 │
 ▼
Microscope API / AgentClient
```

这样 Workflow 可以在无 GUI 环境下独立运行和测试。

### Processing

图像处理函数属于 Client，因为这些计算描述“如何分析实验数据”，而不是“硬件是否允许移动”。

## 7. API 边界

Client 不应直接访问 temscript。

正确路径：

```text
Client Workflow
    │
    ▼
AgentClient
    │ HTTP / WebSocket
    ▼
Server API
    │
    ▼
Server Service
    │
    ▼
Microscope Driver
```

这样即使 Client 和 Server 分别运行在不同 Windows 电脑上，实验代码也不需要改变硬件调用方式。

## 8. Null 模式

Null microscope 是当前无真机开发的主要安全网。

它用于验证：

- Server 能正常启动；
- FastAPI 路由工作；
- Protocol 序列化正确；
- Client 的 AgentClient 能连 Server；
- acquisition 请求链可以完成；
- import / package / 环境拆分没有破坏程序。

Null 模式不能证明：

- temscript 属性名正确；
- 真机初始化顺序正确；
- stage / optics / camera 的单位和范围正确；
- 厂商 SDK 异常处理正确；
- 真机 interlock 和恢复流程正确。

因此 Null CI 通过不等于真实硬件回归完成。

## 9. 设计约束

新增功能时优先遵循以下规则：

1. Client 与 Server 的共享数据结构放入 Protocol。
2. Server API 只负责 transport，不直接堆积硬件业务逻辑。
3. 真实硬件状态只由 Server 判定和维护。
4. Client 不复制 Server 的安全约束作为最终依据。
5. Workflow 应尽可能脱离 Qt。
6. 图像处理函数尽可能保持纯函数或显式输入输出。
7. 可选硬件依赖不得导致无硬件环境下 `import zhoutomo_server` 失败。
8. 新目录和 import 统一使用 `zhoutomo_client.*`、`zhoutomo_server.*`、`zhoutomo_protocol.*` 正式命名空间。
9. 不重新引入 `client/src/view`、`server/src/domain.py` 等顶层兼容模块。
10. 改变跨进程行为时必须增加或更新黑盒集成测试。
