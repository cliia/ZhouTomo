#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from autofocus.config import AutofocusSettings
from autofocus.microscope_api import MicroscopeAPI
from model.targets import TargetModel
from src.utils import get_definition, mag2ps, is_monotonic  # 你的清晰度评价方法与像素尺寸/单调性
from src.normxcorr2 import extract_pattern
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
import logging


class AutofocusController(QObject):
    progress = pyqtSignal(int, str)
    frame = pyqtSignal(object)
    finished = pyqtSignal(bool, dict)
    error = pyqtSignal(str)
    # 清晰度曲线（实时）：defocus(m), definition(value), step_idx(从1开始)
    focusMetric = pyqtSignal(float, float, int)
    # 复刻旧版导出：原始与平滑曲线（单位：m），以及ROI样张
    focusCurvesUpdated = pyqtSignal(object, object, object, object)
    sampleROI = pyqtSignal(object)

    def __init__(self, api: MicroscopeAPI, target: TargetModel, settings: AutofocusSettings, parent=None):
        super().__init__(parent)
        self.api = api
        self.target = target
        self.cfg = settings
        self._cancel = False
        self._logger = logging.getLogger("autofocus.controller")

        # 记录曲线
        self.defocus_list = []
        self.definition_list = []
        self._defocus_cumulative = 0.0  # ! Unit: m, 累计相对离焦，用作x轴
        self._cached_ref_image = None

        # get definition 方法
        self.DEFMETHOD = 'VGR'

    def cancel(self):
        self._cancel = True

    def start(self):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            self._logger.info("[AF] start: scheduling _run on running loop")
            loop.create_task(self._run())
        except RuntimeError:
            # 若当前无运行中的事件循环（异常场景），尽量同步执行一次以避免无反应
            self._logger.warning("[AF] no running loop; creating a temporary loop to run _run()")
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._run())
            finally:
                loop.close()

    async def _run(self):
        try:
            self._logger.info("[AF] _run entered")
            # 粗搜（OFRS）
            self.progress.emit(1, "Coarse search (OFRS)")
            self._logger.info(f"[AF] coarse: step_nm={self.cfg.ofrs_step_nm}, max_iters={self.cfg.max_iterations}")
            ok = await self._coarse_search()
            if not ok:
                self._logger.warning("[AF] coarse search failed")
                return self.finished.emit(False, {"reason": "coarse-failed"})
            if self._cancel:
                self._logger.info("[AF] cancelled after coarse")
                return self.finished.emit(False, {"reason": "cancelled"})

            # 跳过细搜：直接在粗搜结果中选择 definition 最大的 defocus 并设置
            self.progress.emit(2, "Select best focus (from OFRS)")
            try:
                if len(self.definition_list) > 0 and len(self.defocus_list) == len(self.definition_list):
                    import numpy as _np
                    idx_best = int(_np.argmax(_np.asarray(self.definition_list, dtype=float)))
                    best_defocus = float(self.defocus_list[idx_best])
                    self._logger.info(f"[AF] best-from-coarse: idx={idx_best}, defocus={best_defocus:.6e} m, def={float(self.definition_list[idx_best]):.3f}")
                    # 先尝试绝对设置；失败则回退相对设置
                    set_ok = False
                    try:
                        curr = await self.api.get_defocus()
                    except Exception:
                        curr = None
                    try:
                        set_ok = await self.api.set_defocus(best_defocus)
                        if set_ok and isinstance(curr, (int, float)):
                            self._defocus_cumulative += float(best_defocus - float(curr))
                    except Exception:
                        set_ok = False
                    if not set_ok:
                        try:
                            curr = await self.api.get_defocus()
                        except Exception:
                            curr = None
                        if isinstance(curr, (int, float)):
                            delta = float(best_defocus) - float(curr)
                            ok_rel = await self.api.set_defocus_relative(delta)
                            if ok_rel:
                                self._defocus_cumulative += float(delta)
                                set_ok = True
                    self._logger.info(f"[AF] set best defocus result: set_ok={set_ok}")
                else:
                    self._logger.warning("[AF] no coarse results to choose best focus from")
            except Exception as e:
                self._logger.warning(f"[AF] failed to set best-from-coarse defocus: {e}")
            if self._cancel:
                self._logger.info("[AF] cancelled after coarse-best-set")
                return self.finished.emit(False, {"reason": "cancelled"})

            # 最终确认
            self.progress.emit(3, "Confirm")
            frame = await self.api.acquire_frame()
            if frame is not None:
                self.frame.emit(frame)
            self._logger.info("[AF] finished successfully")
            self.finished.emit(True, {"defocus_curve": self.defocus_list, "definition_curve": self.definition_list})
        except Exception as e:
            self._logger.exception(f"[AF] unexpected error: {e}")
            self.error.emit(str(e))
            self.finished.emit(False, {"error": str(e)})

    def _get_reference_image(self):
        # 取最近一次的参考图像
        try:
            if self._cached_ref_image is not None:
                return self._cached_ref_image
            refs = getattr(self.target, 'reference_images', None)
            if refs and len(refs) > 0:
                self._cached_ref_image = refs[-1].image
                return self._cached_ref_image
        except Exception:
            pass
        return None

    async def _center_by_reference(self, frame: np.ndarray) -> Optional[np.ndarray]:
        # 基于参考图像进行归中，返回用于清晰度评价的ROI；若失败返回None
        ref = self._get_reference_image()
        if ref is None or frame is None:
            return None
        try:
            # 互相关求位移（像素）并裁剪ROI
            roi, (_, _), (drow, dcol) = extract_pattern(ref, frame)
        except Exception as e:
            try:
                self._logger.warning(f"[AF] extract_pattern failed: {e}")
            except Exception:
                pass
            return None

        # 保护：异常大位移（相对帧大小）直接拒绝，以避免误匹配导致移动方向随机
        try:
            h, w = int(frame.shape[0]), int(frame.shape[1])
            if abs(float(drow)) > 0.45 * h or abs(float(dcol)) > 0.45 * w:
                try:
                    self._logger.warning(f"[AF] outlier shift rejected: drow={drow:.1f}, dcol={dcol:.1f}, frame=({h},{w})")
                except Exception:
                    pass
                # 仍向UI发送ROI以便观察，但不移动载台
                try:
                    if roi is not None:
                        self.sampleROI.emit(roi)
                except Exception:
                    pass
                return roi
        except Exception:
            pass

        # 估算像素尺寸（米/像素）
        try:
            # 优先从目标快照读取放大倍数
            mag = None
            snap = getattr(self.target, 'snapshot', None) or {}
            if isinstance(snap, dict):
                try:
                    mag = float(snap.get('illumination', {}).get('stem_magnification', None))
                except Exception:
                    mag = None
            if not mag or mag <= 0:
                mag = await self.api.get_stem_magnification()
            if not mag or mag <= 0:
                mag = 5.5e6
            ps = mag2ps(float(mag), (frame.shape[0], frame.shape[1]))  # Angstrom/px
            # 转米/px
            ps_h = float(ps['height']) * 1e-10
            ps_w = float(ps['width']) * 1e-10
        except Exception as e:
            try:
                self._logger.warning(f"[AF] mag2ps failed: {e}")
            except Exception:
                pass
            return roi  # 仍返回ROI用于评价，但不移动载台

        # 像素偏移 -> 物理位移（米），并相对移动载台
        try:
            dx_m = float(dcol) * ps_w
            dy_m = -float(drow) * ps_h  # 行向下为正 -> 物理y负方向
            if abs(dx_m) + abs(dy_m) > 0:
                await self.api.move_stage_relative(dx=dx_m, dy=dy_m, dz=0.0)
        except Exception as e:
            try:
                self._logger.warning(f"[AF] move_stage_relative failed: {e}")
            except Exception:
                pass
        try:
            if roi is not None:
                self.sampleROI.emit(roi)
        except Exception:
            pass
        return roi

    def _emit_focus_curves(self):
        try:
            raw_x_m = list(map(float, self.defocus_list))
            raw_y = list(map(float, self.definition_list))
            # 平滑曲线（仿旧策略，内部 nm 单位）
            if len(raw_x_m) >= 2:
                x_nm = np.asarray(raw_x_m, dtype=float) * 1e9
                y = np.asarray(raw_y, dtype=float)
                xmin, xmax = float(np.min(x_nm)), float(np.max(x_nm))
                x_eps = 1.0  # nm
                grid = np.arange(np.ceil(xmin * 10.0) / 10.0, np.floor(xmax * 10.0) / 10.0, x_eps)
                if grid.size < 3:
                    grid = np.linspace(xmin, xmax if xmax > xmin else xmin + x_eps, num=3)
                try:
                    order = np.argsort(x_nm)
                    f = interp1d(x_nm[order], y[order], kind='linear', bounds_error=False, fill_value=(y[order][0], y[order][-1]))
                    yg = f(grid)
                    ys_smooth = gaussian_filter1d(yg, sigma=3, mode='nearest')
                except Exception:
                    grid = x_nm
                    ys_smooth = y
                smooth_x_m = (grid * 1e-9).tolist()
                smooth_y = list(map(float, ys_smooth))
            else:
                smooth_x_m = raw_x_m
                smooth_y = raw_y
            self.focusCurvesUpdated.emit(raw_x_m, raw_y, smooth_x_m, smooth_y)
        except Exception:
            pass

    async def _coarse_search(self) -> bool:
        step = max(1.0, float(self.cfg.ofrs_step_nm)) * 1e-9  # m
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
                # 记录并继续尝试下一步
                try:
                    self.error.emit("acquire_frame returned None in coarse search")
                except Exception:
                    pass
                import asyncio
                await asyncio.sleep(0.2)
                continue
            self.frame.emit(frame)
            # 基于参考图像进行归中，返回ROI用于清晰度评价
            roi = await self._center_by_reference(frame)
            # 清晰度（在当前 defocus 位置测量）
            try:
                img4def = roi if roi is not None else frame
                definition, _ = get_definition(img4def, method=self.DEFMETHOD)
            except Exception as ge:
                self._logger.warning(f"[AF] get_definition failed at coarse iter {it}: {ge}")
                definition = 0.0
            # 记录当前真实 defocus（若可获取），否则用累计量
            curr_defocus = await self.api.get_defocus()
            x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(self._defocus_cumulative)
            self.defocus_list.append(x_defocus)
            self.definition_list.append(float(definition))
            self.focusMetric.emit(x_defocus, float(definition), len(self.definition_list))
            self._logger.info(f"[AF] coarse iter {it}: defocus={x_defocus:.6e} m, def={definition:.3f}")
            # 复刻旧版：导出曲线
            self._emit_focus_curves()

            # 使用与旧策略一致的优化器（内部以 nm 为单位）给出“绝对”离焦建议
            try:
                defocus_list_nm = [float(v) * 1e9 for v in self.defocus_list]
                suggest_nm = _StrategyLikeOptimizer.suggest_next_nm(
					stage='OFRS',
					defocus_list_nm=defocus_list_nm,
					definition_list=self.definition_list,
					ofrs_step_nm=max(1.0, float(self.cfg.ofrs_step_nm)),
					frs_step_nm=max(0.5, float(self.cfg.frs_step_nm)),
					curr_defocus_nm=float(x_defocus) * 1e9,
				)
            except Exception as e:
                suggest_nm = None
                try:
                    self._logger.warning(f"[AF] optimizer suggest_next_nm failed (coarse): {e}")
                except Exception:
                    pass

            # 优先设置“绝对”离焦（单位：m）；若无建议或失败，则回退到相对调整
            set_ok = False
            delta = direction * step  # fallback 相对步进（m）
            if isinstance(suggest_nm, (int, float)):
                try:
                    suggest_m = float(suggest_nm) * 1e-9
                    curr = await self.api.get_defocus()
                    curr_val = float(curr) if isinstance(curr, (int, float)) else None
                    if curr_val is not None:
                        delta = suggest_m - curr_val
                        set_ok = await self.api.set_defocus(suggest_m)
                        if set_ok:
                            self._defocus_cumulative += float(delta)
                except Exception:
                    set_ok = False
            if not set_ok:
                ok_rel = await self.api.set_defocus_relative(delta)
                if ok_rel:
                    self._defocus_cumulative += float(delta)
                set_ok = ok_rel
            # 设置后即时读取一次，确认值是否变化
            try:
                new_defocus = await self.api.get_defocus()
                self._logger.info(f"[AF] coarse iter {it}: delta={delta:.6e} m, set_ok={set_ok}, now={float(new_defocus) if isinstance(new_defocus, (int,float)) else None}")
            except Exception:
                self._logger.info(f"[AF] coarse iter {it}: delta={delta:.6e} m, set_ok={set_ok}")
            # 粗搜早停：按 defocus 排序后的 definition 非单调时跳出
            try:
                if len(self.defocus_list) >= 3:
                    ind = np.argsort(np.array(self.defocus_list))
                    sdl = list(np.array(self.definition_list)[ind])
                    if not is_monotonic(sdl):
                        break
            except Exception:
                pass
            # 小憩，给硬件反应时间
            import asyncio
            await asyncio.sleep(0.2)
        return True

    async def _fine_search(self) -> bool:
        step = max(0.5, float(self.cfg.frs_step_nm)) * 1e-9  # m
        max_iters = max(1, int(self.cfg.max_iterations))

        for it in range(max_iters):
            if self._cancel:
                return False
            frame = await self.api.acquire_frame()
            if frame is None:
                try:
                    self.error.emit("acquire_frame returned None in fine search")
                except Exception:
                    pass
                import asyncio
                await asyncio.sleep(0.2)
                continue
            self.frame.emit(frame)
            roi = await self._center_by_reference(frame)
            try:
                img4def = roi if roi is not None else frame
                definition, _ = get_definition(img4def, method=self.DEFMETHOD)
            except Exception as ge:
                self._logger.warning(f"[AF] get_definition failed at fine iter {it}: {ge}")
                definition = 0.0
            curr_defocus = await self.api.get_defocus()
            x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(self._defocus_cumulative)
            self.defocus_list.append(x_defocus)
            self.definition_list.append(float(definition))
            self.focusMetric.emit(x_defocus, float(definition), len(self.definition_list))
            self._emit_focus_curves()

            # 用更小步长，采用平滑插值优化器
            try:
                curr_defocus = await self.api.get_defocus()
            except Exception:
                curr_defocus = None
            x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(self._defocus_cumulative)
            try:
                defocus_list_nm = [float(v) * 1e9 for v in self.defocus_list]
                suggest_nm = _StrategyLikeOptimizer.suggest_next_nm(
					stage='FRS',
					defocus_list_nm=defocus_list_nm,
					definition_list=self.definition_list,
					ofrs_step_nm=max(1.0, float(self.cfg.ofrs_step_nm)),
					frs_step_nm=max(0.5, float(self.cfg.frs_step_nm)),
					curr_defocus_nm=float(x_defocus) * 1e9,
				)
            except Exception as e:
                suggest_nm = None
                try:
                    self._logger.warning(f"[AF] optimizer suggest_next_nm failed (fine): {e}")
                except Exception:
                    pass
            # 优先设置“绝对”离焦（单位：m）；若无建议或失败，则回退到相对调整
            set_ok = False
            delta = step
            if isinstance(suggest_nm, (int, float)):
                try:
                    suggest_m = float(suggest_nm) * 1e-9
                    curr = await self.api.get_defocus()
                    if isinstance(curr, (int, float)):
                        delta = suggest_m - float(curr)
                        set_ok = await self.api.set_defocus(suggest_m)
                        if set_ok:
                            self._defocus_cumulative += float(delta)
                except Exception:
                    set_ok = False
            if not set_ok:
                ok_rel = await self.api.set_defocus_relative(delta)
                if ok_rel:
                    self._defocus_cumulative += float(delta)
                set_ok = ok_rel
            try:
                new_defocus = await self.api.get_defocus()
                self._logger.info(f"[AF] fine iter {it}: delta={delta:.6e} m, set_ok={set_ok}, now={float(new_defocus) if isinstance(new_defocus, (int,float)) else None}")
            except Exception:
                self._logger.info(f"[AF] fine iter {it}: delta={delta:.6e} m, set_ok={set_ok}")
            import asyncio
            await asyncio.sleep(0.2)
        return True


