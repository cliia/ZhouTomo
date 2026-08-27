# 测试与 CI

## 1. 测试目标

ZhouTomo 的测试体系要同时回答四个问题：

1. 各 package 是否能独立安装和 import；
2. Protocol / Server / Client 的纯软件逻辑是否正确；
3. Client 与 Server 的真实进程通信是否仍兼容；
4. 真实电镜行为是否正确。

其中前 3 项可以自动化，第 4 项需要真实硬件回归。

## 2. 测试分层

```text
单元 / package 测试
        │
        ▼
Server Null API 测试
        │
        ▼
Client UI / import / resource smoke test
        │
        ▼
Client + Null Server 黑盒集成测试
        │
        ▼
真实电镜回归测试（人工 / 专用环境）
```

## 3. Protocol 测试

```powershell
cd protocol
uv sync --extra dev
uv run pytest tests
```

主要验证：

- 共享模型可以创建；
- state / params 序列化正确；
- package 可以独立 import。

Protocol 不依赖 Client、Server、Qt 或 temscript。

## 4. Server 测试

```powershell
cd server
uv sync --extra dev
uv run pytest tests
```

当前重点包括：

- domain 行为；
- package import；
- `src` layout；
- Null microscope 下的 FastAPI API；
- snapshot、component state、参数更新、command、acquisition；
- WebSocket 基础行为。

Server CI 不安装 `hardware` extra，因此不要求 GitHub runner 存在 temscript。

## 5. Client 测试

```powershell
cd client
uv sync --extra dev
uv run pytest tests
```

当前重点包括：

- `zhoutomo_protocol` import；
- `client/src` 只包含 `zhoutomo_client` 正式 package；
- 禁止旧式 `view/src/model/agent_client/domain` import；
- MainWindow / SplashScreen / Autofocus / AutoTilt 可以从正式 namespace import；
- UI 图标和启动背景资源存在；
- legacy processing namespace 仍可加载。

这些测试的目的不是验证完整 GUI 交互，而是尽早发现 package 迁移、资源移动和 import 重构造成的问题。

## 6. Client + Null Server 黑盒测试

仓库根目录的：

```text
tests/integration/
```

用于验证真实进程边界。

GitHub Actions 会执行：

```text
启动 server/.venv 中的 zhoutomo-server
          │
          │ --mode null --host 127.0.0.1 --port 9000
          ▼
等待 GET /health == healthy
          │
          ▼
client/.venv 中运行 integration pytest
          │
          ▼
AgentClient -> HTTP -> Server -> NullMicroscope
```

这比 FastAPI TestClient 更接近实际部署，因为：

- Server 是独立进程；
- Client 使用自己的 uv 环境；
- 通信经过真实 TCP/HTTP；
- 使用正式 `AgentClient`；
- 可以发现端口、URL、序列化和跨项目安装问题。

默认测试地址：

```text
http://127.0.0.1:9000
```

可通过：

```text
ZHOUTOMO_TEST_SERVER_URL
```

覆盖集成测试使用的 Server URL。

## 7. GitHub Actions

当前 `.github/workflows/ci.yml` 有四个 Windows job：

| Job | 作用 |
|---|---|
| `Protocol` | 安装、pytest、import `zhoutomo_protocol` |
| `Server (no hardware)` | 安装、pytest、创建 FastAPI app |
| `Client` | 安装、pytest、import Client / Protocol |
| `Client + Null Server` | 独立启动 Null Server，并用 Client 黑盒联调 |

CI 在：

- push；
- pull request；
- `workflow_dispatch`

时运行。

## 8. Null 模式能证明什么

Null 测试可以高置信度覆盖：

- package 结构；
- import；
- uv 子项目隔离；
- Server app 组装；
- HTTP / WebSocket 基础接口；
- Client SDK 与 Server 协议兼容；
- 高层 acquisition 请求链；
- 部分 workflow 的纯软件行为。

## 9. Null 模式不能证明什么

Null 模式不能替代真机验证：

- `temscript.GetInstrument()` 与真实环境兼容性；
- stage 的位置、角度单位；
- optics / defocus / beam 等真实属性映射；
- camera acquisition 的返回数据格式与时序；
- 多线程或 COM 生命周期；
- 真机异常恢复；
- 硬件 interlock；
- 真实移动范围和安全边界。

因此在没有真机时，不应把“大规模 temscript driver 重构 + Null CI 通过”视为完成。

## 10. 真机恢复后的回归建议

真实电镜可用后，建议按风险从低到高验证：

1. Server `local` 模式启动和连接；
2. 只读 snapshot；
3. 只读各 component state；
4. 低风险 optics 参数读写；
5. 小幅 stage 移动；
6. camera 单帧 acquisition；
7. 多帧 acquisition；
8. Autofocus；
9. AutoTilt；
10. 故障 / timeout / disconnect 恢复。

每次 driver 重构只改一个 component，并保留改动前后的真机对照结果。
