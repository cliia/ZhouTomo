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
            alpha_now = await self._get_current_alpha_deg()
            await self._capture_and_store(alpha_deg=alpha_now, use_hr=False)

            # 4) 放大拍HR作为序列首张（若提供hr倍率，或沿用当前倍率）
            alpha_now = await self._get_current_alpha_deg()
            await self._capture_and_store(alpha_deg=alpha_now, use_hr=True, hr_mag_override=self.cfg.hr_magnification)

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
                # 稳定性检测：等待3秒再采一张，若偏移>10px则重复归中，最多重复3次
                await self._stability_and_recenter(alpha_deg, max_checks=3, wait_seconds=3.0, pixel_tol=10.0)
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
        # 使用 GlobalImage 作为初始模板（按目标矩形裁剪），用于倾转找回的基准
        template = self._get_base_global_roi()
        if template is None:
            return
        template = self._prepare_template_roi(template)
        await self._iterative_center(template, max_iters=max_iters, pixel_tol=pixel_tol)

    async def _iterative_center_nearby_alpha(self, alpha_target_deg: float, max_iters: int = 8, pixel_tol: float = 50.0):
        # 基于“最初”的 GlobalImage 的 ROI，做中心锚定竖直缩放以模拟当前 alpha 的视图
        base_template = self._get_base_global_roi()
        if base_template is None:
            return
        try:
            base_alpha = float(self.target.tilt_alpha_series[0]) if getattr(self.target, 'tilt_alpha_series', None) and len(self.target.tilt_alpha_series) > 0 else 0.0
        except Exception:
            base_alpha = 0.0
        scaled = self._simulate_vertical_scaling(base_template, float(alpha_target_deg), float(base_alpha))
        template = scaled if scaled is not None else base_template
        # 对模板执行一次直方图均衡（可选），提高相关匹配的稳健性
        try:
            import numpy as np
            arr = np.asarray(template)
            if arr.dtype != np.float32 and arr.dtype != np.float64:
                arr = arr.astype(np.float32)
            # 简单对比度拉伸（1%-99%分位）
            vmin = float(np.percentile(arr, 1))
            vmax = float(np.percentile(arr, 99))
            if np.isfinite(vmin) and np.isfinite(vmax) and vmax > vmin:
                arr = (arr - vmin) * (1.0 / (vmax - vmin))
                arr = np.clip(arr, 0.0, 1.0)
            template = self._prepare_template_roi(arr)
        except Exception:
            pass
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

    async def _get_base_reference_roi(self) -> Optional[np.ndarray]:
        """获取基础参考ROI：优先倾转序列首个 ReferenceImage，其次目标级 ReferenceImage；
        若都不存在，则从当前帧按 rect 裁剪并缓存为 ReferenceImage。"""
        try:
            # 1) 倾转序列首个 ReferenceImage
            if getattr(self.target, 'tilt_reference_series', None) and len(self.target.tilt_reference_series) > 0:
                img = self.target.tilt_reference_series[0].image
                if img is not None:
                    return self._prepare_template_roi(np.ascontiguousarray(img))
            # 2) 目标级 ReferenceImage 列表
            if getattr(self.target, 'reference_images', None) and len(self.target.reference_images) > 0:
                img = self.target.reference_images[0].image
                if img is not None:
                    return self._prepare_template_roi(np.ascontiguousarray(img))
            # 3) 动态建立：采一帧并按 rect 裁剪
            frame = await self.api.acquire_frame()
            if frame is None:
                return None
            rect = getattr(self.target, 'rect', None)
            ref_roi = None
            if rect and isinstance(rect, (list, tuple)) and len(rect) == 4:
                x, y, w, h = rect
                try:
                    x0 = max(0, int(x)); y0 = max(0, int(y))
                    x1 = min(int(x + w), int(frame.shape[1])); y1 = min(int(y + h), int(frame.shape[0]))
                    if x1 > x0 and y1 > y0:
                        ref_roi = frame[y0:y1, x0:x1].copy()
                except Exception:
                    ref_roi = None
            if ref_roi is None:
                ref_roi = np.ascontiguousarray(frame)
            # 缓存为 ReferenceImage
            try:
                snap = await self.api.get_snapshot()
                pose = self._extract_stage_pose(snap)
                from model.targets import ReferenceImage
                self.target.reference_images.append(ReferenceImage(image=ref_roi, pose=pose))
            except Exception:
                pass
            return self._prepare_template_roi(ref_roi)
        except Exception:
            return None

    def _simulate_vertical_scaling(self, arr: np.ndarray, alpha_deg: float, base_alpha_deg: float) -> Optional[np.ndarray]:
        """仅对竖直方向按 cos(alpha) 比例缩放，但以图像中心为锚点，并保持输出高度不变，
        以避免因以顶边为原点插值导致的高角时向上漂移。"""
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
            scale = max(0.1, min(2.0, scale))  # 限幅

            # 以中心对齐的插值：输出高度与输入相同，避免模板尺寸变化引入偏差
            cy = (h - 1) * 0.5
            y_old = np.linspace(0.0, float(h - 1), num=h, dtype=np.float64)
            y_out = np.arange(h, dtype=np.float64)
            # 中心对齐映射：y_in = (y_out - cy)/scale + cy
            y_in = (y_out - cy) / scale + cy
            y_in = np.clip(y_in, 0.0, float(h - 1))

            out = np.empty((h, w), dtype=np.float64)
            for c in range(w):
                col = arr[:, c]
                colf = col.astype(np.float64, copy=False)
                out[:, c] = np.interp(y_in, y_old, colf, left=colf[0], right=colf[-1])

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

    async def _stability_and_recenter(self, alpha_target_deg: float, max_checks: int = 3, wait_seconds: float = 3.0, pixel_tol: float = 10.0):
        """归中完成后等待若干秒再次采样，若相对模板的像素偏移超过阈值则再次归中，直至稳定或达到上限。"""
        try:
            # 使用模拟到当前角度的 Global ROI 作为稳定性检测模板
            template = self._get_simulated_global_roi_for_alpha(alpha_target_deg)
            if template is None:
                return
            import asyncio
            checks = 0
            while checks < int(max_checks) and not self._cancel:
                checks += 1
                # 等待稳定
                try:
                    self._logger.info(f"[AT] stability check {checks}/{max_checks}: waiting {float(wait_seconds)}s before sampling")
                except Exception:
                    pass
                await asyncio.sleep(float(wait_seconds))
                # 采样设置超时，避免 acquire_cardinal 阻塞过久
                try:
                    frame = await asyncio.wait_for(self.api.acquire_frame(), timeout=2.0)
                except asyncio.TimeoutError:
                    try:
                        self._logger.warning("[AT] stability acquire_frame timeout (2s); retrying next check")
                    except Exception:
                        pass
                    continue
                if frame is None:
                    try:
                        self._logger.warning("[AT] stability acquire_frame returned None; retrying next check")
                    except Exception:
                        pass
                    continue
                try:
                    roi, (_, _), (drow, dcol) = extract_pattern(template, frame)
                except Exception:
                    # 若匹配失败，尝试再次归中一次
                    await self._iterative_center_nearby_alpha(alpha_target_deg=alpha_target_deg, max_iters=4, pixel_tol=pixel_tol)
                    continue
                drift = float((drow ** 2 + dcol ** 2) ** 0.5)
                try:
                    self._logger.info(f"[AT] stability drift=\u0394px {drift:.2f} (tol={float(pixel_tol):.2f})")
                except Exception:
                    pass
                if drift <= float(pixel_tol):
                    break
                # 重新归中一次
                await self._iterative_center_nearby_alpha(alpha_target_deg=alpha_target_deg, max_iters=6, pixel_tol=pixel_tol)
        except Exception:
            pass

    def _get_simulated_global_roi_for_alpha(self, alpha_target_deg: float) -> Optional[np.ndarray]:
        try:
            base_template = self._get_base_global_roi()
            if base_template is None:
                return None
            try:
                base_alpha = float(self.target.tilt_alpha_series[0]) if getattr(self.target, 'tilt_alpha_series', None) and len(self.target.tilt_alpha_series) > 0 else 0.0
            except Exception:
                base_alpha = 0.0
            scaled = self._simulate_vertical_scaling(base_template, float(alpha_target_deg), float(base_alpha))
            templ = scaled if scaled is not None else base_template
            return self._prepare_template_roi(templ)
        except Exception:
            return None

    def _prepare_template_roi(self, arr: np.ndarray) -> np.ndarray:
        """将参考图像裁剪为适中的中心 ROI，避免模板过大导致相关匹配过慢。
        默认最大尺寸设为 512x512。"""
        try:
            import numpy as np
            a = np.asarray(arr)
            if a.ndim == 3:
                a = a.mean(axis=2)
            h, w = int(a.shape[0]), int(a.shape[1])
            max_side = 512
            th = min(h, max_side)
            tw = min(w, max_side)
            if th == h and tw == w:
                return np.ascontiguousarray(a)
            cy = h // 2
            cx = w // 2
            y0 = max(0, cy - th // 2)
            x0 = max(0, cx - tw // 2)
            y1 = min(h, y0 + th)
            x1 = min(w, x0 + tw)
            return np.ascontiguousarray(a[y0:y1, x0:x1])
        except Exception:
            return arr

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

    async def _get_current_alpha_deg(self) -> float:
        """读取当前 stage.a（弧度）并转换为度，失败返回 0.0。"""
        try:
            state = await self.api.get_stage_position()
            pos = state.get('position', state) if isinstance(state, dict) else {}
            a_rad = float(pos.get('a', 0.0) or 0.0)
            return float(a_rad * 180.0 / np.pi)
        except Exception:
            # 回退：尝试从快照读取
            try:
                snap = await self.api.get_snapshot()
                pos = (snap or {}).get('stage', {}).get('position', {}) if isinstance(snap, dict) else {}
                a_rad = float(pos.get('a', 0.0) or 0.0)
                return float(a_rad * 180.0 / np.pi)
            except Exception:
                return 0.0

    async def _run_autofocus_with_nearest_reference(self, alpha_deg: float):
        try:
            # 使用 Reference image 作为自动聚焦对象：选择与当前角度最近邻的参考图
            scaled_image = None
            base_ref_img = None
            # 1) 从倾转序列中找离 alpha_deg 最近的 ReferenceImage
            try:
                if getattr(self.target, 'tilt_alpha_series', None) and getattr(self.target, 'tilt_reference_series', None):
                    alphas = list(self.target.tilt_alpha_series)
                    refs = list(self.target.tilt_reference_series)
                    if len(alphas) == len(refs) and len(alphas) > 0:
                        import numpy as np
                        arr_a = np.asarray(alphas, dtype=float)
                        idx = int(np.argmin(np.abs(arr_a - float(alpha_deg))))
                        base_ref_img = getattr(refs[idx], 'image', None)
            except Exception:
                base_ref_img = None
            # 2) 回退：目标级 Reference 列表（用最近一次）
            if base_ref_img is None and getattr(self.target, 'reference_images', None):
                try:
                    base_ref_img = self.target.reference_images[-1].image if len(self.target.reference_images) > 0 else None
                except Exception:
                    base_ref_img = None
            # 3) 仍无参考：动态建立基础 Reference ROI
            if base_ref_img is None:
                base_ref_img = await self._get_base_reference_roi()
            # 将参考按当前角度模拟（中心锚定竖直缩放，基础角取序列首个）
            if base_ref_img is not None:
                try:
                    try:
                        base_alpha = float(self.target.tilt_alpha_series[0]) if getattr(self.target, 'tilt_alpha_series', None) and len(self.target.tilt_alpha_series) > 0 else 0.0
                    except Exception:
                        base_alpha = 0.0
                    scaled_image = self._simulate_vertical_scaling(np.ascontiguousarray(base_ref_img), float(alpha_deg), float(base_alpha))
                except Exception:
                    scaled_image = None
            # 将该参考临时追加到 target.reference_images 末尾，供自动聚焦使用
            if scaled_image is not None:
                try:
                    from model.targets import ReferenceImage, StagePose
                    self.target.reference_images.append(ReferenceImage(image=scaled_image, pose=StagePose()))
                except Exception:
                    pass
            from autofocus.config import AutofocusSettings
            af_cfg = AutofocusSettings.from_dict(self.af_settings_dict)
            algo = str(self.af_settings_dict.get('algorithm', 'basic')).lower()
            # 根据 main_window 中的设定选择自动聚焦算法
            if algo == 'advanced':
                from autofocus.controller_advanced import AutofocusGoldenSearchController
                af = AutofocusGoldenSearchController(self.api, self.target, af_cfg, parent=self.parent())
            else:
                from autofocus.controller import AutofocusController
                af = AutofocusController(self.api, self.target, af_cfg, parent=self.parent())

            # 可选：桥接信号到 UI（若存在），便于在自动倾转过程中也可视化聚焦曲线/ROI
            try:
                parent = self.parent()
                if parent is not None:
                    if hasattr(parent, 'image_panel') and parent.image_panel:
                        af.frame.connect(lambda arr: parent.image_panel.set_image_array(arr))
                    if hasattr(parent, 'info_panel') and parent.info_panel:
                        if hasattr(parent.info_panel, 'update_focus_curves'):
                            af.focusCurvesUpdated.connect(lambda rx, ry, sx, sy: parent.info_panel.update_focus_curves(rx, ry, sx, sy))
                        if hasattr(parent.info_panel, 'set_sample_roi'):
                            af.sampleROI.connect(parent.info_panel.set_sample_roi)
                    # 复用主窗口的聚焦点追加方法（含单位转换/节流逻辑）
                    if hasattr(parent, '_on_focus_metric'):
                        af.focusMetric.connect(parent._on_focus_metric)
            except Exception:
                pass

            # 直接运行一次（同步等待）
            await af._run()
        except Exception:
            pass

