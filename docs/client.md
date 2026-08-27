# Client 说明

## 1. 作用

`zhoutomo-client` 是 ZhouTomo 的 Windows 桌面客户端，负责：

- PyQt GUI；
- 用户交互；
- 实验流程编排；
- Autofocus / AutoTilt；
- 图像显示与处理；
- 通过 `AgentClient` 与 Server 通信。

Client 不拥有真实硬件状态，也不应直接调用 temscript。

## 2. 安装与启动

```powershell
cd client
uv sync --extra dev
uv run zhoutomo-client
```

本地开发时，可先启动：

```powershell
cd server
uv run zhoutomo-server --mode null --host 127.0.0.1 --port 9000
```

然后让 Client 连接：

```text
http://127.0.0.1:9000
```

## 3. Package 结构

```text
client/src/zhoutomo_client/
├── api/
│   └── client.py
├── ui/
│   ├── main_window.py
│   ├── splash_screen.py
│   ├── dialogs.py
│   ├── toolbar.py
│   ├── widgets.py
│   └── panels/
├── workflows/
│   ├── autofocus/
│   └── autotilt/
├── models/
├── processing/
│   └── legacy/
├── strategies/
├── config/
├── resources/
└── main.py
```

`client/src/` 根目录只应存在 `zhoutomo_client/` package。

## 4. `main.py` 是什么

`zhoutomo_client/main.py` 是桌面应用入口。

它负责应用生命周期，例如：

```text
创建 QApplication
      │
      ▼
配置 qasync event loop
      │
      ▼
显示 SplashScreen
      │
      ▼
创建 MainWindow
      │
      ▼
进入 Qt 事件循环
```

它不应该实现：

- Server HTTP 请求细节；
- autofocus 算法；
- image processing；
- 真机控制逻辑。

命令：

```powershell
uv run zhoutomo-client
```

最终调用：

```text
zhoutomo_client.main:main
```

## 5. `AgentClient` 是什么

正式位置：

```text
zhoutomo_client/api/client.py
```

推荐 import：

```python
from zhoutomo_client.api import AgentClient
```

`AgentClient` 是 Client 侧的 Server SDK，封装：

- HTTP session；
- Server health / snapshot；
- component state；
- 参数更新；
- command；
- acquisition；
- WebSocket frame stream。

它和 `main.py` 的关系：

```text
main.py
  │
  ▼
GUI / MainWindow
  │
  ▼
Workflow / AgentClientManager
  │
  ▼
AgentClient
  │ HTTP / WebSocket
  ▼
Server
```

`AgentClient` 本身不需要 GUI，可以单独使用：

```python
from zhoutomo_client.api import AgentClient

async with AgentClient("http://127.0.0.1:9000") as client:
    snapshot = await client.get_snapshot()
```

因此不要让 `AgentClient` import MainWindow、QObject 或其他 Qt 对象。

## 6. UI 层

`zhoutomo_client.ui` 负责：

- MainWindow；
- panel；
- toolbar；
- dialog；
- widget；
- 用户输入；
- 状态显示。

UI 应尽量把“执行什么操作”交给 workflow / API，而不是直接堆积实验算法。

## 7. Workflow 层

当前主要 workflow：

```text
workflows/autofocus/
workflows/autotilt/
```

现阶段仍有不少 Qt controller 与实验流程混合在一起。

下一阶段目标是：

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
MicroscopeAPI / AgentClient
```

例如未来应能在没有 MainWindow 的情况下：

```python
result = await workflow.run(...)
```

这样可以：

- 独立单元测试；
- 复用 autofocus；
- 降低 UI 与实验逻辑耦合；
- 后续支持脚本化控制。

## 8. Processing

`zhoutomo_client.processing` 存放图像处理相关功能。

当前仍存在：

```text
processing/legacy/
```

其中包含从旧 `src/` 目录迁入的算法，以及 BM3D 使用的 `.mat` 数据文件。

正式代码已经不再通过：

```python
from src...
```

访问它们，而是使用：

```python
from zhoutomo_client.processing.legacy...
```

后续可以逐个整理这些 legacy 算法，但应和 Qt/workflow 解耦分开进行，避免一次修改过多行为。

## 9. Models 与 Protocol 的区别

Client-local model 放在：

```text
zhoutomo_client.models
```

例如仅用于 UI / workflow 的 target 信息。

如果一个数据类型必须跨 Client / Server 传输，则应放入：

```text
zhoutomo_protocol
```

判断规则：

```text
仅 Client 使用       -> zhoutomo_client.models
Client + Server 共用 -> zhoutomo_protocol
```

## 10. 资源

UI 静态资源位于：

```text
zhoutomo_client/resources/
├── background/
└── icons/
```

Client 测试会检查关键资源是否被 package 正确包含。

## 11. PyQt 版本

当前 Windows Client 固定：

```text
PyQt5==5.15.11
PyQt5-Qt5==5.15.2
```

原因是较新的 `PyQt5-Qt5` 版本在 Windows wheel 可用性上曾导致 CI 安装失败。

修改该 pin 前必须在 Windows CI 验证。

## 12. PyInstaller

仓库保留：

```text
client/ZhouTomo.spec
client/packaging/pyinstaller_entry.py
```

用于桌面程序打包。

迁移 package 或资源路径时，需要同时检查：

- `ZhouTomo.spec`；
- icons / background；
- processing `.mat`；
- entry point。

## 13. Import 规范

使用：

```python
from zhoutomo_client...
from zhoutomo_protocol...
```

禁止重新引入：

```python
from view...
from model...
from src...
from autofocus...
from autotilt...
from agent_client...
from domain...
```

CI 已有静态测试保护这一点。

## 14. 测试

```powershell
cd client
uv run pytest tests
```

Client CI 会验证 package、正式 import、GUI/workflow smoke import 和资源文件。

仓库级集成测试还会用 `AgentClient` 连接实际启动的 Null Server。
