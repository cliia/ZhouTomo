#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Tuple, Dict
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from zhoutomo_client.workflows.autofocus.config import AutofocusSettings
from zhoutomo_client.workflows.autofocus.microscope_api import MicroscopeAPI
from zhoutomo_client.models.targets import TargetModel
from zhoutomo_client.processing.legacy.utils import get_definition, mag2ps
from zhoutomo_client.processing.legacy.normxcorr2 import extract_pattern
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
import logging
import asyncio
import threading


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
            # 不要在UI线程里阻塞运行事件循环；改为后台线程中创建事件循环
            self._logger.warning("[AF-ADV] no running loop; starting a background event loop thread for _run()")

            def _bg_runner():
                bg_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(bg_loop)
                try:
                    bg_loop.run_until_complete(self._run())
                finally:
                    try:
                        bg_loop.close()
                    except Exception:
                        pass

            t = threading.Thread(target=_bg_runner, name="AF-ADV-Loop", daemon=True)
            t.start()

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
                # 最终确认一次
                await self._evaluate_at_current()

            # 阶段4：超精细微扫（±10nm）（可选）
            try:
                if bool(getattr(self.cfg, 'enable_ultra_fine', True)):
                    self.progress.emit(4, "Ultra-fine refine (±10 nm)")
                    try:
                        base_x = float(x_refined) if isinstance(x_refined, (int, float)) else float(x_opt)
                    except Exception:
                        base_x = float(x_opt)
                    x_ultra = await self._ultra_fine_refine(base_x)
                    if isinstance(x_ultra, (int, float)):
                        await self._set_defocus_absolute(float(x_ultra))
                        await self._evaluate_at_current()
            except Exception:
                pass

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

    async def _evaluate_at(self, x_m: float, record: bool = True) -> Tuple[float, Optional[np.ndarray]]:
        # 去重：若该点已评估过，仍返回缓存（但不再采集，减少运动）
        if x_m in self._eval_cache and record:
            return float(self._eval_cache[x_m]), None
        if self._cancel:
            return 0.0, None
        await self._set_defocus_absolute(x_m)
        await asyncio.sleep(0.2)
        frame = await self.api.acquire_frame()
        if record and frame is not None:
            try:
                self.frame.emit(frame)
            except Exception:
                pass
        roi = await self._center_by_reference(frame) if frame is not None else None
        try:
            img4def = roi if roi is not None else frame
            definition, _ = get_definition(img4def, method='VGR') if img4def is not None else (0.0, None)
        except Exception as ge:
            try:
                self._logger.warning(f"[AF-ADV] get_definition failed at {x_m:.6e} m: {ge}")
            except Exception:
                pass
            definition = 0.0
        # 记录（可选）
        if record:
            try:
                curr_defocus = await self.api.get_defocus()
                x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(x_m)
            except Exception:
                x_defocus = float(x_m)
            self.defocus_list.append(x_defocus)
            self.definition_list.append(float(definition))
            try:
                self.focusMetric.emit(x_defocus, float(definition), len(self.definition_list))
                self._emit_focus_curves()
            except Exception:
                pass
        self._eval_cache[x_m] = float(definition)
        return float(definition), frame

    async def _record_focus_point(self, x_m: float, definition: float, frame: Optional[np.ndarray]) -> None:
        try:
            try:
                curr_defocus = await self.api.get_defocus()
                x_defocus = float(curr_defocus) if isinstance(curr_defocus, (int, float)) else float(x_m)
            except Exception:
                x_defocus = float(x_m)
            self.defocus_list.append(x_defocus)
            self.definition_list.append(float(definition))
            try:
                self.focusMetric.emit(x_defocus, float(definition), len(self.definition_list))
                self._emit_focus_curves()
            except Exception:
                pass
            if frame is not None:
                try:
                    self.frame.emit(frame)
                except Exception:
                    pass
        except Exception:
            pass

    async def _evaluate_at_median(self, x_m: float, repeats: int = 3) -> float:
        vals = []
        last_frame = None
        for _ in range(max(1, int(repeats))):
            fi, fr = await self._evaluate_at(x_m, record=False)
            vals.append(float(fi))
            last_frame = fr if fr is not None else last_frame
        try:
            import numpy as np
            med = float(np.median(np.asarray(vals, dtype=float)))
        except Exception:
            med = float(vals[-1])
        await self._record_focus_point(x_m, med, last_frame)
        self._eval_cache[x_m] = float(med)
        return float(med)

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
        # 目标：通过对称双向扩展与自适应步长下限，尽量找到 a<b<c 且 f(b)>=f(a), f(b)>=f(c)
        try:
            curr = await self.api.get_defocus()
            x0 = float(curr) if isinstance(curr, (int, float)) else 0.0
        except Exception:
            x0 = 0.0

        step0_m = max(1.0, float(self.cfg.ofrs_step_nm)) * 1e-9  # m
        # 自适应步长下限：至少为 min(细搜步长的一半, 10nm) 的上限，避免过小步长被噪声淹没
        try:
            frs_step_m = max(0.5, float(self.cfg.frs_step_nm)) * 1e-9
        except Exception:
            frs_step_m = 75.0e-9
        min_step_m = max(10.0e-9, 0.5 * frs_step_m)
        stepL = max(step0_m, min_step_m)
        stepR = max(step0_m, min_step_m)
        expand_ratio = 1.6
        max_expand = max(6, int(self.cfg.max_iterations))

        self._logger.info(
            f"[AF-ADV] bracket: x0={x0:.6e} m, step0={step0_m:.3e} m, min_step={min_step_m:.3e} m, expand_ratio={expand_ratio}, max_expand={max_expand}"
        )

        # 采样缓存（但 _evaluate_at 内部已有缓存，这里仅便于排序/查找）
        def add_sample(x: float) -> float:
            val, _ = await_self_eval(x)
            return val

        # 为了在本作用域内 await 调用，定义一个小的 async 包装
        async def await_self_eval(x: float) -> float:
            val, _ = await self._evaluate_at(float(x))
            try:
                self._logger.debug(f"[AF-ADV] bracket eval: x={float(x):.6e} m, f={val:.6e}")
            except Exception:
                pass
            return float(val)

        # 检查当前采样点集合是否已形成括域
        def try_form_bracket(xs: np.ndarray, ys: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
            if xs.size < 3:
                return None, None, None
            # 找到全局最大点 b_idx，并确保左右各至少一个点
            b_idx = int(np.argmax(ys))
            if b_idx == 0 or b_idx == xs.size - 1:
                return None, None, None
            a_idx = b_idx - 1
            c_idx = b_idx + 1
            fa_local = float(ys[a_idx])
            fb_local = float(ys[b_idx])
            fc_local = float(ys[c_idx])
            if fb_local >= fa_local and fb_local >= fc_local:
                return float(xs[a_idx]), float(xs[b_idx]), float(xs[c_idx])
            return None, None, None

        # 初始对称三点（稳健采样：多次取中位数）
        samples_x = []  # type: list[float]
        samples_y = []  # type: list[float]
        f0 = await self._evaluate_at_median(x0, repeats=3)
        fa = await self._evaluate_at_median(x0 - stepL, repeats=3)
        fc = await self._evaluate_at_median(x0 + stepR, repeats=3)
        samples_x.extend([x0 - stepL, x0, x0 + stepR])
        samples_y.extend([fa, f0, fc])

        # 排序一次
        order = np.argsort(np.asarray(samples_x))
        xs = np.asarray(samples_x, dtype=float)[order]
        ys = np.asarray(samples_y, dtype=float)[order]

        a_b_c = try_form_bracket(xs, ys)
        if a_b_c[0] is not None:
            a, b, c = a_b_c
            self._logger.info(
                f"[AF-ADV] bracket FOUND at init: a={a:.6e}, b={b:.6e}, c={c:.6e}"
            )
            return a, b, c

        # 迭代对称扩展：每轮在左右两端各添加一个点，并放大步长
        num_expand = 0
        while not self._cancel and num_expand < max_expand:
            left_edge = float(xs[0])
            right_edge = float(xs[-1])
            new_left = left_edge - stepL
            new_right = right_edge + stepR

            fl = await self._evaluate_at_median(new_left, repeats=2)
            fr = await self._evaluate_at_median(new_right, repeats=2)

            xs = np.concatenate([np.asarray([new_left], dtype=float), xs, np.asarray([new_right], dtype=float)])
            ys = np.concatenate([np.asarray([fl], dtype=float), ys, np.asarray([fr], dtype=float)])

            # 检查是否形成括域
            a_b_c = try_form_bracket(xs, ys)
            try:
                self._logger.info(
                    f"[AF-ADV] bracket expand#{num_expand+1}: left=({new_left:.6e},{fl:.6e}), right=({new_right:.6e},{fr:.6e}), stepL={stepL:.3e}, stepR={stepR:.3e}"
                )
            except Exception:
                pass
            if a_b_c[0] is not None:
                a, b, c = a_b_c
                self._logger.info(
                    f"[AF-ADV] bracket FOUND after expand#{num_expand+1}: a={a:.6e}, b={b:.6e}, c={c:.6e}"
                )
                return a, b, c

            # 扩大步长，保持不低于下限
            stepL = max(stepL * expand_ratio, min_step_m)
            stepR = max(stepR * expand_ratio, min_step_m)
            num_expand += 1

        # 仍未括住：再进行一次“居中采样 + 邻域确认”的兜底
        if not self._cancel:
            xmin = float(xs.min())
            xmax = float(xs.max())
            mid = 0.5 * (xmin + xmax)
            fmid = await self._evaluate_at_median(mid, repeats=3)
            xs = np.sort(np.concatenate([xs, np.asarray([mid], dtype=float)]))
            # 重排 ys：从缓存中取，避免错位
            ys = np.asarray([float(self._eval_cache.get(xx, 0.0)) for xx in xs], dtype=float)
            a_b_c = try_form_bracket(xs, ys)
            if a_b_c[0] is not None:
                a, b, c = a_b_c
                self._logger.info(
                    f"[AF-ADV] bracket FOUND at fallback-mid: a={a:.6e}, b={b:.6e}, c={c:.6e}"
                )
                return a, b, c

        # 仍失败：在当前全局最优点附近，以自适应步长采样左右各一点作为最终尝试
        if not self._cancel and xs.size >= 1:
            b_idx = int(np.argmax(ys))
            b = float(xs[b_idx])
            local_step = max(min_step_m, 0.25 * (float(xs.max()) - float(xs.min()) + min_step_m))
            x_left = b - local_step
            x_right = b + local_step
            fl = await self._evaluate_at_median(x_left, repeats=2)
            fr = await self._evaluate_at_median(x_right, repeats=2)

        # 最终兜底：执行一次局部粗扫（x0±N*step0_m），选出局部最大及邻域作为括域
        try:
            N = 6
            grid = [x0 + k * step0_m for k in range(-N, N + 1)]
            vals = []
            for xi in grid:
                vi = await self._evaluate_at_median(xi, repeats=2)
                vals.append(float(vi))
            arrx = np.asarray(grid, dtype=float)
            arry = np.asarray(vals, dtype=float)
            idx_best = int(np.argmax(arry))
            if 0 < idx_best < arrx.size - 1:
                a, b, c = float(arrx[idx_best - 1]), float(arrx[idx_best]), float(arrx[idx_best + 1])
                self._logger.info(f"[AF-ADV] bracket FOUND via coarse-scan: a={a:.6e}, b={b:.6e}, c={c:.6e}")
                return a, b, c
        except Exception:
            pass
            try:
                self._logger.info(
                    f"[AF-ADV] bracket last-try around best: b≈{b:.6e}, left=({x_left:.6e},{fl:.6e}), right=({x_right:.6e},{fr:.6e})"
                )
            except Exception:
                pass
            xs2 = np.sort(np.concatenate([xs, np.asarray([x_left, x_right], dtype=float)]))
            ys2 = np.asarray([float(self._eval_cache.get(xx, 0.0)) for xx in xs2], dtype=float)
            a_b_c = try_form_bracket(xs2, ys2)
            if a_b_c[0] is not None:
                a, b, c = a_b_c
                self._logger.info(
                    f"[AF-ADV] bracket FOUND at last-try: a={a:.6e}, b={b:.6e}, c={c:.6e}"
                )
                return a, b, c

        # 放弃
        try:
            self._logger.warning("[AF-ADV] bracket FAILED: unable to form (a<b<c) with interior maximum after expansions")
        except Exception:
            pass
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


    async def _ultra_fine_refine(self, x0: float) -> Optional[float]:
        """围绕 x0 进行 ±10nm 微扫与局部二次拟合，提升至 ±10nm 精度目标。
        策略：以 5nm 为步长，在 ±30nm 取样，选择最大点；若最佳不在中心，再以其为中心重复一轮（最多两轮）。"""
        if self._cancel:
            return None
        try:
            step = 5e-9  # 10 nm in meters
            span = 3  # ±3 步 -> ±30nm
            best_x = float(x0)
            best_f = -1e30
            for round_idx in range(2):
                xs = [best_x + k * step for k in range(-span, span + 1)]
                vals = []
                for xi in xs:
                    fi, _ = await self._evaluate_at(float(xi))
                    vals.append(float(fi))
                    if fi > best_f:
                        best_f = float(fi)
                        best_x = float(xi)
                # 二次拟合估计顶点（若点数足够）
                try:
                    import numpy as np
                    xarr = np.asarray(xs, dtype=float)
                    yarr = np.asarray(vals, dtype=float)
                    order = np.argsort(xarr)
                    xarr = xarr[order]
                    yarr = yarr[order]
                    if xarr.size >= 3:
                        A = np.vstack([xarr * xarr, xarr, np.ones_like(xarr)]).T
                        coef, *_ = np.linalg.lstsq(A, yarr, rcond=None)
                        a, b, _ = coef
                        if a < 0:
                            xv = float(-b / (2.0 * a))
                            if xarr.min() <= xv <= xarr.max():
                                fv, _ = await self._evaluate_at(xv)
                                if fv > best_f:
                                    best_f = float(fv)
                                    best_x = float(xv)
                except Exception:
                    pass
            return float(best_x)
        except Exception:
            return None


