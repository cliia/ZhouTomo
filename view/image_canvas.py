#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matplotlib 图像画布，用于显示图像并支持矩形框选（数据坐标，自动考虑放缩）。
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
import numpy as np


class ImageCanvas(FigureCanvas):
    """封装 Matplotlib 画布，支持设置图像和矩形选择。"""

    selectionMade = pyqtSignal(float, float, float, float)  # x0, y0, x1, y1（数据坐标）
    imageUpdated = pyqtSignal(object)  # numpy.ndarray 当前显示的图像

    def __init__(self, parent: QWidget = None):
        self._figure = Figure(figsize=(5, 4), dpi=100)
        super().__init__(self._figure)
        self.setParent(parent)
        # 允许在布局中自由伸缩，不强制最小高度
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)
        self.setFocusPolicy(Qt.StrongFocus)

        self._axes = self._figure.add_subplot(111)
        self._axes.set_aspect('equal')
        self._axes.axis('off')
        # 充满画布，不留空白
        self._figure.set_facecolor('none')
        self._figure.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self._axes.set_position([0, 0, 1, 1])

        self._image_artist = None
        self._rect_selector = None
        self._selection_enabled = False
        # 右键删除当前选择
        self.mpl_connect('button_press_event', self._on_button_press)

        # 限流重绘：避免频繁调用 draw_idle
        self._draw_timer = QTimer(self)
        self._draw_timer.setSingleShot(True)
        self._draw_timer.setInterval(30)  # 约33FPS即可
        self._draw_timer.timeout.connect(self._on_draw_timeout)

        self._current_image = None  # numpy.ndarray (H, W) 或 (H, W, C)

    def set_image(self, image_array: np.ndarray):
        """显示图像（numpy 数组）"""
        if image_array is None:
            return
        self._current_image = image_array
        # 初始化坐标轴一次
        if self._image_artist is None:
            self._axes.clear()
            self._axes.set_aspect('equal')
            self._axes.axis('off')
            # 充满画布
            self._figure.subplots_adjust(left=0, right=1, bottom=0, top=1)
            self._axes.set_position([0, 0, 1, 1])

        # 归一化显示：8-bit 直接显示；16-bit 则线性映射到0-1
        arr = image_array
        h, w = arr.shape[0], arr.shape[1]
        if arr.dtype == np.uint16:
            maxv = int(arr.max()) if arr.size else 65535
            maxv = max(1, maxv)
            disp = (arr.astype(np.float32) / maxv)
        else:
            disp = arr
        # origin='upper' 使数据坐标与常见图像行列一致（y 向下）
        if self._image_artist is None:
            # 明确指定 extent，使数据坐标与像素索引一一对应：x∈[0,w], y∈[0,h] 且 y 向下
            self._image_artist = self._axes.imshow(
                disp, cmap='gray', origin='upper', interpolation='nearest', extent=(0, w, h, 0)
            )
            # 锁定坐标范围，避免缩放/平移导致坐标偏移
            self._axes.set_xlim(0, w)
            self._axes.set_ylim(h, 0)
        else:
            self._image_artist.set_data(disp)
            # 同步更新 extent，确保在分辨率变化时坐标仍准确
            try:
                self._image_artist.set_extent((0, w, h, 0))
                self._axes.set_xlim(0, w)
                self._axes.set_ylim(h, 0)
            except Exception:
                pass
        self._request_draw()
        try:
            self.imageUpdated.emit(image_array)
        except Exception:
            pass

    def _request_draw(self):
        try:
            self._draw_timer.start()
        except Exception:
            # 兜底
            try:
                self.draw_idle()
            except Exception:
                pass

    def _on_draw_timeout(self):
        try:
            self.draw_idle()
        except Exception:
            pass

    def enable_selection(self, enabled: bool):
        """启用/禁用矩形框选"""
        self._selection_enabled = enabled
        if enabled:
            if self._rect_selector is None:
                # 兼容较新版本 Matplotlib：使用 props 而非 rectprops
                try:
                    self._rect_selector = RectangleSelector(
                        self._axes,
                        onselect=self._on_select,
                        useblit=True,
                        button=[1],  # 左键
                        minspanx=2,
                        minspany=2,
                        spancoords='data',
                        interactive=False,
                        props=dict(edgecolor='cyan', facecolor='none', linewidth=1.5)
                    )
                except TypeError:
                    # 向后兼容旧版本参数名 rectprops
                    self._rect_selector = RectangleSelector(
                        self._axes,
                        onselect=self._on_select,
                        useblit=True,
                        button=[1],  # 左键
                        minspanx=2,
                        minspany=2,
                        spancoords='data',
                        interactive=False,
                        rectprops=dict(edgecolor='cyan', facecolor='none', linewidth=1.5)
                    )
            self._rect_selector.set_active(True)
        else:
            if self._rect_selector is not None:
                # 禁用交互并彻底隐藏包括 resize handles 在内的所有元素
                try:
                    self._rect_selector.set_active(False)
                    self._clear_current_rectangle()
                except Exception:
                    pass

    def _on_select(self, eclick, erelease):
        if not self._selection_enabled:
            return
        # 数据坐标
        x0, y0 = eclick.xdata, eclick.ydata
        x1, y1 = erelease.xdata, erelease.ydata
        if x0 is None or y0 is None or x1 is None or y1 is None:
            return
        self.selectionMade.emit(float(x0), float(y0), float(x1), float(y1))
        # 选择完成后保留矩形供查看，可通过外部关闭或右键删除

    def _on_button_press(self, event):
        """右键删除当前矩形选择，不影响已保存的目标数据"""
        try:
            if event.button == 3 and self._rect_selector is not None:
                self._clear_current_rectangle()
        except Exception:
            pass

    def _clear_current_rectangle(self):
        """隐藏当前选择框但不改变选择模式的启用状态"""
        sel = self._rect_selector
        if sel is None:
            return
        # 不同版本 Matplotlib 的绘制对象字段名不同，尽可能兼容
        handled = False
        # v3.6+ 使用 _selection_artist
        artist = getattr(sel, '_selection_artist', None)
        if artist is not None:
            try:
                artist.set_visible(False)
                handled = True
            except Exception:
                pass
        # 老版本使用 to_draw 列表
        if not handled:
            to_draw = getattr(sel, 'to_draw', None)
            if isinstance(to_draw, (list, tuple)):
                for a in to_draw:
                    try:
                        a.set_visible(False)
                    except Exception:
                        pass
                handled = True
        # 进一步尝试 rectangle 属性
        if not handled:
            rect = getattr(sel, 'rectangle', None)
            try:
                if rect is not None:
                    rect.set_visible(False)
            except Exception:
                pass
        # 处理交互手柄（corner/edge handles），确保角点与边点一起隐藏
        for list_attr in ('_corner_handles', 'corner_handles',
                          '_edge_handles', 'edge_handles',
                          '_handles', 'handles'):
            handles = getattr(sel, list_attr, None)
            if isinstance(handles, (list, tuple)):
                for h in handles:
                    try:
                        h.set_visible(False)
                    except Exception:
                        pass
        # 重绘
        try:
            self.draw_idle()
        except Exception:
            try:
                self.draw()
            except Exception:
                pass


