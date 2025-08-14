#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标数据模型，用于自动聚焦/自动倾转等任务。

包含：
- TargetModel: 单个目标对象
- StagePose: 样品台位姿 (x, y, z, a, b)
- ReferenceImage: 参考图像记录（携带位姿）
- GlobalImage: 全局图像记录（携带放大倍数）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class StagePose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0  # 倾斜
    b: float = 0.0  # 旋转


@dataclass
class ReferenceImage:
    image: object  # numpy.ndarray (避免直接依赖类型)
    pose: StagePose
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class GlobalImage:
    image: object  # numpy.ndarray
    magnification: float
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class TargetModel:
    target_id: str
    name: str
    preview_pixmap: Optional[object] = None  # QPixmap（可选）
    rect: Optional[tuple] = None             # (x, y, w, h) in data coords
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    # 采集时的状态快照（绑定到该目标，供属性/计算使用）
    snapshot: Optional[dict] = None

    # 数据堆
    reference_images: List[ReferenceImage] = field(default_factory=list)
    global_images: List[GlobalImage] = field(default_factory=list)

    # 倾转序列（运行自动倾转时填充）
    # 设计为并行序列，且提供便捷的新增方法，保持四个列表索引对齐
    tilt_alpha_series: List[float] = field(default_factory=list)
    tilt_global_series: List[GlobalImage] = field(default_factory=list)
    tilt_snapshot_series: List[Dict[str, Any]] = field(default_factory=list)
    tilt_reference_series: List[ReferenceImage] = field(default_factory=list)
    tilt_highres_series: List[GlobalImage] = field(default_factory=list)

    def add_reference(self, image, pose: StagePose):
        self.reference_images.append(ReferenceImage(image=image, pose=pose))

    def add_global(self, image, magnification: float):
        self.global_images.append(GlobalImage(image=image, magnification=magnification))

    def add_tilt_entry(self,
                       alpha_deg: float,
                       global_image: object,
                       global_magnification: float,
                       reference_image: object,
                       stage_pose: StagePose,
                       snapshot: Optional[Dict[str, Any]] = None,
                       highres_image: Optional[object] = None,
                       highres_magnification: Optional[float] = None):
        gi = GlobalImage(image=global_image, magnification=float(global_magnification))
        ri = ReferenceImage(image=reference_image, pose=stage_pose)
        self.tilt_alpha_series.append(float(alpha_deg))
        self.tilt_global_series.append(gi)
        self.tilt_reference_series.append(ri)
        self.tilt_snapshot_series.append(dict(snapshot) if isinstance(snapshot, dict) else {})
        if highres_image is not None:
            hi_mag = float(highres_magnification) if isinstance(highres_magnification, (int, float)) else float(global_magnification)
            hi = GlobalImage(image=highres_image, magnification=hi_mag)
            self.tilt_highres_series.append(hi)
        else:
            # 占位，确保索引对齐
            self.tilt_highres_series.append(GlobalImage(image=None, magnification=0.0))


