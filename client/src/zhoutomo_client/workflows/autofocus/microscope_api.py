#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, Any
import base64
import numpy as np
import logging

try:
    from zhoutomo_client.api import AgentClient
except Exception:
    AgentClient = None


class MicroscopeAPI:
    """薄封装主窗口的 AgentManager，提供采集/移动等常用操作。

    注意：这里不直接依赖具体 UI，只接触 agent_manager。
    """

    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.server_url = getattr(agent_manager, 'server_url', None)
        self._logger = logging.getLogger(__name__)

    async def acquire_frame(self) -> Optional[np.ndarray]:
        """一次采集，返回 numpy.ndarray 灰度图。
        优先使用服务器返回的 frame_shapes/frame_dtypes/frame_byteorders 元数据，避免靠平方根猜测。
        """
        try:
            # 使用独立客户端，避免跨事件循环复用旧 session
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    result = await client._make_request("POST", "/acquisition/start")
            else:
                result = await self.agent_manager.start_acquisition()
            if not result or not isinstance(result, dict):
                return None
            frames_b64 = result.get("frames") or []
            if not frames_b64:
                return None
            b64 = frames_b64[0]
            data = base64.b64decode(b64)
            shapes = result.get("frame_shapes") or []
            dtypes = result.get("frame_dtypes") or []
            byteorders = result.get("frame_byteorders") or []
            # 更新信息面板底部参数：在有快照接口时由外层刷新；此处仅在日志提示
            try:
                self._logger.info(f"[AF] acquire_frame: shapes0={shapes[0] if shapes else None}, dtype0={dtypes[0] if dtypes else None}")
            except Exception:
                pass

            def _dtype_from_meta(dtype_name: str, byteorder: str):
                if not dtype_name:
                    return None
                dn = dtype_name.lower()
                bo = '<' if byteorder in (None, '=', '<') else '>'
                mapping = {
                    'uint8': 'u1', 'u1': 'u1',
                    'uint16': 'u2', 'u2': 'u2',
                    'int16': 'i2', 'i2': 'i2',
                    'int32': 'i4', 'i4': 'i4',
                    'float32': 'f4', 'f4': 'f4',
                    'float64': 'f8', 'f8': 'f8',
                }
                core = mapping.get(dn)
                if not core:
                    return None
                if core in ('u1',):
                    return np.dtype(core)
                return np.dtype(bo + core)

            try:
                if shapes and dtypes:
                    shape = shapes[0]
                    dtype_name = dtypes[0]
                    byteorder = byteorders[0] if byteorders else None
                    if shape and len(shape) >= 2 and dtype_name:
                        h, w = int(shape[0]), int(shape[1])
                        dt = _dtype_from_meta(dtype_name, byteorder)
                        if dt is not None:
                            arr = np.frombuffer(data, dtype=dt)
                            if arr.size >= h * w:
                                self._logger.info(f"[AF] decoded by meta: shape=({h},{w}), dtype={dt}")
                                return arr[:h*w].reshape(h, w)
            except Exception:
                pass

            # 回退：正方猜测
            n = len(data)
            side8 = int(n ** 0.5)
            if side8 * side8 == n:
                self._logger.info(f"[AF] decoded as u8 square: side={side8}")
                return np.frombuffer(data, dtype=np.uint8).reshape(side8, side8)
            side16 = int((n // 2) ** 0.5)
            if side16 * side16 * 2 == n:
                self._logger.info(f"[AF] decoded as u16 square: side={side16}")
                return np.frombuffer(data, dtype='<u2').reshape(side16, side16)
            return None
        except Exception:
            return None

    async def get_acquisition_state(self) -> Optional[Dict[str, Any]]:
        """获取采集状态"""
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/acquisition/state")
            else:
                state = await self.agent_manager.get_component_state('acquisition')
            return state
        except Exception:
            return None

    async def set_acquisition_state(self, state: Dict[str, Any]) -> bool:
        """设置采集状态"""
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    body = {"params": state}
                    result = await client._make_request("PATCH", "/components/acquisition/params", body)
            else:
                result = await self.agent_manager.set_component_state('acquisition', state)
            return bool(result)
        except Exception:
            return False

    async def get_stage_position(self) -> Optional[Dict[str, float]]:
        """
        获取样品台位置
        
        返回：
            - 字典：{'x': x, 'y': y, 'z': z, 'a': a, 'b': b}
            - 单位：um, um, um, rad, rad
            - 若失败，返回 None
        """
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/stage/state")
            else:
                state = await self.agent_manager.get_component_state('stage')
            return state.get('position', state)
        except Exception:
            return None

    async def set_stage_position(self, position: Dict[str, float]) -> bool:
        """设置样品台位置"""
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    body = {"params": position}
                    result = await client._make_request("PATCH", "/components/stage/params", body)
            else:
                result = await self.agent_manager.set_component_params('stage', position)
            return bool(result)
        except Exception:
            return False

    async def move_stage_relative(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0,
                                  da: float = 0.0, db: float = 0.0) -> bool:
        """相对移动样品台，单位 m / rad（按你的系统定义）。"""
        try:
            # 使用临时客户端避免跨事件循环
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/stage/state")
            else:
                state = await self.agent_manager.get_component_state('stage')
            pos = state.get('position', state)
            cx = float(pos.get('x', 0.0))
            cy = float(pos.get('y', 0.0))
            cz = float(pos.get('z', 0.0))
            ca = float(pos.get('a', 0.0))
            cb = float(pos.get('b', 0.0))

            new_pos = {
                'position': {
                    'x': cx + float(dx),
                    'y': cy + float(dy),
                    'z': cz + float(dz),
                    'a': ca + float(da),
                    'b': cb + float(db),
                }
            }

            # 下发参数
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    # 服务端期望 body: {"params": {...}}
                    body = {"params": new_pos}
                    result = await client._make_request("PATCH", "/components/stage/params", body)
                    return bool(result)
            else:
                # 直接传入展平后的参数字典，由 AgentClientManager 统一封装为 {"params": ...}
                result = await self.agent_manager.set_component_params('stage', new_pos)
                return bool(result)
        except Exception:
            return False

    async def get_defocus(self) -> Optional[float]:
        """
        获取当前离焦值
        
        返回：
            - 离焦值，单位 m
            - 若失败，返回 None
        """
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/projection/state")
            else:
                state = await self.agent_manager.get_component_state('projection')
            return state.get('defocus', 0.0)
        except Exception:
            return None

    async def set_defocus(self, defocus: float) -> bool:
        """设置离焦值"""
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    body = {"params": {'defocus': defocus}}
                    result = await client._make_request("PATCH", "/components/projection/params", body)
            else:
                result = await self.agent_manager.set_component_params('projection', {'defocus': defocus})
            return bool(result)
        except Exception:
            return False

    async def set_defocus_relative(self, d_defocus: float) -> bool:
        """相对调整离焦值，单位 um。
        读取 projection.state['defocus'] -> 设置 projection.params{'defocus': new}
        """
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/projection/state")
            else:
                state = await self.agent_manager.get_component_state('projection')
            curr = float(state.get('defocus', 0.0))
            new_val = curr + float(d_defocus)
            params = {'defocus': new_val}
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    body = {"params": params}
                    result = await client._make_request("PATCH", "/components/projection/params", body)
            else:
                result = await self.agent_manager.set_component_params('projection', params)
            try:
                self._logger.info(f"[AF] set_defocus_relative: curr={curr:.3f} -> new={new_val:.3f}, ok={bool(result)}")
            except Exception:
                pass
            return bool(result)
        except Exception:
            return False

    async def get_stem_magnification(self) -> Optional[float]:
        """
        获取当前放大倍率
        
        返回：
            - 放大倍率，单位 1
            - 若失败，返回 None
        """
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    state = await client._make_request("GET", "/components/illumination/state")
            else:
                state = await self.agent_manager.get_component_state('illumination')
            return state.get('stem_magnification', 0.0)
        except Exception:
            return None

    async def set_stem_magnification(self, magnification: float) -> bool:
        """
        设置放大倍率
        
        返回：
            - 是否成功
        """
        try:
            params = {'stem_magnification': magnification}
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    body = {"params": params}
                    result = await client._make_request("PATCH", "/components/illumination/params", body)
            else:
                result = await self.agent_manager.set_component_params('illumination', params)
            return bool(result)
        except Exception:
            return False

    async def get_snapshot(self) -> Optional[Dict[str, Any]]:
        """获取当前状态快照"""
        try:
            if self.server_url and AgentClient is not None:
                async with AgentClient(self.server_url) as client:
                    snapshot = await client._make_request("GET", "/snapshot")
            else:
                snapshot = await self.agent_manager.get_snapshot()
            return snapshot
        except Exception:
            return None
