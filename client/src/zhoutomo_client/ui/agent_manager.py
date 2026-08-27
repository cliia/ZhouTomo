#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentClientManager 封装与服务器的通信，供 UI 调用。
从原 `view/main_window.py` 中拆分，降低主窗口类体积，提高可读性。
"""

from PyQt5.QtCore import QObject, pyqtSignal

import asyncio

from zhoutomo_client.api import AgentClient


class AgentClientManager(QObject):
    """AgentClient 管理器，处理与电镜代理服务器的通信"""
    # 定义信号
    connectionStatusChanged = pyqtSignal(bool)  # 连接状态变化信号
    snapshotUpdated = pyqtSignal(dict)         # 状态快照更新信号
    acquisitionProgress = pyqtSignal(int, int) # 采集进度信号
    acquisitionCompleted = pyqtSignal()        # 采集完成信号
    acquisitionError = pyqtSignal(str)         # 采集错误信号
    stageMoved = pyqtSignal(float, float, float, float, float)  # 样品台移动信号
    errorOccurred = pyqtSignal(str)            # 错误信号

    def __init__(self):
        super().__init__()
        self.agent_client = None
        self.server_url = None
        self.connection_type = None
        self.is_connected = False

    async def connect_microscope(self, connection_type, server_url=None):
        """连接电镜"""
        try:
            self.connection_type = connection_type

            if connection_type == "local":
                # 本地连接
                self.server_url = "http://localhost:9000"
            elif connection_type == "remote":
                # 远程连接
                if not server_url:
                    raise ValueError("远程连接需要指定服务器URL")
                self.server_url = server_url
            elif connection_type == "dummy":
                # 模拟模式
                self.server_url = "http://localhost:9000"
            else:
                raise ValueError(f"不支持的连接类型: {connection_type}")

            # 创建AgentClient实例
            self.agent_client = AgentClient(self.server_url)

            # 连接服务器
            await self.agent_client.connect()

            # 检查连接状态
            if await self.agent_client.is_connected():
                self.is_connected = True
                self.connectionStatusChanged.emit(True)
                return True
            else:
                self.is_connected = False
                self.connectionStatusChanged.emit(False)
                return False

        except Exception as e:
            self.is_connected = False
            self.connectionStatusChanged.emit(False)
            self.errorOccurred.emit(f"连接电镜失败: {str(e)}")
            return False

    async def disconnect_microscope(self):
        """断开电镜连接"""
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                self.agent_client = None
                self.is_connected = False
                self.connectionStatusChanged.emit(False)
                return True
        except Exception as e:
            self.errorOccurred.emit(f"断开电镜连接失败: {str(e)}")
            return False

    async def get_snapshot(self):
        """获取状态快照"""
        try:
            if not self.agent_client or not self.is_connected:
                raise Exception("电镜未连接")

            snapshot = await self.agent_client.get_snapshot()
            self.snapshotUpdated.emit(snapshot)
            return snapshot
        except Exception as e:
            self.errorOccurred.emit(f"获取状态快照失败: {str(e)}")
            return None

    async def start_acquisition(self):
        """开始图像采集"""
        try:
            if not self.agent_client or not self.is_connected:
                raise Exception("电镜未连接")

            result = await self.agent_client.start_acquisition()
            return result
        except Exception as e:
            self.acquisitionError.emit(f"开始图像采集失败: {str(e)}")
            return None

    async def stop_acquisition(self):
        """停止图像采集"""
        try:
            if not self.agent_client or not self.is_connected:
                raise Exception("电镜未连接")

            result = await self.agent_client.stop_acquisition()
            return result
        except Exception as e:
            self.acquisitionError.emit(f"停止图像采集失败: {str(e)}")
            return None

    async def set_component_params(self, component: str, params):
        """设置组件参数"""
        try:
            if not self.agent_client or not self.is_connected:
                raise Exception("电镜未连接")

            # 若传入的是dataclass对象，先转字典
            try:
                from dataclasses import is_dataclass
                if is_dataclass(params) or hasattr(params, "__dataclass_fields__"):
                    from zhoutomo_protocol import params_to_dict
                    params = params_to_dict(params)
            except Exception:
                pass

            # 通过AgentClient调用服务器的set_component_params API（要求字典）
            result = await self.agent_client.set_component_params(component, params)
            return result
        except Exception as e:
            self.errorOccurred.emit(f"设置组件参数失败: {str(e)}")
            return False

    async def get_component_state(self, component: str):
        """获取组件状态"""
        try:
            if not self.agent_client or not self.is_connected:
                raise Exception("电镜未连接")

            state = await self.agent_client.get_component_state(component)
            return state
        except Exception as e:
            self.errorOccurred.emit(f"获取组件状态失败: {str(e)}")
            return None


