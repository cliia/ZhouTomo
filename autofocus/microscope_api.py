#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional
import base64
import numpy as np


class MicroscopeAPI:
    """薄封装主窗口的 AgentManager，提供采集/移动等常用操作。

    注意：这里不直接依赖具体 UI，只接触 agent_manager。
    """

    def __init__(self, agent_manager):
        self.agent_manager = agent_manager

    async def acquire_frame(self) -> Optional[np.ndarray]:
        """一次采集，返回 numpy.ndarray 灰度图（自动解码 8/16bit 正方形）。"""
        try:
            result = await self.agent_manager.start_acquisition()
            if not result or not isinstance(result, dict):
                return None
            frames_b64 = result.get("frames") or []
            if not frames_b64:
                return None
            b64 = frames_b64[0]
            data = base64.b64decode(b64)
            n = len(data)
            # 8-bit 正方
            side8 = int(n ** 0.5)
            if side8 * side8 == n:
                return np.frombuffer(data, dtype=np.uint8).reshape(side8, side8)
            # 16-bit 正方
            side16 = int((n // 2) ** 0.5)
            if side16 * side16 * 2 == n:
                return np.frombuffer(data, dtype='<u2').reshape(side16, side16)
            # 兜底
            return None
        except Exception:
            return None

    async def move_stage_relative(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0,
                                  da: float = 0.0, db: float = 0.0) -> bool:
        """相对移动样品台，单位 um / rad（按你的系统定义）。"""
        try:
            # 读取当前 stage 状态
            state = await self.agent_manager.get_component_state('stage')
            # 兼容两种结构：{'position':{x,y,z,a,b}} 或 {'x':...}
            pos = state.get('position', state)
            cx = float(pos.get('x', 0.0))
            cy = float(pos.get('y', 0.0))
            cz = float(pos.get('z', 0.0))
            ca = float(pos.get('a', 0.0))
            cb = float(pos.get('b', 0.0))

            new_pos = {
                'x': cx + float(dx),
                'y': cy + float(dy),
                'z': cz + float(dz),
                'a': ca + float(da),
                'b': cb + float(db),
            }

            # 优先尝试 position 内层
            try:
                result = await self.agent_manager.set_component_params('stage', {'params': new_pos})
                return bool(result)
            except Exception:
                # 回退为顶层 x,y,z,a,b
                result = await self.agent_manager.set_component_params('stage', new_pos)
                return bool(result)
        except Exception:
            return False

    async def set_defocus_relative(self, d_defocus: float) -> bool:
        """相对调整离焦值，单位 um。
        读取 projection.state['defocus'] -> 设置 projection.params{'defocus': new}
        """
        try:
            state = await self.agent_manager.get_component_state('projection')
            curr = float(state.get('defocus', 0.0))
            new_val = curr + float(d_defocus)
            params = {'defocus': new_val}
            result = await self.agent_manager.set_component_params('projection', params)
            return bool(result)
        except Exception:
            return False


