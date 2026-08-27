# ZhouTomo v2 - 显微镜控制系统

ZhouTomo是一个基于Python的电子显微镜控制系统，采用分层架构设计，提供稳定、可扩展的显微镜控制接口。

## 🏗️ 项目架构

### 分层设计

```
┌─────────────────────────────────────────────────────────────┐
│                    远程客户端 (Remote Client)                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │     PyQt5 UI    │  │    Web Client   │  │     SDK     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP/WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                本地代理服务器 (Local Agent)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              FastAPI Server                         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │    │
│  │  │ HTTP API    │  │ WebSocket   │  │ 中间件       │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ 依赖注入
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    装配层 (Wiring)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Local Mode    │  │   Remote Mode   │  │  Null Mode  │ │
│  │  (temscript)    │  │ (temscript svr) │  │ (simulator) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ 接口抽象
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    接口层 (Ports)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Gun       │  │Illumination │  │      Camera         │ │
│  │   Port      │  │   Port      │  │      Port           │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Stage     │  │   Vacuum    │  │      Mode           │ │
│  │   Port      │  │   Port      │  │      Port           │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ 硬件驱动
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    硬件层 (Hardware)                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              temscript SDK                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │   Gun       │  │Illumination │  │   Camera    │ │   │
│  │  │  Control    │  │   Control   │  │   Control   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

- **`domain.py`** - 领域模型定义，包含所有数据结构和接口抽象
- **`ports_temscript.py`** - temscript硬件驱动实现
- **`wiring.py`** - 装配层，负责组件组合和模式选择
- **`server_fastapi.py`** - FastAPI服务器，提供HTTP和WebSocket接口
- **`run_agent.py`** - 启动脚本，支持多种运行模式

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# 可选：安装开发依赖
pip install -r requirements.txt[dev]
```

### 2. 启动服务

#### 本地模式（直接控制电镜）
```bash
python run_agent.py --mode local
```

#### 模拟器模式（离线调试）
```bash
python run_agent.py --mode null
```

#### 远程模式（连接远程temscript server）
```bash
python run_agent.py --mode remote --server-url http://remote-server:8080
```

#### 开发模式（自动重载）
```bash
python run_agent.py --mode local --reload --log-level debug
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 运行完整测试
python test_api_server.py
```

## 📡 API接口

### HTTP端点

#### 系统信息
- `GET /health` - 健康检查
- `GET /version` - 获取版本信息
- `GET /info` - 获取系统信息

#### 显微镜控制
- `GET /snapshot` - 获取完整状态快照
- `GET /components` - 获取可用组件列表
- `GET /components/{component}/state` - 获取组件状态
- `PATCH /components/{component}/params` - 设置组件参数
- `POST /components/{component}/commands/{command}` - 执行命令

#### 图像采集
- `POST /acquisition/start` - 开始采集
- `POST /acquisition/stop` - 停止采集
- `GET /acquisition/status` - 获取采集状态

### WebSocket端点

- `WS /ws/frames` - 实时图像流推送

## 🔧 配置选项

### 环境变量

- `ZHOUTOMO_MODE` - 运行模式 (local/remote/null)
- `ZHOUTOMO_SERVER_URL` - 远程服务器地址

### 命令行参数

```bash
python run_agent.py --help
```

主要选项：
- `--mode` - 运行模式
- `--host` - 绑定主机地址
- `--port` - 绑定端口号
- `--server-url` - 远程服务器地址
- `--reload` - 启用自动重载
- `--log-level` - 日志级别

## 📊 功能特性

### 显微镜组件支持

- **电子枪 (Gun)** - 电压、电流、温度控制
- **照明系统 (Illumination)** - 光斑大小、强度、光阑
- **投影系统 (Projection)** - 放大倍数、光阑选择
- **载物台 (Stage)** - 位置、速度、限制控制
- **真空系统 (Vacuum)** - 压力、泵状态、阀门
- **工作模式 (Mode)** - 成像、衍射、STEM、EELS
- **束流遮挡 (Blanker)** - 遮挡控制、定时遮挡
- **相机 (Camera)** - 曝光、增益、图像采集
- **采集系统 (Acquisition)** - 批量采集、保存
- **自动归一化 (AutoNormalize)** - 自动参数优化

### 高级功能

- **实时状态监控** - 所有组件状态实时更新
- **参数验证** - 输入参数自动验证和范围检查
- **错误处理** - 完善的异常处理和错误恢复
- **日志记录** - 详细的操作日志和错误追踪
- **健康检查** - 系统状态监控和故障检测
- **WebSocket支持** - 实时数据推送和双向通信

## 🧪 测试

### 运行测试

```bash
# 测试API服务器
python test_api_server.py

# 测试特定功能
python test_wiring.py
python test_import.py
```

### 测试覆盖

- HTTP API端点测试
- WebSocket连接测试
- 组件状态获取测试
- 参数设置测试
- 命令执行测试

## 📚 文档

- [API使用示例](docs/API_USAGE_EXAMPLES.md) - 详细的API使用说明
- [README v2](docs/README_v2.md) - 项目架构详细说明
- [领域模型说明](README_domain.md) - 数据模型和接口定义
- [装配层说明](README_wiring.md) - 组件装配和模式选择

## 🔒 安全考虑

### 生产环境配置

- 限制CORS来源
- 启用身份验证
- 使用HTTPS
- 配置防火墙规则
- 监控异常访问

### 网络安全

- 限制服务器绑定地址
- 实现API密钥或JWT认证
- 使用反向代理（如Nginx）
- 定期安全审计

## 🤝 贡献指南

### 开发环境设置

```bash
# 克隆项目
git clone <repository-url>
cd ZhouTomo_v2

# 安装开发依赖
pip install -r requirements.txt

# 运行测试
python -m pytest

# 代码格式化
black .
flake8 .
```

### 代码规范

- 遵循PEP 8编码规范
- 使用类型注解
- 编写完整的文档字符串
- 添加适当的单元测试

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 🙏 致谢

- 基于temscript SDK开发
- 参考FEI/Thermo Fisher官方文档
- 感谢开源社区的支持

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交Issue
- 发送邮件
- 参与讨论

---

**注意**: 本项目仅供学习和研究使用，在生产环境中使用前请充分测试和验证。
