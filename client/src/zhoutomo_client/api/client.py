"""
远程客户端SDK - AgentClient

本模块实现了远程电脑的AgentClient类，用于与本地电脑的显微镜代理服务器通信。
提供HTTP和WebSocket接口的封装，包括状态获取、参数设置、图像流订阅等功能。

使用方法:
    client = AgentClient("http://localhost:8000")
    state = await client.get_state()
    await client.set_param("camera", {"exposure_time": 100.0})
    async for frame in client.subscribe_frames():
        process_frame(frame)
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, AsyncGenerator, Union
from urllib.parse import urljoin, urlparse
from contextlib import asynccontextmanager

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentClientError(Exception):
    """AgentClient异常基类"""
    pass


class ConnectionError(AgentClientError):
    """连接错误"""
    pass


class AuthenticationError(AgentClientError):
    """认证错误"""
    pass


class APIError(AgentClientError):
    """API调用错误"""
    pass


class WebSocketError(AgentClientError):
    """WebSocket错误"""
    pass


class AgentClient:
    """
    远程显微镜代理客户端
    
    提供与本地显微镜代理服务器的HTTP和WebSocket通信接口
    """
    
    def __init__(self, base_url: str, timeout: float = 30.0, max_retries: int = 3):
        """
        初始化客户端
        
        Args:
            base_url: 代理服务器基础URL (如: "http://localhost:8000")
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        
        # 验证URL格式
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL format: {base_url}")
            
        # 构建WebSocket URL
        if parsed.scheme == 'https':
            self.ws_url = f"wss://{parsed.netloc}/ws/frames"
        else:
            self.ws_url = f"ws://{parsed.netloc}/ws/frames"
            
        logger.info(f"AgentClient initialized for {base_url}")
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
        
    async def connect(self):
        """建立HTTP连接"""
        await self._ensure_session_for_current_loop()
            
    async def disconnect(self):
        """断开所有连接"""
        if self.session:
            await self.session.close()
            self.session = None
            self._session_loop = None
            logger.info("HTTP session closed")
            
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("WebSocket connection closed")
            
    async def _ensure_session_for_current_loop(self):
        """确保在当前事件循环中拥有可用的ClientSession。
        如果已存在但绑定在不同事件循环，创建一个新的Session绑定到当前循环。
        旧Session若来自其它循环，这里不强行关闭以避免跨循环关闭带来的错误。"""
        current_loop = asyncio.get_event_loop()
        needs_new = (
            self.session is None or
            getattr(self.session, 'closed', False) or
            self._session_loop is None or
            self._session_loop is not current_loop
        )
        if needs_new:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            # 不在此处关闭旧session，避免跨循环关闭引发错误
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'ZhouTomo-AgentClient/1.0.0',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            )
            self._session_loop = current_loop
            logger.info("HTTP session (re)created for current event loop")

    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求数据
            
        Returns:
            响应数据
            
        Raises:
            ConnectionError: 连接错误
            APIError: API调用错误
        """
        
        print('_MAKE_REQUEST', method, endpoint, data)

        await self._ensure_session_for_current_loop()
            
        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.request(method, url, json=data) as response:
                    print(f"Response status: {response.status}")
                    print(f"Response headers: {dict(response.headers)}")
                    
                    if response.status == 200:
                        response_data = await response.json()
                        return response_data
                    elif response.status == 401:
                        raise AuthenticationError("Authentication required")
                    elif response.status == 404:
                        raise APIError(f"Endpoint not found: {endpoint}")
                    elif response.status >= 500:
                        raise APIError(f"Server error: {response.status}")
                    else:
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('message', 'Unknown error')
                            print(f"Error response: {error_data}")
                        except:
                            error_msg = f"HTTP {response.status}"
                            print(f"Could not parse error response, status: {response.status}")
                        raise APIError(f"API error: {error_msg}")
                        
            except (RuntimeError, aiohttp.ClientError) as e:
                # 若出现跨事件循环相关错误（如 Timeout context manager 应在 task 中使用），
                # 尝试在当前循环重建 session 并立即重试一次
                if isinstance(e, RuntimeError) and "Timeout context manager" in str(e):
                    logger.warning("Detected event-loop mismatch for ClientSession; recreating session and retrying once...")
                    await self._ensure_session_for_current_loop()
                    # 立即进行一次快速重试，不计入总体重试次数
                    try:
                        async with self.session.request(method, url, json=data) as response:
                            print(f"Response status: {response.status}")
                            print(f"Response headers: {dict(response.headers)}")
                            if response.status == 200:
                                response_data = await response.json()
                                return response_data
                            elif response.status == 401:
                                raise AuthenticationError("Authentication required")
                            elif response.status == 404:
                                raise APIError(f"Endpoint not found: {endpoint}")
                            elif response.status >= 500:
                                raise APIError(f"Server error: {response.status}")
                            else:
                                try:
                                    error_data = await response.json()
                                    error_msg = error_data.get('message', 'Unknown error')
                                    print(f"Error response: {error_data}")
                                except:
                                    error_msg = f"HTTP {response.status}"
                                    print(f"Could not parse error response, status: {response.status}")
                                raise APIError(f"API error: {error_msg}")
                    except Exception as e2:
                        # 若快速重试仍失败，继续按正常重试流程处理
                        logger.warning(f"Immediate retry after session recreation failed: {e2}")
                        # 继续走到下面的重试等待
                
                if attempt == self.max_retries - 1:
                    raise ConnectionError(f"Failed to connect after {self.max_retries} attempts: {e}")
                logger.warning(f"Request failed, retrying... ({attempt + 1}/{self.max_retries})")
                await asyncio.sleep(2 * (attempt + 1))  # 指数退避
                
        raise ConnectionError("Max retries exceeded")
        
    async def get_health(self) -> Dict[str, Any]:
        """
        获取服务器健康状态
        
        Returns:
            健康状态信息
        """
        return await self._make_request("GET", "/health")
        
    async def get_version(self) -> Dict[str, Any]:
        """
        获取API版本信息
        
        Returns:
            版本信息
        """
        return await self._make_request("GET", "/version")
        
    async def get_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        
        Returns:
            系统信息
        """
        return await self._make_request("GET", "/info")
        
    async def get_snapshot(self) -> Dict[str, Any]:
        """
        获取显微镜完整状态快照
        
        Returns:
            显微镜状态数据
        """
        return await self._make_request("GET", "/snapshot")
        
    async def get_component_state(self, component: str) -> Dict[str, Any]:
        """
        获取指定组件的状态
        
        Args:
            component: 组件名称 (如: "camera", "stage", "gun")
            
        Returns:
            组件状态数据
        """
        return await self._make_request("GET", f"/components/{component}/state")
        
    async def get_params(self) -> Dict[str, Any]:
        """
        获取显微镜参数配置
        
        Returns:
            参数配置数据
        """
        return await self._make_request("GET", "/params")
        
    async def set_component_params(self, component: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        设置指定组件的参数
        
        Args:
            component: 组件名称
            params: 参数字典
            
        Returns:
            设置结果
        """
        print(f"=== set_component_params 开始 ===")
        print(f"组件: {component}")
        print(f"参数: {params}")
        print(f"参数类型: {type(params)}")
        
        # 验证参数是否为可序列化的字典
        if not isinstance(params, dict):
            raise ValueError(f"参数必须是字典类型，当前类型: {type(params)}")
        
        # 检查参数是否包含不可序列化的对象
        def check_serializable(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    check_serializable(value, current_path)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    check_serializable(value, current_path)
            elif not isinstance(obj, (str, int, float, bool, type(None))):
                raise ValueError(f"参数包含不可序列化的对象: {current_path} = {obj} (类型: {type(obj)})")
        
        try:
            check_serializable(params)
            print("参数序列化检查通过")
        except ValueError as e:
            print(f"参数序列化检查失败: {e}")
            raise
        
        # 服务器期望的请求体格式是 {"params": {...}}
        request_body = {"params": params}
        print(f"请求体: {request_body}")
        
        try:
            result = await self._make_request("PATCH", f"/components/{component}/params", request_body)
            print(f"设置参数成功，结果: {result}")
            return result
        except Exception as e:
            print(f"设置参数失败: {e}")
            print(f"异常类型: {type(e)}")
            raise
        finally:
            print(f"=== set_component_params 完成 ===")
        
    async def execute_command(self, component: str, command: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行指定组件的命令
        
        Args:
            component: 组件名称
            command: 命令名称
            parameters: 命令参数
            
        Returns:
            命令执行结果
        """
        return await self._make_request("POST", f"/components/{component}/commands/{command}", parameters or {})
        
    async def start_acquisition(self) -> Dict[str, Any]:
        """
        开始图像采集
        
        Returns:
            启动结果
        """
        return await self._make_request("POST", "/acquisition/start")
        
    async def stop_acquisition(self) -> Dict[str, Any]:
        """
        停止图像采集
        
        Returns:
            停止结果
        """
        return await self._make_request("POST", "/acquisition/stop")
        
    async def get_acquisition_status(self) -> Dict[str, Any]:
        """
        获取采集状态
        
        Returns:
            采集状态信息
        """
        return await self._make_request("GET", "/acquisition/status")
        
    # 向后兼容的方法
    async def get_state(self) -> Dict[str, Any]:
        """向后兼容：获取显微镜状态快照"""
        return await self.get_snapshot()
        
    async def set_param(self, component: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """向后兼容：设置指定组件的参数"""
        return await self.set_params(component, params)
        
    async def subscribe_frames(self, component: str = "camera") -> AsyncGenerator[Dict[str, Any], None]:
        """向后兼容：订阅图像帧流"""
        return self.stream_frames(component)
        
    async def stream_frames(self, component: str = "camera") -> AsyncGenerator[Dict[str, Any], None]:
        """
        订阅图像帧流
        
        Args:
            component: 组件名称 (默认: "camera")
            
        Yields:
            图像帧数据
        """
        try:
            # 建立WebSocket连接
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket
                logger.info(f"WebSocket connected to {self.ws_url}")
                
                # 发送订阅消息
                subscribe_msg = {
                    "type": "control",
                    "command": "subscribe",
                    "component": component,
                    "timestamp": time.time()
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # 接收帧数据
                async for message in websocket:
                    try:
                        frame_data = json.loads(message)
                        # 检查是否是连接确认消息
                        if frame_data.get("type") == "connection":
                            logger.info(f"WebSocket connection confirmed: {frame_data.get('message')}")
                            continue
                        # 检查是否是控制响应
                        elif frame_data.get("type") == "control_response":
                            logger.info(f"Control response: {frame_data}")
                            continue
                        # 检查是否是心跳响应
                        elif frame_data.get("type") == "pong":
                            continue
                        # 其他消息作为帧数据处理
                        yield frame_data
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON message: {e}")
                        continue
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except websockets.exceptions.WebSocketException as e:
            raise WebSocketError(f"WebSocket error: {e}")
        except Exception as e:
            raise WebSocketError(f"Unexpected error in frame subscription: {e}")
        finally:
            self.websocket = None
            
    async def get_components(self) -> Dict[str, Any]:
        """
        获取可用组件列表
        
        Returns:
            组件列表
        """
        return await self._make_request("GET", "/components")
        
    async def is_connected(self) -> bool:
        """
        检查与服务器的连接状态
        
        Returns:
            是否连接
        """
        try:
            await self.get_health()
            return True
        except Exception:
            return False
            
    async def ping(self) -> float:
        """
        测试连接延迟
        
        Returns:
            延迟时间(毫秒)
        """
        start_time = time.time()
        try:
            await self.get_health()
            latency = (time.time() - start_time) * 1000
            return latency
        except Exception:
            return -1  # 连接失败
            
    async def send_websocket_ping(self) -> bool:
        """
        发送WebSocket心跳
        
        Returns:
            是否成功
        """
        if not self.websocket:
            return False
            
        try:
            ping_msg = {
                "type": "ping",
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(ping_msg))
            return True
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")
            return False


# 便捷函数
async def create_client(base_url: str, **kwargs) -> AgentClient:
    """
    创建AgentClient实例的便捷函数
    
    Args:
        base_url: 代理服务器基础URL
        **kwargs: 其他参数
        
    Returns:
        AgentClient实例
    """
    client = AgentClient(base_url, **kwargs)
    await client.connect()
    return client


# 使用示例
async def example_usage():
    """使用示例"""
    async with AgentClient("http://localhost:8000") as client:
        # 获取状态
        state = await client.get_state()
        print(f"Microscope state: {state}")
        
        # 设置参数
        result = await client.set_param("camera", {"exposure_time": 100.0})
        print(f"Set param result: {result}")
        
        # 订阅图像流
        async for frame in client.subscribe_frames():
            print(f"Received frame: {frame.get('frame_id', 'unknown')}")
            break  # 只接收一帧作为示例


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())