class _GradientSmoothingOptimizer:
    @staticmethod
    def suggest_next(stage: str,
                     defocus_list: list,
                     definition_list: list,
                     ofrs_step_m: float,
                     frs_step_m: float,
                     curr_defocus: float,
                     logger: Optional[logging.Logger] = None) -> Optional[float]:
        try:
            n = len(defocus_list)
            if n == 0:
                return None
            x = np.array(defocus_list, dtype=float)
            y = np.array(definition_list, dtype=float)
            # 边界：数据不足
            if n == 1:
                direction = -1.0 if x[-1] >= 0 else 1.0
                step = ofrs_step_m if stage == 'OFRS' else frs_step_m
                return float(x[-1] + direction * step)
            if n == 2 and stage == 'OFRS':
                # 旧实现思想：比较两点，沿更优点的方向继续
                try:
                    grad = (y[1] - y[0]) / (x[1] - x[0] if x[1] != x[0] else 1.0)
                except Exception:
                    grad = (y[1] - y[0])
                direction = 1.0 if grad >= 0 else -1.0
                start_point = x[1] if y[1] >= y[0] else x[0]
                return float(start_point + direction * ofrs_step_m)

            # 插值 + 平滑
            order = np.argsort(x)
            xs = x[order]
            ys = y[order]
            # 网格步长：依据当前阶段步长
            dx = max(1e-10, ofrs_step_m if stage == 'OFRS' else frs_step_m)
            xmin, xmax = float(np.min(xs)), float(np.max(xs))
            if xmax - xmin < dx:
                xmax = xmin + dx
            grid = np.arange(xmin, xmax, dx)
            if grid.size < 3:
                # 扩展为至少3点
                grid = np.linspace(xmin, xmax, num=3)
            try:
                f = interp1d(xs, ys, kind='linear', bounds_error=False, fill_value=(ys[0], ys[-1]))
                yg = f(grid)
            except Exception:
                # 回退到最近点
                idx = np.argmin(np.abs(xs - curr_defocus))
                center = xs[idx]
                step = ofrs_step_m if stage == 'OFRS' else frs_step_m
                direction = 1.0 if (xs[-1] - xs[0]) >= 0 else -1.0
                return float(center + direction * step)

            ys_smooth = gaussian_filter1d(yg, sigma=3, mode='nearest')
            # 中心差分梯度（与旧版一致的相对近似）
            g = (ys_smooth[2:] - ys_smooth[:-2]) / (grid[2:] - grid[:-2])
            grid_mid = grid[1:-1]
            if g.size == 0:
                step = ofrs_step_m if stage == 'OFRS' else frs_step_m
                return float(xs[-1] + step)
            idx = int(np.argmin(np.abs(grid_mid - float(curr_defocus))))
            grad_here = float(g[idx])
            if stage == 'OFRS':
                direction = 1.0 if grad_here >= 0 else -1.0
                return float(xs[-1] + direction * ofrs_step_m)
            else:
                delta = grad_here * frs_step_m * 5.0
                # 限幅，避免异常大步长
                limit = 5.0 * frs_step_m
                if abs(delta) > limit:
                    delta = limit if delta > 0 else -limit
                return float(xs[-1] + delta)
        except Exception as e:
            try:
                if logger:
                    logger.warning(f"[AF] optimizer internal error: {e}")
            except Exception:
                pass
            return None




