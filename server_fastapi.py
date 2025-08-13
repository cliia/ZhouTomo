"""
对外API服务器 - FastAPI实现

本模块实现了显微镜系统的对外API接口，包括：
1. HTTP端点：状态获取、参数设置、命令执行
2. WebSocket端点：实时图像流推送
3. 横切关注点：鉴权、日志、错误映射、健康检查、版本号

参考文档: https://temscript.readthedocs.io/en/latest/instrument.html
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ValidationError

# 导入项目模块
from domain import (
    MicroscopeState, MicroscopeParams,
    state_to_dict, params_to_dict,
    create_default_state, create_default_params
)
from wiring import MicroscopeWiring, create_microscope_wiring

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型定义
# ============================================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(description="服务状态")
    timestamp: str = Field(description="检查时间")
    version: str = Field(description="API版本")
    microscope_connected: bool = Field(description="显微镜连接状态")
    uptime: float = Field(description="服务运行时间(秒)")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(description="错误类型")
    message: str = Field(description="错误消息")
    timestamp: str = Field(description="错误时间")
    request_id: str = Field(description="请求ID")


class ComponentParamsRequest(BaseModel):
    """组件参数设置请求"""
    params: Dict[str, Any] = Field(description="参数数据")


class CommandRequest(BaseModel):
    """命令执行请求"""
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="命令参数")


class CommandResponse(BaseModel):
    """命令执行响应"""
    success: bool = Field(description="执行是否成功")
    message: str = Field(description="执行结果消息")
    timestamp: str = Field(description="执行时间")


class FrameData(BaseModel):
    """图像帧数据"""
    frame_id: str = Field(description="帧ID")
    timestamp: float = Field(description="时间戳")
    component: str = Field(description="组件名称")
    data: bytes = Field(description="图像数据")
    metadata: Dict[str, Any] = Field(description="元数据")


# ============================================================================
# 全局状态管理
# ============================================================================

class ServerState:
    """服务器状态管理"""
    
    def __init__(self):
        self.start_time = time.time()
        self.version = "1.0.0"
        self.microscope_wiring: Optional[MicroscopeWiring] = None
        self.acquisition_task: Optional[asyncio.Task] = None
        self.websocket_connections: List[WebSocket] = []
    
    def get_uptime(self) -> float:
        """获取服务运行时间"""
        return time.time() - self.start_time
    
    def is_microscope_connected(self) -> bool:
        """检查显微镜是否连接"""
        if self.microscope_wiring is None:
            return False
        
        try:
            return self.microscope_wiring.is_connected()
        except Exception as e:
            logger.error(f"Error checking microscope connection: {e}")
            return False
    
    async def start_acquisition(self):
        """开始采集任务"""
        if self.acquisition_task is None or self.acquisition_task.done():
            self.acquisition_task = asyncio.create_task(self._acquisition_loop())
            logger.info("Acquisition task started")
    
    async def stop_acquisition(self):
        """停止采集任务"""
        if self.acquisition_task and not self.acquisition_task.done():
            self.acquisition_task.cancel()
            try:
                await self.acquisition_task
            except asyncio.CancelledError:
                pass
            logger.info("Acquisition task stopped")
    
    async def _acquisition_loop(self):
        """采集循环"""
        acquisition_initialized = False
        while True:
            try:
                # 未连接则等待
                if not self.is_microscope_connected():
                    acquisition_initialized = False
                    await asyncio.sleep(5.0)
                    continue

                # 根据装配模式决定模拟/真实
                mode = getattr(self.microscope_wiring, "mode", "null") if self.microscope_wiring else "null"

                # Null 模式不在此处直接生成模拟数据，由 Null 端口负责；这里只驱动获取帧

                # 硬件模式（local/remote）：尝试启动底层采集并抓取帧
                aggregate = self.microscope_wiring.get_aggregate() if self.microscope_wiring else None

                if not acquisition_initialized and aggregate is not None:
                    try:
                        if hasattr(aggregate, "has_component") and aggregate.has_component("acquisition"):
                            aggregate.execute_command("acquisition", "start")
                        acquisition_initialized = True
                    except Exception as e:
                        logger.warning(f"Failed to start hardware acquisition: {e}")

                # 抓取单帧（若相机端口支持）
                image_bytes = None
                try:
                    microscope = self.microscope_wiring.get_microscope() if self.microscope_wiring else None
                    camera = getattr(microscope, "camera", None) if microscope else None
                    acquire_fn = getattr(camera, "acquire_image", None)
                    if callable(acquire_fn):
                        # 将潜在阻塞的采集放到线程池，避免阻塞事件循环
                        loop = asyncio.get_event_loop()
                        image_bytes = await loop.run_in_executor(None, acquire_fn)
                except Exception as e:
                    logger.warning(f"Failed to acquire image from hardware: {e}")

                # 发送帧或小憩等待
                if image_bytes:
                    frame_data = FrameData(
                        frame_id=str(uuid.uuid4()),
                        timestamp=time.time(),
                        component="camera",
                        data=image_bytes,
                        metadata={"width": 1024, "height": 1024, "source": mode}
                    )
                    await self._broadcast_frame(frame_data)
                    # 简单的帧间隔控制（可后续改为读取参数）
                    await asyncio.sleep(1.0)
                else:
                    # 未能获取到帧，稍后重试
                    await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                # 停止底层采集
                try:
                    aggregate = self.microscope_wiring.get_aggregate() if self.microscope_wiring else None
                    if aggregate and hasattr(aggregate, "has_component") and aggregate.has_component("acquisition"):
                        aggregate.execute_command("acquisition", "stop")
                except Exception:
                    pass
                break
            except Exception as e:
                logger.error(f"Error in acquisition loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _broadcast_frame(self, frame_data: FrameData):
        """广播帧数据到所有WebSocket连接"""
        if not self.websocket_connections:
            return
        
        # 移除已关闭的连接
        self.websocket_connections = [
            conn for conn in self.websocket_connections 
            if not conn.client_state.disconnected
        ]
        
        # 广播到所有活跃连接
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json({
                    "type": "frame",
                    "data": {
                        "frame_id": frame_data.frame_id,
                        "timestamp": frame_data.timestamp,
                        "component": frame_data.component,
                        "metadata": frame_data.metadata
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to send frame to websocket: {e}")
                # 移除失败的连接
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)


# 创建全局服务器状态实例
server_state = ServerState()


# ============================================================================
# 依赖注入函数
# ============================================================================

def get_microscope_wiring() -> MicroscopeWiring:
    """获取显微镜装配实例"""
    if not server_state.microscope_wiring:
        logger.error("Microscope not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microscope not initialized"
        )
    
    return server_state.microscope_wiring


def get_microscope_aggregate():
    """获取显微镜聚合根实例"""
    try:
        wiring = get_microscope_wiring()
        
        if wiring is None:
            logger.error("Microscope wiring not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Microscope wiring not available"
            )
        
        if not wiring.is_connected():
            logger.warning("Microscope not connected")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Microscope not connected"
            )
        
        aggregate = wiring.get_aggregate()
        
        if not aggregate:
            logger.error("Microscope aggregate not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Microscope aggregate not available"
            )
        
        return aggregate
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get microscope aggregate: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get microscope aggregate: {str(e)}"
        )


# ============================================================================
# 应用生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting ZhouTomo API Server...")
    
    # 注意：显微镜连接由run_agent.py管理，这里不需要重复连接
    # 如果server_state.microscope_wiring为None，说明需要外部设置
    
    yield
    
    # 关闭时
    logger.info("Shutting down ZhouTomo API Server...")
    if server_state.microscope_wiring:
        server_state.microscope_wiring.disconnect()
    await server_state.stop_acquisition()


def set_microscope_wiring(wiring: MicroscopeWiring):
    """设置显微镜装配实例（由外部调用）"""
    if wiring is None:
        logger.error("Cannot set None wiring")
        return
    
    server_state.microscope_wiring = wiring
    logger.info(f"Microscope wiring set successfully, mode: {wiring.mode}")


# ============================================================================
# FastAPI应用创建
# ============================================================================

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="ZhouTomo API Server",
        description="显微镜控制系统的对外API接口",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境中应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    register_routes(app)
    
    return app


def register_routes(app: FastAPI):
    """注册所有路由到FastAPI应用"""
    
    # 系统相关路由
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """健康检查端点"""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            version=server_state.version,
            microscope_connected=server_state.is_microscope_connected(),
            uptime=server_state.get_uptime()
        )

    @app.get("/version", tags=["System"])
    async def get_version():
        """获取API版本"""
        return {
            "version": server_state.version,
            "timestamp": datetime.now().isoformat()
        }

    @app.get("/info", tags=["System"])
    async def get_system_info():
        """获取系统信息"""
        return {
            "name": "ZhouTomo API Server",
            "version": server_state.version,
            "uptime": server_state.get_uptime(),
            "microscope_connected": server_state.is_microscope_connected(),
            "timestamp": datetime.now().isoformat()
        }

    # 显微镜控制路由
    @app.get("/snapshot", tags=["Microscope"])
    async def get_snapshot(aggregate=Depends(get_microscope_aggregate)):
        """获取显微镜状态快照"""
        try:
            if not aggregate:
                raise HTTPException(status_code=503, detail="Microscope not available")
            
            state = aggregate.get_snapshot()
            return state_to_dict(state)
        except Exception as e:
            logger.error(f"Failed to get snapshot: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/components", tags=["Microscope"])
    async def list_components(aggregate=Depends(get_microscope_aggregate)):
        """获取可用组件列表"""
        try:
            if not aggregate:
                raise HTTPException(status_code=503, detail="Microscope not available")
            
            components = aggregate.get_available_components()
            return {"components": components}
        except Exception as e:
            logger.error(f"Failed to list components: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/components/{component}/state", tags=["Microscope"])
    async def get_component_state(
        component: str,
        aggregate=Depends(get_microscope_aggregate)
    ):
        """获取指定组件状态"""
        try:
            if not aggregate:
                raise HTTPException(status_code=503, detail="Microscope not available")
            
            if not aggregate.has_component(component):
                raise HTTPException(status_code=404, detail=f"Component {component} not found")
            
            state = aggregate.get_component_state(component)
            return state_to_dict(state)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get component {component} state: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/params", tags=["Microscope"])
    async def get_params():
        """获取参数配置"""
        try:
            # 这里应该返回可配置的参数列表
            # 暂时返回模拟数据
            return {
                "camera": {
                    "exposure_time": {"min": 0.1, "max": 1000.0, "default": 100.0},
                    "gain": {"min": 0.1, "max": 10.0, "default": 1.0}
                },
                "stage": {
                    "x": {"min": -1000, "max": 1000, "default": 0},
                    "y": {"min": -1000, "max": 1000, "default": 0}
                }
            }
        except Exception as e:
            logger.error(f"Failed to get params: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.patch("/components/{component}/params", tags=["Microscope"])
    async def set_component_params(
        component: str,
        request: ComponentParamsRequest,
        aggregate=Depends(get_microscope_aggregate)
    ):
        """设置组件参数"""
        try:
            # 检查组件是否存在
            if hasattr(aggregate, 'has_component'):
                if not aggregate.has_component(component):
                    available_components = aggregate.list_components() if hasattr(aggregate, 'list_components') else []
                    logger.warning(f"组件 {component} 不存在，可用组件: {available_components}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Component {component} not found"
                    )
            
            # 将字典转换为对应组件的dataclass（当前至少支持 acquisition）
            converted_params = request.params
            try:
                if isinstance(request.params, dict):
                    if component == "acquisition":
                        from domain import AcquisitionParams
                        allowed_keys = {"acq_image_size", "dwell_time", "brightness", "contrast", "binnings", "frames"}
                        filtered = {k: v for k, v in request.params.items() if k in allowed_keys}
                        converted_params = AcquisitionParams(**filtered)
            except Exception as conv_e:
                logger.warning(f"参数转换失败，按原样下发: {conv_e}")

            # 设置参数
            success = aggregate.set_component_params(component, converted_params)
            
            if success:
                logger.info(f"成功更新 {component} 参数")
                return {"message": f"Successfully updated {component} parameters"}
            else:
                logger.error(f"参数设置失败")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to update {component} parameters"
                )
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"参数值错误: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid parameter value: {str(e)}"
            )
        except Exception as e:
            logger.error(f"设置组件参数时发生异常: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to set component params: {str(e)}"
            )

    @app.post("/components/{component}/commands/{command}", tags=["Commands"])
    async def execute_command(
        component: str,
        command: str,
        request: CommandRequest,
        aggregate=Depends(get_microscope_aggregate)
    ):
        """执行组件命令"""
        try:
            if not aggregate:
                raise HTTPException(status_code=503, detail="Microscope not available")
            
            if not aggregate.has_component(component):
                raise HTTPException(status_code=404, detail=f"Component {component} not found")
            
            # 执行命令
            parameters = request.parameters or {}
            result = aggregate.execute_command(component, command, **parameters)
            return CommandResponse(
                success=True,
                message=f"Command {command} executed successfully",
                timestamp=datetime.now().isoformat()
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to execute command {command} on {component}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # 采集控制路由
    @app.post("/acquisition/start", tags=["Acquisition"]) 
    async def start_acquisition():
        """一次性采集，返回采集到的帧列表（base64编码）"""
        try:
            # 确保已连接并获取显微镜实例
            wiring = get_microscope_wiring()
            if not wiring.is_connected():
                raise HTTPException(status_code=503, detail="Microscope not connected")

            microscope = wiring.get_microscope()
            if microscope is None:
                raise HTTPException(status_code=503, detail="Microscope not available")

            # 在线程池中执行可能阻塞的采集
            loop = asyncio.get_running_loop()
            raw_frames = await loop.run_in_executor(None, microscope.start_acquisition)

            # 统一转为可序列化：确保为“帧列表”，避免 bytes 被当作可迭代导致按字节拆成数百万“帧”
            def normalize_to_frame_list(obj):
                if obj is None:
                    return []
                # 单帧：bytes 类
                if isinstance(obj, (bytes, bytearray, memoryview)):
                    return [bytes(obj)]
                # 单帧：numpy.ndarray 或类似
                if hasattr(obj, 'tobytes') and callable(getattr(obj, 'tobytes')):
                    try:
                        return [obj.tobytes()]
                    except Exception:
                        return [obj]
                # 多帧：list/tuple
                if isinstance(obj, (list, tuple)):
                    return list(obj)
                # 回退：将任意对象视为单帧
                return [obj]

            frames = normalize_to_frame_list(raw_frames)

            # 转 base64 序列化
            import base64
            frames_b64 = []
            for f in frames:
                # 兼容 numpy.ndarray / memoryview / bytes
                if hasattr(f, 'tobytes') and callable(getattr(f, 'tobytes')):
                    f = f.tobytes()
                if isinstance(f, (bytes, bytearray, memoryview)):
                    frames_b64.append(base64.b64encode(bytes(f)).decode('ascii'))
                else:
                    # 非字节数据，转字符串以防崩溃（调试占位）
                    frames_b64.append(base64.b64encode(str(f).encode('utf-8')).decode('ascii'))

            return {
                "success": True,
                "frames": frames_b64,
                "count": len(frames_b64)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/acquisition/stop", tags=["Acquisition"])
    async def stop_acquisition():
        """停止采集"""
        try:
            await server_state.stop_acquisition()
            return {
                "success": True,
                "message": "Acquisition stopped",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to stop acquisition: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/acquisition/status", tags=["Acquisition"])
    async def get_acquisition_status():
        """获取采集状态"""
        try:
            return {
                "active": server_state.acquisition_task is not None and not server_state.acquisition_task.done(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get acquisition status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # WebSocket路由
    @app.websocket("/ws/frames")
    async def websocket_frames(websocket: WebSocket):
        """WebSocket图像帧流端点"""
        await websocket.accept()
        server_state.websocket_connections.append(websocket)
        
        try:
            while True:
                # 发送心跳
                await websocket.send_text(json.dumps({
                    "type": "heartbeat",
                    "timestamp": time.time()
                }))
                
                # 等待消息
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": time.time()
                        }))
                    elif message.get("type") == "control":
                        # 处理控制命令
                        await _handle_websocket_control(websocket, message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from WebSocket: {data}")
                    
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # 清理连接
            if websocket in server_state.websocket_connections:
                server_state.websocket_connections.remove(websocket)


# 创建默认应用实例（用于直接运行server_fastapi.py时）
app = create_app()


# ============================================================================
# 中间件
# ============================================================================

@app.middleware("http")
async def add_process_time_header(request, call_next):
    """添加处理时间头"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def add_request_id_header(request, call_next):
    """添加请求ID头"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ============================================================================
# 异常处理器
# ============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    """验证错误处理器"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message=str(exc),
            timestamp=datetime.now().isoformat(),
            request_id=getattr(request.state, 'request_id', 'unknown')
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            timestamp=datetime.now().isoformat(),
            request_id=getattr(request.state, 'request_id', 'unknown')
        ).dict()
    )


