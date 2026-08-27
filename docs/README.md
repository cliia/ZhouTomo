# ZhouTomo 文档

本目录存放 **当前架构下有效的中文文档**。如果文档内容与当前代码冲突，应以代码和测试为准，并同步修正文档。

## 推荐阅读顺序

1. [`../README.md`](../README.md)：项目概览与快速启动
2. [`architecture.md`](architecture.md)：总体架构、依赖方向、职责边界
3. [`development.md`](development.md)：开发环境与日常工作流
4. [`testing.md`](testing.md)：测试分层、Null 模式和 CI
5. 根据修改内容阅读对应子系统文档：
   - [`server.md`](server.md)
   - [`client.md`](client.md)
   - [`protocol.md`](protocol.md)
   - [`api.md`](api.md)
6. [`refactoring.md`](refactoring.md)：当前重构状态和后续边界

## 文档分类

| 文档 | 用途 |
|---|---|
| `architecture.md` | 说明 Client / Server / Protocol 的职责与依赖规则 |
| `development.md` | 安装、运行、配置、开发约定 |
| `server.md` | Server 启动模式、配置优先级、内部结构 |
| `client.md` | GUI、`main.py`、`AgentClient`、Workflow、Processing |
| `protocol.md` | 共享模型、序列化与协议边界 |
| `api.md` | 当前 HTTP / WebSocket 接口 |
| `testing.md` | 单元测试、集成测试、CI、真机测试边界 |
| `refactoring.md` | 重构进度、已完成阶段、后续计划 |
| `legacy/` | 历史实现说明，仅供追溯 |

## 当前文档原则

- 文档默认使用中文；代码标识符、命令、API 路径保持原文。
- 示例命令默认使用 Windows PowerShell。
- 默认 Server 端口统一为 `9000`。
- 无真实电镜时，开发和自动化测试统一使用 `null` 模式。
- `remote` Server 模式目前未实现，不应作为可用功能宣传。
- 真实 `temscript` 驱动在缺少真机回归条件时只允许做低风险整理，不应改变硬件行为。
- `docs/legacy/` 中的文件可能包含旧目录、旧端口或已废弃 import，不应直接复制到新代码。

## 更新文档的时机

以下修改应同时更新文档：

- 改变 Client / Server / Protocol 的职责边界；
- 修改 Server 默认端口、环境变量或 CLI 参数；
- 新增、删除或修改 HTTP / WebSocket API；
- 更改项目安装、启动、测试或打包方式；
- 移动公共 package 或改变推荐 import 路径；
- 改变 Null 模式或真实硬件模式的支持范围。
