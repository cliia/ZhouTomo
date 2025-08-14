#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中间图像显示面板：封装 ImageCanvas + 帧控制（滑块与行编辑），对外暴露简洁信号与方法。
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLineEdit

from PyQt5.QtWidgets import QSizePolicy

import base64
import numpy as np


class ImagePanel(QWidget):
    """图像显示与帧导航面板。

    对外信号：
    - selectionMade(x0,y0,x1,y1): 来自 ImageCanvas 的矩形框选（数据坐标）
    - imageUpdated(ndarray): 画布图像更新
    - frameChanged(index, total): 帧索引变化（1-based）
    """

    selectionMade = pyqtSignal(float, float, float, float)
    imageUpdated = pyqtSignal(object)
    frameChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_frames_data = []
        self._decode_frame_fn = None
        self._current_frame_index = 0

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Matplotlib 画布
        from view.image_canvas import ImageCanvas
        self.image_canvas = ImageCanvas()
        self.image_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_canvas.selectionMade.connect(self.selectionMade.emit)
        self.image_canvas.imageUpdated.connect(self.imageUpdated.emit)
        layout.addWidget(self.image_canvas)

        # 帧控制条
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(8, 8, 8, 8)
        ctrl.setSpacing(8)
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(1)
        self.frame_slider.setMaximum(1)
        self.frame_slider.setValue(1)
        self.frame_slider.setSingleStep(1)
        self.frame_slider.setPageStep(1)
        self.frame_slider.setFixedHeight(24)
        self.frame_slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #3a3a3a; height: 4px; background: #2a2f33; border-radius: 2px; }
            QSlider::handle:horizontal { background: #3daee9; border: 1px solid #2980b9; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #3daee9; border-radius: 2px; }
        """)
        self.frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        self.frame_edit = QLineEdit("0 / 0")
        self.frame_edit.setAlignment(Qt.AlignCenter)
        self.frame_edit.setFixedWidth(80)
        self.frame_edit.setStyleSheet("""
            QLineEdit { color: #d0d0d0; font-size: 12px; background: #2a2f33; border: 1px solid #3a3a3a; border-radius: 3px; padding: 2px 6px; min-height: 20px; }
            QLineEdit:hover { border: 1px solid #3daee9; background: #2f3438; }
        """)
        self.frame_edit.returnPressed.connect(self._on_frame_edit_finished)
        self.frame_edit.editingFinished.connect(self._on_frame_edit_finished)

        ctrl.addWidget(self.frame_slider, 1)
        ctrl.addWidget(self.frame_edit, 0)
        layout.addLayout(ctrl)

        self.frame_slider.setVisible(False)
        self.frame_edit.setVisible(False)

    # ---------- 对外方法 ----------
    def enable_selection(self, enabled: bool):
        self.image_canvas.enable_selection(bool(enabled))

    def clear_selection(self):
        try:
            self.image_canvas._clear_current_rectangle()
        except Exception:
            pass

    def set_image_array(self, image_array: np.ndarray):
        self.image_canvas.set_image(image_array)

    def set_image_stack(self, frames_b64_list, frame_shapes=None, frame_dtypes=None, frame_byteorders=None):
        """显示帧栈：保存 b64 列表，提供滑块/编辑导航。
        可选携带服务端提供的帧形状/类型信息，优先用于解码，避免靠字节数猜测导致条纹。
        """
        if not frames_b64_list:
            return
        self._original_frames_data = frames_b64_list
        self._current_frame_index = 0
        self._frame_shapes = frame_shapes or [None] * len(frames_b64_list)
        self._frame_dtypes = frame_dtypes or [None] * len(frames_b64_list)
        self._frame_byteorders = frame_byteorders or [None] * len(frames_b64_list)

        def _dtype_from_meta(dtype_name: str, byteorder: str):
            if not dtype_name:
                return None
            dn = dtype_name.lower()
            # 默认小端
            bo = '<' if byteorder in (None, '=', '<') else '>'
            mapping = {
                'uint8': 'u1', 'u1': 'u1',
                'uint16': 'u2', 'u2': 'u2',
                'int16': 'i2', 'i2': 'i2',
                'int32': 'i4', 'i4': 'i4',
                'float32': 'f4', 'f4': 'f4',
                'float64': 'f8', 'f8': 'f8',
            }
            core = mapping.get(dn)
            if not core:
                return None
            if core in ('u1',):
                return np.dtype(core)
            return np.dtype(bo + core)

        def decode_to_array(b64: str, idx: int):
            data = base64.b64decode(b64)
            # 优先使用服务端元数据
            shape = self._frame_shapes[idx] if idx < len(self._frame_shapes) else None
            dtype_name = self._frame_dtypes[idx] if idx < len(self._frame_dtypes) else None
            byteorder = self._frame_byteorders[idx] if idx < len(self._frame_byteorders) else None
            try:
                if shape and isinstance(shape, (list, tuple)) and len(shape) >= 2 and dtype_name:
                    h, w = int(shape[0]), int(shape[1])
                    dt = _dtype_from_meta(dtype_name, byteorder)
                    if dt is None:
                        raise ValueError("unsupported dtype from meta")
                    arr = np.frombuffer(data, dtype=dt)
                    if arr.size >= h * w:
                        return arr[:h*w].reshape(h, w)
            except Exception:
                pass
            # 回退：按正方 8bit/16bit 猜测
            n_bytes = len(data)
            side8 = int((n_bytes) ** 0.5)
            if side8 * side8 == n_bytes:
                return np.frombuffer(data, dtype=np.uint8).reshape(side8, side8)
            side16 = int((n_bytes // 2) ** 0.5)
            if side16 * side16 * 2 == n_bytes:
                return np.frombuffer(data, dtype='<u2').reshape(side16, side16)
            return np.full((512, 512), 128, dtype=np.uint8)

        self._decode_frame_fn = lambda b64, i: decode_to_array(b64, i)
        first_arr = decode_to_array(frames_b64_list[0], 0)
        self.set_image_array(first_arr)

        total = len(frames_b64_list)
        self.frame_slider.setMaximum(total)
        self.frame_slider.setValue(1)
        self.frame_edit.setText(f"1 / {total}")
        self.frame_slider.setVisible(True)
        self.frame_edit.setVisible(True)
        self.frameChanged.emit(1, total)

    def get_current_image_array(self):
        return getattr(self.image_canvas, '_current_image', None)

    def set_snapshot(self, snapshot: dict):
        """转发快照给画布，供属性对话框使用。"""
        try:
            if hasattr(self, 'image_canvas') and self.image_canvas:
                self.image_canvas.set_snapshot(snapshot)
        except Exception:
            pass

    # ---------- 内部事件 ----------
    def _on_frame_slider_changed(self, value: int):
        try:
            idx = max(1, int(value))
            frames = self._original_frames_data
            if not frames or not (1 <= idx <= len(frames)):
                return
            arr = self._decode_frame_fn(frames[idx - 1], idx - 1) if self._decode_frame_fn else None
            if arr is None:
                return
            self.image_canvas.set_image(arr)
            self.frame_edit.setText(f"{idx} / {len(frames)}")
            self._current_frame_index = idx - 1
            self.frameChanged.emit(idx, len(frames))
        except Exception:
            pass

    def _on_frame_edit_finished(self):
        try:
            total = len(self._original_frames_data)
            text = self.frame_edit.text().strip()
            if '/' in text:
                left = text.split('/', 1)[0].strip()
            else:
                left = text
            frame_num = int(left)
            if 1 <= frame_num <= total:
                self.frame_slider.setValue(frame_num)
            else:
                self.frame_edit.setText(f"{self._current_frame_index + 1} / {total}")
        except Exception:
            if self._original_frames_data:
                total = len(self._original_frames_data)
                self.frame_edit.setText(f"{self._current_frame_index + 1} / {total}")