# ============================================================================
# 健康检查和系统信息
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version=server_state.version,
        microscope_connected=server_state.is_microscope_connected(),
        uptime=server_state.get_uptime()
    )


@app.get("/version", tags=["System"])
async def get_version():
    """获取API版本"""
    return {
        "version": server_state.version,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/info", tags=["System"])
async def get_system_info():
    """获取系统信息"""
    info = {
        "version": server_state.version,
        "uptime": server_state.get_uptime(),
        "microscope_connected": server_state.is_microscope_connected(),
        "acquisition_running": server_state.acquisition_task is not None and not server_state.acquisition_task.done(),
        "connected_clients": len(server_state.websocket_connections)
    }
    
    if server_state.microscope_wiring:
        info["microscope_info"] = server_state.microscope_wiring.get_info()
    
    return info


# ============================================================================
# 显微镜状态和参数管理
# ============================================================================

@app.get("/snapshot", tags=["Microscope"])
async def get_snapshot(aggregate=Depends(get_microscope_aggregate)):
    """获取显微镜完整状态快照"""
    try:
        snapshot = aggregate.get_snapshot()
        return state_to_dict(snapshot)
    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get snapshot: {str(e)}"
        )


@app.get("/components", tags=["Microscope"])
async def list_components(aggregate=Depends(get_microscope_aggregate)):
    """获取可用组件列表"""
    try:
        components = aggregate.list_components()
        return {"components": components}
    except Exception as e:
        logger.error(f"Failed to list components: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list components: {str(e)}"
        )


