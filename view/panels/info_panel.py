#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧信息面板：上（Histogram/FFT tabs）、中（信息文本）、下（预留）。
对外暴露 update_analysis(image_array) 与 set_snapshot(snapshot)。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QTabWidget

from config.colors import colors
import numpy as np


class InfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{ background-color: {colors.LIGHT_BACKGROUND}; border: 0px; }}
        """)
        layout = QVBoxLayout(self)

        # 顶部 tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setStyleSheet(f"""
            QTabWidget {{ background-color: {colors.DARK_BACKGROUND}; border: 0px; color: {colors.TEXT_NORMAL}; font-family: Microsoft YaHei; font-size: 12px; font-weight: bold; }}
            QTabWidget::pane {{ border: 1px solid {colors.BORDER_COLOR}; top: -1px; margin: 0px; padding: 0px; }}
            QStackedWidget {{ background-color: {colors.DARK_BACKGROUND}; border: 0px; margin: 0px; padding: 0px; }}
            QTabBar::tab {{ background-color: {colors.DARK_BACKGROUND}; border: 1px solid {colors.BORDER_COLOR}; color: {colors.TEXT_NORMAL}; font-family: Microsoft YaHei; font-size: 12px; font-weight: bold; padding: 5px 10px; }}
            QTabBar::tab:selected {{ background-color: {colors.BUTTON_HOVER}; color: {colors.TEXT_NORMAL}; }}
            QTabBar::tab:hover {{ background-color: {colors.BUTTON_HOVER}; color: {colors.TEXT_NORMAL}; }}
        """)

        # Histogram
        self.hist_figure = Figure(figsize=(3, 2), dpi=100)
        self.hist_canvas = FigureCanvas(self.hist_figure)
        self.hist_ax = self.hist_figure.add_subplot(111)
        self.hist_ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelbottom=False, labelleft=False)
        self.hist_figure.tight_layout()
        self.hist_figure.patch.set_facecolor('none')
        self.hist_ax.set_facecolor(colors.LIGHT_BACKGROUND)
        self.hist_ax.set_xlim(0, 65535)

        # FFT
        self.fft_figure = Figure(figsize=(3, 2), dpi=100)
        self.fft_canvas = FigureCanvas(self.fft_figure)
        self.fft_ax = self.fft_figure.add_subplot(111)
        self.fft_ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelbottom=False, labelleft=False)
        self.fft_figure.tight_layout()
        self.fft_figure.patch.set_facecolor('none')
        self.fft_ax.set_facecolor(colors.LIGHT_BACKGROUND)

        # Focus curve figure (defocus vs definition)
        self.focus_figure = Figure(figsize=(3, 2), dpi=100)
        self.focus_canvas = FigureCanvas(self.focus_figure)
        self.focus_ax = self.focus_figure.add_subplot(111)
        self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
        self.focus_figure.patch.set_facecolor('none')
        self.focus_figure.tight_layout()
        self._focus_x = []
        self._focus_y = []

        # tabs（仅 Histogram / FFT 放在上部标签页）
        from PyQt5.QtWidgets import QWidget, QVBoxLayout as QV
        hist_tab = QWidget(); hl = QV(hist_tab); hl.setContentsMargins(0,0,0,0); hl.addWidget(self.hist_canvas)
        fft_tab = QWidget(); fl = QV(fft_tab); fl.setContentsMargins(0,0,0,0); fl.addWidget(self.fft_canvas)
        self.tabs.addTab(hist_tab, "Histogram")
        self.tabs.addTab(fft_tab, "FFT")
        layout.addWidget(self.tabs, 3)

        # 中部信息（自动化信息）：改为显示 Focus Curve，取代原电镜信息文本
        mid_title = QLabel("自动化信息")
        mid_title.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; padding: 4px; background:#e0e0e0; border:1px solid #cccccc; }")
        layout.addWidget(mid_title)
        # 中部主体：Focus Curve 画布
        layout.addWidget(self.focus_canvas, 4)

        # 底部占位
        bottom = QLabel("预留区域（后续功能）")
        bottom.setAlignment(Qt.AlignCenter)
        bottom.setStyleSheet("QLabel { color:#777; border:1px dashed #bbbbbb; padding:6px; }")
        layout.addWidget(bottom, 1)

    # ---------- 对外 API ----------
    def update_analysis(self, image_array):
        try:
            if image_array is None:
                return
            arr = image_array
            if arr.ndim == 3:
                arr = arr.mean(axis=2)
            # hist
            self.hist_ax.cla()
            hist, bins = np.histogram(arr, bins=200, range=(0, 65535))
            self.hist_ax.plot(bins[:-1], hist, color=colors.TEXT_NORMAL, linewidth=1)
            self.hist_ax.fill_between(bins[:-1], hist, color=colors.TEXT_NORMAL, alpha=0.2)
            self.hist_ax.grid(True, alpha=0.2)
            self.hist_canvas.draw_idle()
            # fft
            self.fft_ax.cla(); self.fft_ax.axis('off')
            f = np.fft.fft2(arr.astype(np.float32))
            fshift = np.fft.fftshift(f)
            mag = np.log1p(np.abs(fshift))
            self.fft_ax.imshow(mag, cmap='gray')
            self.fft_canvas.draw_idle()
        except Exception:
            pass

    def set_snapshot(self, snapshot):
        # 中部已改为 Focus Curve，不再显示电镜信息；保持接口兼容，忽略或可用于未来扩展。
        return

    # ---------- Focus metric API ----------
    def reset_focus_curve(self):
        self._focus_x = []
        self._focus_y = []
        try:
            self.focus_ax.cla()
            self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
            self.focus_canvas.draw_idle()
        except Exception:
            pass

    def append_focus_point(self, defocus_um: float, definition_value: float):
        try:
            self._focus_x.append(float(defocus_um))
            self._focus_y.append(float(definition_value))
            # 绘制曲线
            self.focus_ax.cla()
            self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
            if len(self._focus_x) >= 1:
                pairs = sorted(zip(self._focus_x, self._focus_y), key=lambda p: p[0])
                xs, ys = zip(*pairs)
                self.focus_ax.plot(xs, ys, color='orange', linewidth=1.5, marker='o', markersize=3)
                self.focus_ax.grid(True, alpha=0.2)
                self.focus_ax.set_xlabel('Defocus (um)')
                self.focus_ax.set_ylabel('Definition')
            self.focus_canvas.draw_idle()
        except Exception:
            pass


