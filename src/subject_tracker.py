#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Tuple, List
import numpy as np
import cv2


def _clip_rect(rect: Tuple[int, int, int, int], h: int, w: int) -> Tuple[int, int, int, int]:
    x, y, rw, rh = rect
    x0 = max(0, int(x)); y0 = max(0, int(y))
    x1 = min(int(x + rw), int(w)); y1 = min(int(y + rh), int(h))
    if x1 <= x0 or y1 <= y0:
        return 0, 0, 0, 0
    return x0, y0, x1 - x0, y1 - y0


def detect_subject(image: np.ndarray,
                   seed_rect: Tuple[int, int, int, int],
                   prev_mask: Optional[np.ndarray] = None,
                   search_margin: int = 24) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[Tuple[float, float]]]:
    """
    基于用户框出的主体矩形，在附近区域进行鲁棒分割，返回：
    - mask: 与整幅图同尺寸的布尔掩膜（主体为 True）
    - contour: Nx2 的边界坐标（x,y），用于绘制
    - center: 主体外接矩形的中心 (cy, cx) ，以像素计

    策略：
    - 在 seed_rect 周围扩展一定 margin 的搜索窗口，减少邻域干扰
    - 采用平滑 + 自适应阈值 + 形态学开闭操作
    - 选择与 prev_mask 有最大 IoU 的连通域；若无 prev_mask，选择最大连通域
    """
    try:
        if image is None:
            return None, None, None
        arr = np.asarray(image)
        if arr.ndim == 3:
            arr = arr.mean(axis=2)
        h, w = int(arr.shape[0]), int(arr.shape[1])
        x, y, rw, rh = seed_rect if isinstance(seed_rect, (list, tuple)) and len(seed_rect) == 4 else (0, 0, w, h)
        # 搜索窗口：在种子矩形基础上扩展 margin
        sx0 = max(0, int(x) - int(search_margin))
        sy0 = max(0, int(y) - int(search_margin))
        sx1 = min(w, int(x + rw) + int(search_margin))
        sy1 = min(h, int(y + rh) + int(search_margin))
        if sx1 <= sx0 or sy1 <= sy0:
            return None, None, None
        crop = arr[sy0:sy1, sx0:sx1]

        # 预处理：轻度高斯滤波，增强对比
        crop_f = crop.astype(np.float32, copy=False)
        crop_f = cv2.GaussianBlur(crop_f, (3, 3), 0)
        # 对比度拉伸（分位数 1%-99%）
        try:
            vmin = float(np.percentile(crop_f, 1))
            vmax = float(np.percentile(crop_f, 99))
            if vmax > vmin:
                crop_n = (crop_f - vmin) * (1.0 / (vmax - vmin))
            else:
                crop_n = crop_f - np.min(crop_f)
        except Exception:
            crop_n = crop_f - np.min(crop_f)

        # 自适应阈值（Otsu 或自适应均可），取亮或暗区域中更显著者
        crop_u8 = np.clip(crop_n * 255.0, 0, 255).astype(np.uint8)
        try:
            _, th1 = cv2.threshold(crop_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            _, th2 = cv2.threshold(crop_u8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        except Exception:
            th1 = (crop_u8 > 128).astype(np.uint8) * 255
            th2 = (crop_u8 <= 128).astype(np.uint8) * 255
        # 选择面积较大的阈值结果
        if int(np.sum(th1 > 0)) >= int(np.sum(th2 > 0)):
            bw = th1
        else:
            bw = th2

        # 形态学去噪：开运算去小点，闭运算填小洞
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 连通域，优先 IoU 最大者，否则选择面积最大的
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((bw > 0).astype(np.uint8), connectivity=8)
        if num_labels <= 1:
            return None, None, None
        areas = stats[1:, cv2.CC_STAT_AREA]
        candidates = list(range(1, num_labels))
        chosen = None
        if isinstance(prev_mask, np.ndarray) and prev_mask.shape[:2] == (h, w):
            prev_local = prev_mask[sy0:sy1, sx0:sx1].astype(bool)
            best_iou = -1.0
            for lab in candidates:
                comp = (labels == lab)
                inter = float(np.logical_and(comp, prev_local).sum())
                union = float(np.logical_or(comp, prev_local).sum())
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    chosen = lab
        if chosen is None:
            # 面积最大者
            chosen = int(1 + int(np.argmax(areas)))

        comp = (labels == chosen)
        # 提取外接矩形与轮廓
        ys, xs = np.where(comp)
        if xs.size == 0:
            return None, None, None
        x0 = int(xs.min()) + sx0; x1 = int(xs.max()) + sx0
        y0 = int(ys.min()) + sy0; y1 = int(ys.max()) + sy0
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * (y0 + y1)

        # 轮廓坐标（映射回全图坐标）
        try:
            contours, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) > 0:
                cnt = contours[0].reshape(-1, 2)
                cnt[:, 0] = cnt[:, 0] + sx0
                cnt[:, 1] = cnt[:, 1] + sy0
                contour_xy = cnt.astype(np.float32)
            else:
                contour_xy = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], dtype=np.float32)
        except Exception:
            contour_xy = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], dtype=np.float32)

        # 构造整图掩膜
        mask = np.zeros((h, w), dtype=bool)
        mask[sy0:sy1, sx0:sx1] = comp

        return mask, contour_xy, (cy, cx)
    except Exception:
        return None, None, None


