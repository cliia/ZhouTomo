#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from autofocus.config import AutofocusSettings
from autofocus.microscope_api import MicroscopeAPI
from model.targets import TargetModel
from src.utils import get_definition  # 你的清晰度评价方法


class AutofocusController(QObject):
    progress = pyqtSignal(int, str)
    frame = pyqtSignal(object)
    finished = pyqtSignal(bool, dict)
    error = pyqtSignal(str)
    # 清晰度曲线（实时）：defocus(um), definition(value), step_idx(从1开始)
    focusMetric = pyqtSignal(float, float, int)

    def __init__(self, api: MicroscopeAPI, target: TargetModel, settings: AutofocusSettings, parent=None):
        super().__init__(parent)
        self.api = api
        self.target = target
        self.cfg = settings
        self._cancel = False

        # 记录曲线
        self.defocus_list = []
        self.definition_list = []
        self._defocus_cumulative = 0.0  # um 累计相对离焦，用作x轴

    def cancel(self):
        self._cancel = True

    def start(self):
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(self._run())

    async def _run(self):
        try:
            # 粗搜（OFRS）
            self.progress.emit(1, "Coarse search (OFRS)")
            ok = await self._coarse_search()
            if not ok:
                return self.finished.emit(False, {"reason": "coarse-failed"})
            if self._cancel:
                return self.finished.emit(False, {"reason": "cancelled"})

            # 细搜（FRS）
            self.progress.emit(2, "Fine search (FRS)")
            ok = await self._fine_search()
            if not ok:
                return self.finished.emit(False, {"reason": "fine-failed"})
            if self._cancel:
                return self.finished.emit(False, {"reason": "cancelled"})

            # 最终确认
            self.progress.emit(3, "Confirm")
            frame = await self.api.acquire_frame()
            if frame is not None:
                self.frame.emit(frame)
            self.finished.emit(True, {"defocus_curve": self.defocus_list, "definition_curve": self.definition_list})
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, {"error": str(e)})

    async def _coarse_search(self) -> bool:
        step = max(1.0, float(self.cfg.ofrs_step_nm))
        max_iters = max(1, int(self.cfg.max_iterations))
        self.defocus_list.clear()
        self.definition_list.clear()
        self._defocus_cumulative = 0.0

        direction = 1.0
        for it in range(max_iters):
            if self._cancel:
                return False
            # 采集
            frame = await self.api.acquire_frame()
            if frame is None:
                return False
            self.frame.emit(frame)
            # 清晰度（在当前 defocus 位置测量）
            definition, _ = get_definition(frame, method='VGR')
            self.defocus_list.append(float(self._defocus_cumulative))
            self.definition_list.append(float(definition))
            self.focusMetric.emit(float(self._defocus_cumulative), float(definition), len(self.definition_list))

            # 简化的方向更新逻辑（参考旧实现思想）：第一步取负方向，第二步根据梯度切换
            if len(self.definition_list) == 1:
                direction = -1.0
            elif len(self.definition_list) == 2:
                grad = (self.definition_list[1] - self.definition_list[0])
                direction = 1.0 if grad >= 0 else -1.0
            else:
                # 使用最近两步的梯度指示方向
                grad = (self.definition_list[-1] - self.definition_list[-2])
                direction = 1.0 if grad >= 0 else -1.0

            # 相对调整 defocus（占位，实际请改为设置电镜 defocus 或 stage z）
            delta = direction * step
            ok = await self.api.set_defocus_relative(delta)
            if ok:
                self._defocus_cumulative += float(delta)
        return True

    async def _fine_search(self) -> bool:
        step = max(0.5, float(self.cfg.frs_step_nm))
        max_iters = max(1, int(self.cfg.max_iterations))

        for it in range(max_iters):
            if self._cancel:
                return False
            frame = await self.api.acquire_frame()
            if frame is None:
                return False
            self.frame.emit(frame)
            definition, _ = get_definition(frame, method='VGR')
            self.defocus_list.append(float(self._defocus_cumulative))
            self.definition_list.append(float(definition))
            self.focusMetric.emit(float(self._defocus_cumulative), float(definition), len(self.definition_list))

            # 用更小步长调整
            grad = 0.0 if len(self.definition_list) < 2 else (self.definition_list[-1] - self.definition_list[-2])
            direction = 1.0 if grad >= 0 else -1.0
            delta = direction * step
            ok = await self.api.set_defocus_relative(delta)
            if ok:
                self._defocus_cumulative += float(delta)
        return True


