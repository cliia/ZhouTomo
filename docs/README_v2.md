# 1 总体架构

`ZhouTomo` 总体架构分为**本地电脑**和**远程电脑**

* **本地电脑 MA**

  作为代理显微镜（Microscope Agent, MA），负责和电子显微镜（Electron Microscope, EM）/temscript 软件开发工作包（Software Development Kit, SDK）通讯，暴露稳定的网络接口。

* **远程电脑**

  运行可视化与控制 UI，只和 MA 的网络接口交互。



## 1.1 分层与职责

### 领域层 Domain（抽象）

* `MicroscopeInterface`：抽象出最小可用能力（GET / SET / 采集流）
* `MicroscopeState`、`AcquisitionParam` 等数据模型（Data Transfer Object, DTO）

### 驱动层 Driver（temscript）

* `VendorMicroscope`：实现 `MicroscopeInterface`，即 `temscript` 封装的 SDK
* `MockMicroscope`：EM 模拟器，用于离线调试

### 本地服务器 Agent

* `CommandHandler`：执行 SET / GET 指令（Remote Procedure Call, RPC）
* `FrameStreamer`：采集流（`WebSocket`）
* `AgentAPI`：进程对外 API（`FastAPI` + `WebSocket`）
* 横切：鉴权、日志、错误映射、健康检查/心跳、版本号。

### 远程客户端库 SDK

* `AgentClient`：封装网络协议，包括以下方法
  * `get_state()`
  * `set_param()`
  * `subscribe_frames()`
* 远程 UI 直接依赖 SDK

### 远程界面层 UI

* 基于 PyQt5



## 1.2 数据模型 DTO





# 2 本地电脑

**主要作用**

* 直接通过 `temscript` 控制 EM
* 对外暴露一个安全的 API 给全程电脑使用

## **A. 领域层（domain.py）**

* 定义了每个功能模块的数据模型
  * `Gun`
  * `Illumination`
  * `Projection`
  * `Stage`
  * `Vacuum`
  * `Mode`
  * `Blanker`
  * `Camera`
  * `Acquisition`
  * `AutoNormalize`
* 每个模块包含
  * `State` 当前状态
  * `Params` 可设置的参数
* 通过 `MicroscopeAggregate` 聚合所有的组件，方便一次性获取全部状态（snapshot）

## **B. 硬件接口层（ports_temscript.py）**

* 这里的类是每个组件的驱动，直接调用 `temscript` 的方法

  如：

  * `StagePortTS` 调用 `microscope.get_stage_position()` 读取位置
  * `IlluminationPortTS` 调用 `set_spot_size_index()` 修改光斑
  * `CameraPortTS` 调用 `acquire()` 获取图像

* `microscope` 类可以替换为 `NullMicroscope` 或 `RemoteMicroscope`

## **C. 装配层（wiring.py）**

* 决定使用哪种显微镜实现
  * `local` 本地直接使用 `Microscope`
  * `remote` 连接 temscript server `RemoteMicroscope`
  * `null` 用模拟器 `NullMicroscope`
* 把所有组件的 Port 实例化，组合成 `MicroscopeAggregate`

## **D. 对外 API（server_fastapi.py）**

* HTTP 端点
  * `GET /snapshot` 获取全部状态
  * `PATCH /params/{component}` 修改组件参数
  * `POST /cmd/{component}/...` 执行操作（如移动 stage）
* WebSocket 端点
  * `/ws/frames` 持续推送相机传回图像流

## **E. 启动入口（run_agent.py）**

* 命令行参数
  * `--mode`（null/local/remote）
  * `--server_url`（remote 模式时的 temscript server 地址）
* 启动 FastAPI 服务，准备好 WebSocket 推流



# 3 远程电脑

**主要作用**

* 通过 HTTP/WS 调用本地电脑提供的 API
* 获取实时图像、设置参数、控制电镜

## A. 客户端 SDK

* Python 类 `AgentClient`
  * 方法：
    * `get_snapshot()`
    * `set_params(component, params)`
    * `start_acquisition()`
    * `stop_acquisition()`
    * `stream_frames()`

## B. UI

PyQt5



# 4 ZhouTomo FastAPI v1.0.0









