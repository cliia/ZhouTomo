#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, Any, List, Tuple
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from autofocus.microscope_api import MicroscopeAPI
from model.targets import TargetModel, StagePose
from src.utils import mag2ps
from src.normxcorr2 import extract_pattern
import logging


class AutoTiltSettings:
    def __init__(self, sequence: List[float], hr_magnification: Optional[float] = None):
        self.sequence = list(sequence or [])
        self.hr_magnification = float(hr_magnification) if isinstance(hr_magnification, (int, float)) else None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'AutoTiltSettings':
        try:
            seq = list(d.get('sequence', [])) if isinstance(d, dict) else []
            hrmag = d.get('hr_magnification', None) if isinstance(d, dict) else None
            return AutoTiltSettings(seq, hrmag)
        except Exception:
            return AutoTiltSettings([], None)


class AutoTiltController(QObject):
    progress = pyqtSignal(int, str)
    frame = pyqtSignal(object)
    finished = pyqtSignal(bool, dict)
    error = pyqtSignal(str)

    def __init__(self, api: MicroscopeAPI, target: TargetModel, settings: AutoTiltSettings, autofocus_settings_dict: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.api = api
        self.target = target
        self.cfg = settings
        self.af_settings_dict = dict(autofocus_settings_dict or {})
        self._cancel = False
        self._logger = logging.getLogger("autotilt.controller")

    def cancel(self):
        self._cancel = True

    def start(self):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._run())
            finally:
                loop.close()

    async def _run(self):
        try:
            # 0) 初始定位到目标的历史位置（若快照有位姿）
            await self._goto_target_snap_pose()
            if self._cancel:
                return self.finished.emit(False, {"reason": "cancelled"})

            # 1) 统一放大倍率到目标初选时的倍率（若有）
            base_mag = await self._ensure_base_magnification()

            # 2) 拍一张图，与目标 GlobalImage 做归中迭代
            self.progress.emit(1, "归中到目标")
            await self._iterative_center_on_target(max_iters=8, pixel_tol=5.0)

            # 3) 归中完成后，记录基准 Global / Snapshot / Reference（按目标矩形裁剪）
            await self._capture_and_store(alpha_deg=self._get_current_alpha_deg_fallback(), use_hr=False)

            # 4) 放大拍HR作为序列首张（若提供hr倍率，或沿用当前倍率）
            await self._capture_and_store(alpha_deg=self._get_current_alpha_deg_fallback(), use_hr=True, hr_mag_override=self.cfg.hr_magnification)

            # 5) 依序倾转 alpha
            # 在开始前将角度计划下发给信息面板
            try:
                if hasattr(self.parent(), 'info_panel') and self.parent().info_panel:
                    self.parent().info_panel.set_autotilt_plan(list(self.cfg.sequence))
            except Exception:
                pass
            step_idx = 0
            for alpha_deg in self.cfg.sequence:
                step_idx += 1
                if self._cancel:
                    return self.finished.emit(False, {"reason": "cancelled"})
                self.progress.emit(10 + step_idx, f"倾转至 alpha={alpha_deg:.2f}° 并归中/对焦")
                # 向信息面板汇报当前 alpha
                try:
                    if hasattr(self.parent(), 'info_panel') and self.parent().info_panel:
                        self.parent().info_panel.set_autotilt_alpha(float(alpha_deg))
                        self.parent().info_panel.set_autotilt_status("Tilting/Centering...")
                except Exception:
                    pass
                await self._move_stage_alpha_deg(alpha_deg)
                # 最近 alpha 的 Global 用于粗归中
                await self._iterative_center_nearby_alpha(alpha_target_deg=alpha_deg, max_iters=8, pixel_tol=50.0)
                # 用最近 alpha 的参考 ROI 执行自动聚焦
                try:
                    if hasattr(self.parent(), 'info_panel') and self.parent().info_panel:
                        self.parent().info_panel.set_autotilt_status("Auto Focusing...")
                except Exception:
                    pass
                await self._run_autofocus_with_nearest_reference(alpha_deg)
                # 记录当前帧（Global + HR）
                await self._capture_and_store(alpha_deg=alpha_deg, use_hr=False)
                await self._capture_and_store(alpha_deg=alpha_deg, use_hr=True, hr_mag_override=self.cfg.hr_magnification)
                try:
                    if hasattr(self.parent(), 'info_panel') and self.parent().info_panel:
                        self.parent().info_panel.set_autotilt_status("Done")
                        # 标记该角度已完成并推进进度
                        try:
                            self.parent().info_panel.mark_autotilt_angle_done(float(alpha_deg))
                        except Exception:
                            pass
                except Exception:
                    pass

            self.finished.emit(True, {"alpha_series": list(self.target.tilt_alpha_series)})
        except Exception as e:
            self._logger.exception(f"[AT] unexpected error: {e}")
            try:
                self.error.emit(str(e))
            except Exception:
                pass
            self.finished.emit(False, {"error": str(e)})

    async def _goto_target_snap_pose(self):
        try:
            snap = getattr(self.target, 'snapshot', None) or {}
            if not isinstance(snap, dict):
                return
            pos = None
            # 支持两种快照格式：{'stage': {'position': {...}}} 或 平铺 {'x':...}
            try:
                pos = snap.get('stage', {}).get('position')
            except Exception:
                pos = None
            if not pos and all(k in snap for k in ('x','y','z','a','b')):
                pos = {k: snap[k] for k in ('x','y','z','a','b')}
            if not pos:
                return
            await self.api.set_stage_position({'position': pos})
        except Exception:
            pass

    async def _ensure_base_magnification(self) -> Optional[float]:
        # 读取目标中已知倍率
        mag = None
        try:
            # 优先用目标最近一张 Global 的倍率
            if getattr(self.target, 'global_images', None):
                mag = float(self.target.global_images[-1].magnification)
        except Exception:
            mag = None
        if not mag or mag <= 0:
            try:
                snap = getattr(self.target, 'snapshot', None) or {}
                if isinstance(snap, dict):
                    mag = float(snap.get('illumination', {}).get('stem_magnification', 0.0))
            except Exception:
                mag = None
        if isinstance(mag, (int, float)) and mag > 0:
            try:
                await self.api.set_stem_magnification(float(mag))
            except Exception:
                pass
            return float(mag)
        # 回退：维持现状
        try:
            return float(await self.api.get_stem_magnification() or 0.0)
        except Exception:
            return None

    async def _iterative_center_on_target(self, max_iters: int = 8, pixel_tol: float = 5.0):
        # 使用“最初”的 GlobalImage（创建目标时记录的第一张），并按目标矩形裁剪为 ROI 作为模板
        template = self._get_base_global_roi()
        if template is None:
            return
        await self._iterative_center(template, max_iters=max_iters, pixel_tol=pixel_tol)

    async def _iterative_center_nearby_alpha(self, alpha_target_deg: float, max_iters: int = 8, pixel_tol: float = 50.0):
        # 基于“最初”的 GlobalImage 的 ROI，按平面假设在竖直方向进行缩放，模拟当前 alpha 的视图
        base_template = self._get_base_global_roi()
        if base_template is None:
            return
        try:
            base_alpha = float(self.target.tilt_alpha_series[0]) if getattr(self.target, 'tilt_alpha_series', None) and len(self.target.tilt_alpha_series) > 0 else 0.0
        except Exception:
            base_alpha = 0.0
        scaled = self._simulate_vertical_scaling(base_template, float(alpha_target_deg), float(base_alpha))
        template = scaled if scaled is not None else base_template
        await self._iterative_center(template, max_iters=max_iters, pixel_tol=pixel_tol)

    def _get_base_global_roi(self):
        try:
            if not getattr(self.target, 'global_images', None):
                return None
            if len(self.target.global_images) == 0:
                return None
            base = self.target.global_images[0].image
            if base is None:
                return None
            rect = getattr(self.target, 'rect', None)
            if rect and isinstance(rect, (list, tuple)) and len(rect) == 4:
                x, y, w, h = rect
                try:
                    x0 = max(0, int(x))
                    y0 = max(0, int(y))
                    x1 = min(int(x + w), int(base.shape[1]))
                    y1 = min(int(y + h), int(base.shape[0]))
                    if x1 > x0 and y1 > y0:
                        return base[y0:y1, x0:x1].copy()
                except Exception:
                    return np.ascontiguousarray(base)
            # 无 rect 时，直接使用整幅图（注意模板需不大于帧，extract_pattern 内部会处理）
            return np.ascontiguousarray(base)
        except Exception:
            return None

    def _simulate_vertical_scaling(self, arr: np.ndarray, alpha_deg: float, base_alpha_deg: float) -> Optional[np.ndarray]:
        try:
            if arr is None:
                return None
            h, w = arr.shape[0], arr.shape[1]
            import math
            ca = math.cos(math.radians(alpha_deg))
            cb = math.cos(math.radians(base_alpha_deg)) if abs(base_alpha_deg) > 1e-9 else 1.0
            if cb == 0:
                cb = 1.0
            scale = float(ca / cb)
            scale = max(0.1, min(2.0, scale))  # 简单限幅，避免极端情况
            new_h = max(1, int(round(h * scale)))
            # 逐列线性插值到 new_h
            y_old = np.linspace(0.0, float(h - 1), num=h, dtype=np.float64)
            y_new = np.linspace(0.0, float(h - 1), num=new_h, dtype=np.float64)
            out = np.empty((new_h, w), dtype=np.float64)
            for c in range(w):
                col = arr[:, c]
                colf = col.astype(np.float64, copy=False)
                out[:, c] = np.interp(y_new / scale, y_old, colf, left=colf[0], right=colf[-1])
            # 尝试保持原 dtype（若为 uint8/uint16），否则回退为 float32
            if arr.dtype == np.uint8 or arr.dtype == np.uint16:
                out = np.clip(out, 0, 65535.0)
                return out.astype(arr.dtype)
            return out.astype(np.float32)
        except Exception:
            return None

    async def _iterative_center(self, template: np.ndarray, max_iters: int = 8, pixel_tol: float = 50.0):
        for it in range(max_iters):
            frame = await self.api.acquire_frame()
            if frame is None:
                continue
            try:
                self.frame.emit(frame)
            except Exception:
                pass
            try:
                roi, (_, _), (drow, dcol) = extract_pattern(template, frame)
            except Exception:
                break
            # 估算像素尺寸
            try:
                mag = await self.api.get_stem_magnification()
                if not mag or float(mag) <= 0:
                    mag = 5.5e6
                ps = mag2ps(float(mag), (frame.shape[0], frame.shape[1]))  # Angstrom/px
                ps_h = float(ps['height']) * 1e-10
                ps_w = float(ps['width']) * 1e-10
            except Exception:
                ps_h, ps_w = 0.0, 0.0
            # 偏移像素范数判定达到阈值则结束
            if (drow ** 2 + dcol ** 2) ** 0.5 <= float(pixel_tol):
                break
            # 物理移动
            try:
                dx_m = float(dcol) * ps_w
                dy_m = -float(drow) * ps_h
                if abs(dx_m) + abs(dy_m) > 0:
                    await self.api.move_stage_relative(dx=dx_m, dy=dy_m, dz=0.0)
            except Exception:
                pass
            # 小憩
            import asyncio
            await asyncio.sleep(0.2)

    async def _capture_and_store(self, alpha_deg: float, use_hr: bool, hr_mag_override: Optional[float] = None):
        # 可选切换倍率
        restore_mag = None
        try:
            restore_mag = await self.api.get_stem_magnification()
        except Exception:
            restore_mag = None
        try:
            if use_hr:
                target_mag = float(hr_mag_override) if isinstance(hr_mag_override, (int, float)) else None
                if not target_mag or target_mag <= 0:
                    # 若未配置HR倍率，则在当前基础上保持
                    target_mag = float(restore_mag) if isinstance(restore_mag, (int, float)) else None
                if target_mag and restore_mag and abs(float(target_mag) - float(restore_mag)) > 1e-6:
                    await self.api.set_stem_magnification(float(target_mag))
        except Exception:
            pass

        # 拍摄
        frame = await self.api.acquire_frame()
        if frame is not None:
            try:
                self.frame.emit(frame)
            except Exception:
                pass
        # 快照与位姿
        snapshot = await self.api.get_snapshot()
        pose = self._extract_stage_pose(snapshot)
        # 参考 ROI：按目标 rect 从当前帧裁剪（用于后续迭代归中模板与自动聚焦参考）
        ref_roi = None
        try:
            rect = getattr(self.target, 'rect', None)
            if rect and frame is not None:
                x, y, w, h = rect
                x0 = max(0, int(x))
                y0 = max(0, int(y))
                x1 = min(int(x + w), int(frame.shape[1]))
                y1 = min(int(y + h), int(frame.shape[0]))
                if x1 > x0 and y1 > y0:
                    ref_roi = frame[y0:y1, x0:x1].copy()
        except Exception:
            ref_roi = None

        # 存入目标 Tilt 序列，并将裁剪的参考作为该角度的 ReferenceImage
        try:
            current_mag = float(await self.api.get_stem_magnification() or 0.0)
            if use_hr:
                # 更新最近一次条目的 HR 图像（若不存在条目则新建）
                if getattr(self.target, 'tilt_highres_series', None) and len(self.target.tilt_highres_series) > 0 \
                   and len(self.target.tilt_alpha_series) > 0:
                    # 用新的 HR GlobalImage 覆盖最后一项
                    from model.targets import GlobalImage
                    self.target.tilt_highres_series[-1] = GlobalImage(image=frame, magnification=current_mag)
                else:
                    # 若无条目，创建一条（HR 与 Global 相同）
                    self.target.add_tilt_entry(alpha_deg=alpha_deg,
                                               global_image=frame,
                                               global_magnification=current_mag,
                                               reference_image=(ref_roi if ref_roi is not None else frame),
                                               stage_pose=pose,
                                               snapshot=snapshot,
                                               highres_image=frame,
                                               highres_magnification=current_mag)
            else:
                # 新增一条（含占位 HR）
                self.target.add_tilt_entry(alpha_deg=alpha_deg,
                                           global_image=frame,
                                           global_magnification=current_mag,
                                           reference_image=(ref_roi if ref_roi is not None else frame),
                                           stage_pose=pose,
                                           snapshot=snapshot,
                                           highres_image=None,
                                           highres_magnification=None)
        except Exception:
            pass

        # 恢复倍率
        try:
            if use_hr and isinstance(restore_mag, (int, float)):
                await self.api.set_stem_magnification(float(restore_mag))
        except Exception:
            pass

    def _extract_stage_pose(self, snapshot: Dict[str, Any]) -> StagePose:
        try:
            pos = None
            if isinstance(snapshot, dict):
                pos = snapshot.get('stage', {}).get('position')
            if not pos:
                pos = {}
            return StagePose(
                x=float(pos.get('x', 0.0) or 0.0),
                y=float(pos.get('y', 0.0) or 0.0),
                z=float(pos.get('z', 0.0) or 0.0),
                a=float(pos.get('a', 0.0) or 0.0),
                b=float(pos.get('b', 0.0) or 0.0),
            )
        except Exception:
            return StagePose()

    async def _move_stage_alpha_deg(self, alpha_deg: float):
        # 将输入角度（度）转换/设置到 stage.a（弧度）
        try:
            state = await self.api.get_stage_position()
            if not state:
                return
            curr = state
            # 兼容 {'position': {...}} 或平铺
            pos = curr.get('position', curr)
            x, y, z = float(pos.get('x', 0.0)), float(pos.get('y', 0.0)), float(pos.get('z', 0.0))
            beta = float(pos.get('b', 0.0))
            a_rad = float(alpha_deg) * np.pi / 180.0
            new_pos = {'position': {'x': x, 'y': y, 'z': z, 'a': a_rad, 'b': beta}}
            await self.api.set_stage_position(new_pos)
        except Exception:
            pass

    def _get_current_alpha_deg_fallback(self) -> float:
        try:
            import math
            state = None
            # 无 await：用于初始记录时的兜底；允许返回0
            return 0.0
        except Exception:
            return 0.0

    async def _run_autofocus_with_nearest_reference(self, alpha_deg: float):
        try:
            # 始终使用“首帧”的参考ROI，必要时按 alpha 做竖直缩放，避免逐角度累积偏移
            scaled_image = None
            base_ref = None
            if getattr(self.target, 'tilt_reference_series', None) and len(self.target.tilt_reference_series) > 0:
                base_ref = self.target.tilt_reference_series[0]
                try:
                    base_alpha = float(self.target.tilt_alpha_series[0]) if getattr(self.target, 'tilt_alpha_series', None) and len(self.target.tilt_alpha_series) > 0 else 0.0
                except Exception:
                    base_alpha = 0.0
                # 尝试将首帧参考按照当前 alpha 做竖直缩放（与迭代归中一致的近似）
                scaled_image = self._simulate_vertical_scaling(np.ascontiguousarray(base_ref.image), float(alpha_deg), float(base_alpha)) if getattr(base_ref, 'image', None) is not None else None
            # 无法获取首帧参考时，退化到“最初的 Global ROI”
            if scaled_image is None:
                alt = self._get_base_global_roi()
                scaled_image = alt if alt is not None else None
            # 将该参考临时追加到 target.reference_images 末尾，供自动聚焦使用
            if scaled_image is not None:
                try:
                    from model.targets import ReferenceImage, StagePose
                    self.target.reference_images.append(ReferenceImage(image=scaled_image, pose=StagePose()))
                except Exception:
                    pass
            from autofocus.controller import AutofocusController
            from autofocus.config import AutofocusSettings
            af_cfg = AutofocusSettings.from_dict(self.af_settings_dict)
            af = AutofocusController(self.api, self.target, af_cfg, parent=None)
            # 直接运行一次（同步等待）
            # await af._coarse_search()
            # await af._fine_search()
            await af._run()
        except Exception:
            pass

