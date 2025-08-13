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
from typing import List, Optional
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

    # 数据堆
    reference_images: List[ReferenceImage] = field(default_factory=list)
    global_images: List[GlobalImage] = field(default_factory=list)

    def add_reference(self, image, pose: StagePose):
        self.reference_images.append(ReferenceImage(image=image, pose=pose))

    def add_global(self, image, magnification: float):
        self.global_images.append(GlobalImage(image=image, magnification=magnification))


