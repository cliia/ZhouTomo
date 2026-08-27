# 重构状态与后续计划

本文档记录 `refactor/uv-monorepo` 分支当前架构状态，避免后续开发继续依据旧目录或旧兼容层做判断。

## 1. 已完成

### Phase 1：三项目单仓库

已经完成：

```text
server/
client/
protocol/
```

三个独立 uv Python 项目。

仓库根目录不再作为 Python 项目使用。

### Phase 2：Protocol 提取

共享模型已经迁入：

```text
zhoutomo_protocol
```

Client / Server 不再各自维护完整重复的 microscope state / params 定义。

### Phase 3：Server API 分层

原大型 FastAPI 模块已经拆分为：

```text
api/
services/
state/
```

路由按 system / microscope / acquisition / diagnostics / websocket 分开。

### Phase 4：Server namespace 正规化

`server/src/` 已经只保留：

```text
zhoutomo_server/
```

旧顶层模块：

```text
domain.py
wiring.py
server_fastapi.py
run_agent.py
ports_temscript.py
```

已经从 `server/src` 根目录移除。

真实 temscript 实现为降低真机回归风险，被原样收进：

```text
zhoutomo_server/drivers/_legacy_temscript.py
```

正式入口为：

```text
zhoutomo_server.drivers.temscript
```

### Phase 5：Client namespace 正规化

`client/src/` 已经只保留：

```text
zhoutomo_client/
```

旧物理顶层目录：

```text
view/
autofocus/
autotilt/
model/
strategy/
src/
```

均已迁入正式 package。

### Phase 5A：移除 Client legacy import alias

临时 `compat.py` 已删除。

Client 内部 import 已统一使用：

```python
from zhoutomo_client...
from zhoutomo_protocol...
```

CI 会阻止旧式：

```python
from view...
from src...
from model...
from agent_client...
from domain...
```

重新进入源码。

### Null 集成测试

当前 CI 已能执行：

```text
真实启动 zhoutomo-server --mode null
             │
             ▼
      localhost:9000
             │
             ▼
      Client AgentClient
             │
             ▼
      黑盒 integration tests
```

因此 package、端口、HTTP 和基本 Client/Server 边界已经有自动化安全网。

## 2. 当前仍存在的技术债

### Client Workflow 与 Qt 耦合

Autofocus / AutoTilt 目前仍有较多实验逻辑直接位于 `QObject` controller 中。

这会导致：

- workflow 难以脱离 GUI 测试；
- 状态管理与 UI signal 混合；
- 后续脚本化运行困难；
- AutoTilt 与 Autofocus 之间耦合偏强。

### Processing legacy

旧算法目前集中在：

```text
zhoutomo_client/processing/legacy/
```

命名、接口和资源依赖尚未系统整理。

### Temscript legacy driver

真实驱动仍集中在：

```text
zhoutomo_server/drivers/_legacy_temscript.py
```

这不是最终理想结构，但在没有真机的条件下暂时保留是有意的风险控制。

### Safety

Server 已预留 `safety/`，但真实硬件 range check / interlock / recovery 还需要在真机环境下系统完善。

## 3. 下一阶段：Phase 5B

下一步优先处理 **Autofocus 的 Qt / Workflow 解耦**。

目标结构：

```text
workflows/autofocus/
├── workflow.py
├── settings.py
├── result.py
├── microscope_api.py
└── qt_controller.py
```

依赖方向：

```text
Qt UI
  │
  ▼
Qt Controller
  │
  ▼
AutofocusWorkflow
  │
  ▼
MicroscopeAPI / AgentClient
```

核心目标是让：

```python
await autofocus_workflow.run(...)
```

可以在没有 MainWindow 的情况下运行和测试。

## 4. Phase 5B 的实施原则

1. 先处理 Autofocus，不同时大改 AutoTilt。
2. 先提取纯数据 `settings/result`。
3. 再提取不依赖 Qt 的 workflow。
4. Qt controller 只负责 signal、UI 生命周期和调用 workflow。
5. 保持现有外部 GUI 行为不变。
6. 增加纯 workflow 单元测试。
7. 保持 Client + Null Server 黑盒测试通过。
8. 不在同一阶段整理 BM3D / processing legacy。

## 5. 后续 Phase 5C

Autofocus 稳定后，再以相同模式处理 AutoTilt：

```text
workflows/autotilt/
├── workflow.py
├── settings.py
├── result.py
└── qt_controller.py
```

需要特别注意：AutoTilt 当前会调用 Autofocus，因此应让它依赖纯 Autofocus workflow 接口，而不是直接构造 Qt AutofocusController。

## 6. 暂缓：Temscript 深度拆分

最终目标可能是：

```text
drivers/temscript/
├── microscope.py
├── stage.py
├── optics.py
├── camera.py
├── acquisition.py
└── errors.py
```

但必须等真实电镜可用后再逐个 component 实施。

原因是 CI 无法验证：

- 真机属性映射；
- SDK 生命周期；
- stage 单位；
- camera 返回值；
- acquisition 时序；
- COM / threading；
- interlock。

因此当前优先级低于 Client workflow 解耦。

## 7. 推荐后续顺序

```text
中文文档完善（当前阶段）
        ↓
Autofocus Qt / Workflow 解耦
        ↓
AutoTilt Qt / Workflow 解耦
        ↓
Processing legacy 逐步整理
        ↓
Null simulator 增强
        ↓
Safety 接口完善
        ↓
真实电镜恢复
        ↓
Temscript driver 分 component 重构
        ↓
真机回归与异常恢复
```

每个阶段都应保持正常 CI 全绿，不把多个独立风险混入一个大 commit。
