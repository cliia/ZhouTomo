#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Tuple, Dict
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from autofocus.config import AutofocusSettings
from autofocus.microscope_api import MicroscopeAPI
from model.targets import TargetModel
from src.utils import get_definition, mag2ps
from src.normxcorr2 import extract_pattern
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
import logging
import asyncio


class AutofocusGoldenSearchController(QObject):
    """
    更先进的自动对焦控制器：
    - 阶段1：自适应括域（bracketing），确保存在 a<b<c 且 f(b)>=f(a), f(b)>=f(c)
    - 阶段2：在括域内执行黄金分割搜索以最大化清晰度指标
    - 阶段3：对最优邻域做抛物线细化估计顶点，并设置最终离焦

    说明：
    - 离焦单位统一为 米（m），外部 API 亦使用该单位
    - 清晰度评价复用 `src.utils.get_definition`（默认 method='VGR'）
    - 提供与旧控制器一致的信号，便于 UI 复用
    """

    progress = pyqtSignal(int, str)
    frame = pyqtSignal(object)
    finished = pyqtSignal(bool, dict)
    error = pyqtSignal(str)
    # 清晰度曲线（实时）：defocus(m), definition(value), step_idx(从1开始)
    focusMetric = pyqtSignal(float, float, int)
    # 导出：原始与平滑曲线（单位：m），以及ROI样张
    focusCurvesUpdated = pyqtSignal(object, object, object, object)
    sampleROI = pyqtSignal(object)

    def __init__(self, api: MicroscopeAPI, target: TargetModel, settings: AutofocusSettings, parent=None):
        super().__init__(parent)
        self.api = api
        self.target = target
        self.cfg = settings
        self._cancel = False
        self._logger = logging.getLogger("autofocus.controller_advanced")

        # 曲线记录
        self.defocus_list = []  # 单位 m
        self.definition_list = []
        self._defocus_cumulative = 0.0  # 仅用于在 get_defocus 失败时构造横坐标
        self._cached_ref_image = None

        # 缓存已评估点，避免重复采样
        self._eval_cache: Dict[float, float] = {}

    def cancel(self):
        self._cancel = True

    def start(self):
        try:
            loop = asyncio.get_running_loop()
            self._logger.info("[AF-ADV] start: scheduling _run on running loop")
            loop.create_task(self._run())
        except RuntimeError:
            self._logger.warning("[AF-ADV] no running loop; creating a temporary loop to run _run()")
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._run())
            finally:
                loop.close()

    async def _run(self):
        try:
            self._logger.info("[AF-ADV] _run entered")
            # 阶段1：括域
            self.progress.emit(1, "Bracket peak")
            a, b, c = await self._bracket_peak()
            if a is None:
                return self.finished.emit(False, {"reason": "bracket-failed"})
            if self._cancel:
                return self.finished.emit(False, {"reason": "cancelled"})

            # 阶段2：黄金分割
            self.progress.emit(2, "Golden-section search")
            x_opt, f_opt = await self._golden_search(a, b, c)
            if x_opt is None:
                return self.finished.emit(False, {"reason": "golden-failed"})
            if self._cancel:
                return self.finished.emit(False, {"reason": "cancelled"})

            # 阶段3：抛物线细化
            self.progress.emit(3, "Parabolic refine")
            x_refined = await self._parabolic_refine_near(x_opt)
            if isinstance(x_refined, (int, float)):
                await self._set_defocus_absolute(float(x_refined))
                await asyncio.sleep(0.2)
                # 最终确认一次
                await self._evaluate_at_current()

            # 完成
            frame = await self.api.acquire_frame()
            if frame is not None:
                self.frame.emit(frame)
            self._logger.info("[AF-ADV] finished successfully")
            self.finished.emit(True, {"defocus_curve": self.defocus_list, "definition_curve": self.definition_list})
        except Exception as e:
            self._logger.exception(f"[AF-ADV] unexpected error: {e}")
            self.error.emit(str(e))
            self.finished.emit(False, {"error": str(e)})

    # ---------- 图像与ROI ----------
    def _get_reference_image(self):
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
        ref = self._get_reference_image()
        if ref is None or frame is None:
            return None
        try:
            roi, (_, _), (drow, dcol) = extract_pattern(ref, frame)
        except Exception as e:
            try:
                self._logger.warning(f"[AF-ADV] extract_pattern failed: {e}")
            except Exception:
                pass
            return None

        try:
            # 估算像素尺寸
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
            ps_h = float(ps['height']) * 1e-10
            ps_w = float(ps['width']) * 1e-10
        except Exception as e:
            try:
                self._logger.warning(f"[AF-ADV] mag2ps failed: {e}")
            except Exception:
                pass
            return roi

        try:
            dx_m = float(dcol) * ps_w
            dy_m = -float(drow) * ps_h
            if abs(dx_m) + abs(dy_m) > 0:
                await self.api.move_stage_relative(dx=dx_m, dy=dy_m, dz=0.0)
        except Exception as e:
            try:
                self._logger.warning(f"[AF-ADV] move_stage_relative failed: {e}")
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

    # ---------- 评估与设置 ----------
    async def _set_defocus_absolute(self, defocus_m: float) -> bool:
        try:
            curr = await self.api.get_defocus()
        except Exception:
            curr = None
        try:
            ok = await self.api.set_defocus(float(defocus_m))
            if ok and isinstance(curr, (int, float)):
                self._defocus_cumulative += float(defocus_m) - float(curr)
            return bool(ok)
        except Exception:
            # 回退到相对设置
            try:
                if isinstance(curr, (int, float)):
                    delta = float(defocus_m) - float(curr)
                    ok_rel = await self.api.set_defocus_relative(delta)
                    if ok_rel:
                        self._defocus_cumulative += float(delta)
                    return bool(ok_rel)
            except Exception:
                return False
        return False

    async def _evaluate_at(self, x_m: float) -> Tuple[float, Optional[np.ndarray]]:
        # 去重：若该点已评估过，仍返回缓存（但不再采集，减少运动）
        if x_m in self._eval_cache:
            return float(self._eval_cache[x_m]), None
        if self._cancel:
            return 0.0, None
        await self._set_defocus_absolute(x_m)
        await asyncio.sleep(0.2)
        frame = await self.api.acquire_frame()
        if frame is not None:
            self.frame.emit(frame)
        roi = await self._center_by_reference(frame) if frame is not None else None
        try:
            img4def = roi if roi is not None else frame
            definition, _ = get_definition(img4def, method='VGR') if img4def is not None else (0.0, None)
        except Exception as ge:
            self._logger.warning(f"[AF-ADV] get_definition failed at {x_m:.6e} m: {ge}")
            definition = 0.0
        # 记录真实 defocus（若可读）
        try:
            curr_defocus = await self.api.get_defocus()
            x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(x_m)
        except Exception:
            x_defocus = float(x_m)
        self.defocus_list.append(x_defocus)
        self.definition_list.append(float(definition))
        self.focusMetric.emit(x_defocus, float(definition), len(self.definition_list))
        self._emit_focus_curves()
        self._eval_cache[x_m] = float(definition)
        return float(definition), frame

    async def _evaluate_at_current(self) -> float:
        try:
            curr = await self.api.get_defocus()
            x = float(curr) if isinstance(curr, (int, float)) else float(self._defocus_cumulative)
        except Exception:
            x = float(self._defocus_cumulative)
        val, _ = await self._evaluate_at(x)
        return val

    # ---------- 括域阶段 ----------
    async def _bracket_peak(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        try:
            curr = await self.api.get_defocus()
            x0 = float(curr) if isinstance(curr, (int, float)) else 0.0
        except Exception:
            x0 = 0.0
        step = max(1.0, float(self.cfg.ofrs_step_nm)) * 1e-9  # m
        expand_ratio = 1.6
        max_expand = max(6, int(self.cfg.max_iterations))

        # 初始三点
        f0, _ = await self._evaluate_at(x0)
        a = x0 - step
        c = x0 + step
        fa, _ = await self._evaluate_at(a)
        fc, _ = await self._evaluate_at(c)
        # 确保 b 为当前最佳
        if f0 >= fa and f0 >= fc:
            b = x0
            fb = f0
        elif fa >= f0 and fa >= fc:
            b = a
            fb = fa
        else:
            b = c
            fb = fc

        # 若最佳在边界，向该侧扩展直到成为内部最优或达到扩展上限
        num_expand = 0
        while not self._cancel and num_expand < max_expand:
            if (b <= a and fb >= fc) or (b >= c and fb >= fa):
                # 仍在边界，扩展区间
                if b <= a:
                    # 向左扩展
                    new_a = a - step
                    fa, _ = await self._evaluate_at(new_a)
                    a = new_a
                else:
                    # 向右扩展
                    new_c = c + step
                    fc, _ = await self._evaluate_at(new_c)
                    c = new_c
                step *= expand_ratio
                num_expand += 1
            else:
                break

        # 调整使 a < b < c，并且 b 是内部点
        xs = sorted([(a, self._eval_cache.get(a, fa)), (b, self._eval_cache.get(b, fb)), (c, self._eval_cache.get(c, fc))], key=lambda t: t[0])
        a, fa = xs[0]
        b, fb = xs[1]
        c, fc = xs[2]

        # 若 b 不是内部极大点，再做一次居中评估
        if not (fb >= fa and fb >= fc):
            mid = 0.5 * (a + c)
            fmid, _ = await self._evaluate_at(mid)
            if fmid >= fb:
                b, fb = mid, fmid

        if fb >= fa and fb >= fc:
            return a, b, c
        return None, None, None

    # ---------- 黄金分割搜索（极大化） ----------
    async def _golden_search(self, a: float, b: float, c: float) -> Tuple[Optional[float], Optional[float]]:
        # 保证 a < c，b 在内
        if c < a:
            a, c = c, a
        if not (a < b < c):
            b = a + 0.5 * (c - a)
        gr = (5 ** 0.5 - 1) / 2  # ~0.618
        tol = max(0.5, float(self.cfg.frs_step_nm)) * 1e-9  # m
        left, right = float(a), float(c)

        # 初始化内部点
        x1 = right - gr * (right - left)
        x2 = left + gr * (right - left)
        f1, _ = await self._evaluate_at(x1)
        f2, _ = await self._evaluate_at(x2)

        iters = 0
        max_iters = max(10, int(self.cfg.max_iterations) * 2)
        while not self._cancel and (right - left) > tol and iters < max_iters:
            if f1 < f2:
                left = x1
                x1 = x2
                f1 = f2
                x2 = left + gr * (right - left)
                f2, _ = await self._evaluate_at(x2)
            else:
                right = x2
                x2 = x1
                f2 = f1
                x1 = right - gr * (right - left)
                f1, _ = await self._evaluate_at(x1)
            iters += 1

        # 最优点估计为内部更优的点
        if f1 >= f2:
            return x1, f1
        else:
            return x2, f2

    # ---------- 抛物线细化 ----------
    async def _parabolic_refine_near(self, x0: float) -> Optional[float]:
        if self._cancel:
            return None
        # 选取近邻的 5 个最优样本点（若不足则用全部），做二次拟合估计顶点
        if len(self.defocus_list) < 3:
            return None
        xs = np.asarray(self.defocus_list, dtype=float)
        ys = np.asarray(self.definition_list, dtype=float)
        order = np.argsort(-ys)  # 从大到小
        topk = min(5, xs.size)
        sel = order[:topk]
        xk = xs[sel]
        yk = ys[sel]
        # 至少3点才能拟合二次项
        if xk.size < 3:
            return None
        try:
            A = np.vstack([xk * xk, xk, np.ones_like(xk)]).T
            coef, *_ = np.linalg.lstsq(A, yk, rcond=None)
            a, b, _ = coef
            if a >= 0:
                return None
            x_vertex = float(-b / (2.0 * a))
            # 仅当顶点在已采样范围内且改进不大于一倍细步长时才下发
            xmin, xmax = float(np.min(xs)), float(np.max(xs))
            if x_vertex < xmin or x_vertex > xmax:
                return None
            # 下发并轻评估一次（会自动记录曲线）
            await self._evaluate_at(x_vertex)
            return x_vertex
        except Exception:
            return None