class _StrategyLikeOptimizer:
    """
    更贴近旧版 strategy/ztStemAutoFocus.py 中 AutoFocusOptimizer 的行为：
    - 输入输出均使用 nm 作为 defocus 单位
    - OFRS 阶段：
        * n<=1：沿符号反向推进一步
        * n==2：根据两点斜率与更优点决定方向与起点
        * n>=3：线性插值 + 高斯平滑，再用局部梯度符号决定方向
    - FRS 阶段：在当前点处取平滑梯度，delta = grad * frs_step_nm * 5，带限幅
    """
    @staticmethod
    def suggest_next_nm(stage: str,
                        defocus_list_nm: list,
                        definition_list: list,
                        ofrs_step_nm: float,
                        frs_step_nm: float,
                        curr_defocus_nm: float) -> Optional[float]:
        try:
            n = len(defocus_list_nm)
            if n == 0:
                return None
            x = np.asarray(defocus_list_nm, dtype=float)
            y = np.asarray(definition_list, dtype=float)

            if n == 1:
                direction = -1.0 if x[-1] >= 0 else 1.0
                step = ofrs_step_nm if stage == 'OFRS' else frs_step_nm
                return float(x[-1] + direction * step)

            if n == 2 and stage == 'OFRS':
                try:
                    grad = (y[1] - y[0]) / (x[1] - x[0] if x[1] != x[0] else 1.0)
                except Exception:
                    grad = (y[1] - y[0])
                direction = 1.0 if grad >= 0 else -1.0
                start_point = x[1] if y[1] >= y[0] else x[0]
                return float(start_point + direction * ofrs_step_nm)

            # n>=3 或 FRS：按旧策略的网格与梯度计算
            order = np.argsort(x)
            xs = x[order]
            ys = y[order]
            x_eps = 1.0  # nm
            xmin, xmax = float(np.min(xs)), float(np.max(xs))
            grid = np.arange(np.ceil(xmin * 10.0) / 10.0, np.floor(xmax * 10.0) / 10.0, x_eps)
            if grid.size < 3:
                grid = np.linspace(xmin, xmax if xmax > xmin else xmin + x_eps, num=3)
            try:
                f = interp1d(xs, ys, kind='linear', bounds_error=False, fill_value=(ys[0], ys[-1]))
                yg = f(grid)
            except Exception:
                step = ofrs_step_nm if stage == 'OFRS' else frs_step_nm
                direction = 1.0 if (xs[-1] - xs[0]) >= 0 else -1.0
                return float(xs[-1] + direction * step)

            ys_smooth = gaussian_filter1d(yg, sigma=3, mode='nearest')
            gradient_def = (ys_smooth[2:] - ys_smooth[:-2]) / x_eps
            if gradient_def.size == 0:
                step = ofrs_step_nm if stage == 'OFRS' else frs_step_nm
                return float(xs[-1] + step)
            # 旧代码用 grid[:-2] 接近当前 defocus 位置
            idx = int(np.argmin(np.abs(grid[:-2] - float(curr_defocus_nm))))
            grad_here = float(gradient_def[idx])

            if stage == 'OFRS':
                direction = 1.0 if grad_here >= 0 else -1.0
                return float(xs[-1] + direction * ofrs_step_nm)
            else:
                delta = grad_here * frs_step_nm * 5.0
                limit = 5.0 * frs_step_nm
                if abs(delta) > limit:
                    delta = limit if delta > 0 else -limit
                return float(xs[-1] + delta)
        except Exception:
            return None