@app.get("/components/{component}/state", tags=["Microscope"])
async def get_component_state(
    component: str,
    aggregate=Depends(get_microscope_aggregate)
):
    """获取指定组件的状态"""
    try:
        state = aggregate.get_component_state(component)
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component '{component}' not found"
            )
        return state_to_dict(state)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get component state for {component}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get component state: {str(e)}"
        )


@app.get("/params", tags=["Microscope"])
async def get_params():
    """获取显微镜默认参数"""
    try:
        params = create_default_params()
        return params_to_dict(params)
    except Exception as e:
        logger.error(f"Failed to get default params: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default params: {str(e)}"
        )


@app.patch("/components/{component}/params", tags=["Microscope"])
async def set_component_params(
    component: str,
    request: ComponentParamsRequest,
    aggregate=Depends(get_microscope_aggregate)
):
    """设置指定组件的参数"""
    try:
        # 检查组件是否存在
        if hasattr(aggregate, 'has_component'):
            if not aggregate.has_component(component):
                available_components = aggregate.list_components() if hasattr(aggregate, 'list_components') else []
                logger.warning(f"Component {component} not found, available: {available_components}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Component {component} not found"
                )
        
        # 设置参数
        success = aggregate.set_component_params(component, request.params)
        
        if success:
            logger.info(f"Successfully updated {component} parameters")
            return {"message": f"Successfully updated {component} parameters"}
        else:
            logger.error(f"Failed to update {component} parameters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update {component} parameters"
            )
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid parameter value: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter value: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error setting component params: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set component params: {str(e)}"
        )


# ============================================================================
# 命令执行
# ============================================================================






async def _handle_websocket_control(websocket: WebSocket, message: Dict[str, Any]):
    """处理WebSocket控制消息"""
    try:
        command = message.get("command")
        if command == "set_frame_interval":
            interval = message.get("interval", 1.0)
            # 模拟帧间隔设置
            # 实际应用中，需要更新server_state.frame_interval
            await websocket.send_text(json.dumps({
                "type": "control_response",
                "command": command,
                "success": True,
                "message": f"Frame interval set to {interval}s (simulated)"
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "control_response",
                "command": command,
                "success": False,
                "message": f"Unknown command: {command}"
            }))
    except Exception as e:
        logger.error(f"Failed to handle WebSocket control: {e}")
        await websocket.send_text(json.dumps({
            "type": "control_response",
            "command": message.get("command", "unknown"),
            "success": False,
            "message": f"Error: {str(e)}"
        }))


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ZhouTomo API Server")
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level", 
        default="info", 
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # 启动服务器
    uvicorn.run(
        "server_fastapi:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
