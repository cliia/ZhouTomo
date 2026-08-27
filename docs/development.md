# 开发指南

## 1. 开发环境

当前项目以 Windows 为主要运行平台。

推荐环境：

- Windows 10 / 11；
- Python `>=3.10,<3.11`；
- 仓库 `.python-version` 当前为 `3.10.17`；
- `uv`；
- Git。

真实电镜 Server 还需要：

- `temscript`；
- 厂商显微镜控制环境；
- 能够正常连接真实 instrument 的 Windows 电脑。

## 2. 不要在根目录创建统一 Python 环境

仓库是 Git monorepo，但不是 uv workspace。

```text
ZhouTomo/
├── client/.venv
├── server/.venv
└── protocol/.venv
```

实际 `.venv` 由 `uv sync` 在对应子项目中创建，并被 Git 忽略。

这样可以避免 Client 的 PyQt / OpenCV 等依赖污染 Server 环境，也避免 Server 的硬件依赖进入 Client。

## 3. 安装开发环境

### Protocol

```powershell
cd protocol
uv sync --extra dev
```

### Server

```powershell
cd server
uv sync --extra dev
```

只在需要真实硬件时安装：

```powershell
uv sync --extra hardware
```

### Client

```powershell
cd client
uv sync --extra dev
```

Client 当前固定：

```text
PyQt5==5.15.11
PyQt5-Qt5==5.15.2
```

这是为了保证 Windows 有可安装的 Qt runtime wheel，不要在未验证 Windows CI 的情况下随意移除该 pin。

## 4. 常用启动命令

### Null Server

```powershell
cd server
uv run zhoutomo-server --mode null
```

默认：

```text
host = 0.0.0.0
port = 9000
```

如果只希望本机访问：

```powershell
uv run zhoutomo-server --mode null --host 127.0.0.1 --port 9000
```

### Client

```powershell
cd client
uv run zhoutomo-client
```

本地开发时，GUI 推荐连接：

```text
http://127.0.0.1:9000
```

### 真实电镜

```powershell
cd server
uv sync --extra hardware
uv run zhoutomo-server --mode local
```

没有 `temscript` 或真实显微镜运行环境时，`local` 模式可能无法启动，这是预期行为。

## 5. Server 配置优先级

Server 配置优先级固定为：

```text
命令行参数
    ↓
环境变量
    ↓
代码默认值
```

主要配置：

| 配置 | CLI | 环境变量 | 默认值 |
|---|---|---|---|
| 模式 | `--mode` | `AGENT_MODE` | `local` |
| host | `--host` | `AGENT_HOST` | `0.0.0.0` |
| port | `--port` | `AGENT_PORT` | `9000` |
| 日志级别 | `--log-level` | `AGENT_LOG_LEVEL` | `INFO` |
| reload | `--reload` / `--no-reload` | `AGENT_RELOAD` | `false` |
| remote URL | `--server_url` | `AGENT_SERVER_URL` | 无 |

示例：

```powershell
$env:AGENT_MODE = "null"
$env:AGENT_PORT = "9100"
uv run zhoutomo-server
```

如果同时指定：

```powershell
uv run zhoutomo-server --port 9000
```

则 CLI 的 `9000` 覆盖环境变量中的 `9100`。

查看 Server 环境信息：

```powershell
uv run zhoutomo-server --info
```

## 6. 推荐开发流程

每次修改尽量只跨越一个清晰边界：

```text
修改
 ↓
对应项目 pytest
 ↓
package import smoke test
 ↓
Null Client/Server 集成测试
 ↓
GitHub Actions
```

如果修改真实硬件 driver，则还需要增加真机回归步骤，不能只依据 Null CI 判断完成。

## 7. Import 规则

正式 import 使用：

```python
from zhoutomo_client...
from zhoutomo_server...
from zhoutomo_protocol...
```

不要重新使用旧式顶层 import：

```python
from view...
from src...
from model...
from autofocus...
from agent_client...
from domain...
```

Client CI 已有测试阻止这些旧 import 重新进入代码。

## 8. Protocol 修改规则

如果 Client 和 Server 都需要某个数据类型，应优先放入 `zhoutomo_protocol`，而不是各定义一份。

修改 Protocol 后至少运行：

```powershell
cd protocol
uv run pytest tests

cd ..\server
uv run pytest tests

cd ..\client
uv run pytest tests
```

原因是 Protocol 本质上是跨进程接口契约。

## 9. API 修改规则

改变 URL、request schema 或 response schema 时：

1. 优先更新 Protocol 中共享模型；
2. 更新 Server router / service；
3. 更新 `AgentClient`；
4. 更新 `docs/api.md`；
5. 增加或修改 `tests/integration`；
6. 确认 Null 黑盒联调通过。

不要只修改 Server 而依赖 Client 在运行时才发现协议不一致。

## 10. 真实硬件代码修改规则

在没有真机条件时：

可以做：

- package / import 整理；
- 注释和类型提示；
- 不改变行为的 facade；
- 与硬件无关的 API / service 分层；
- Null simulator 和测试增强。

暂缓做：

- temscript 属性映射重写；
- stage / optics / camera 单位转换重写；
- acquisition 时序重构；
- 硬件生命周期和异常恢复的大幅调整；
- safety / interlock 最终行为变化。

这些工作应在真实电镜可用时逐项验证。

## 11. Ruff 与测试

开发依赖已经包含 Ruff。可以手动执行：

```powershell
uv run ruff check src tests
```

当前 CI 的核心门槛仍是 pytest 和 import / integration smoke test。新增 lint 规则时应避免一次性把大量历史风格问题与功能重构混在同一个 commit。
