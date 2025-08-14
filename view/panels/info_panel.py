#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧信息面板：上（Histogram/FFT tabs）、中（信息文本）、下（预留）。
对外暴露 update_analysis(image_array) 与 set_snapshot(snapshot)。
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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

        # tabs（仅 Histogram / FFT 放在上部标签页）
        from PyQt5.QtWidgets import QWidget, QVBoxLayout as QV
        hist_tab = QWidget(); hl = QV(hist_tab); hl.setContentsMargins(0,0,0,0); hl.addWidget(self.hist_canvas)
        fft_tab = QWidget(); fl = QV(fft_tab); fl.setContentsMargins(0,0,0,0); fl.addWidget(self.fft_canvas)
        self.tabs.addTab(hist_tab, "Histogram")
        self.tabs.addTab(fft_tab, "FFT")

        # 中部信息（自动化信息）：改为显示 Focus Curve，取代原电镜信息文本
        mid_title = QLabel("自动化信息")
        mid_title.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; padding: 4px; background:#e0e0e0; border:1px solid #cccccc; }")

        # Focus curve figure (defocus vs definition)
        self.focus_figure = Figure(figsize=(3, 2), dpi=100)
        self.focus_canvas = FigureCanvas(self.focus_figure)
        self.focus_ax = self.focus_figure.add_subplot(111)
        self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
        # 删除 spines
        self.focus_ax.spines['top'].set_visible(False)
        self.focus_ax.spines['right'].set_visible(False)
        self.focus_ax.spines['bottom'].set_visible(False)
        self.focus_ax.spines['left'].set_visible(False)
        # 设置 ticks
        self.focus_ax.set_xticks([])
        self.focus_ax.set_yticks([])
        # 设置标签
        self.focus_figure.patch.set_facecolor('none')
        self.focus_figure.tight_layout()
        self._focus_x = []
        self._focus_y = []

        # 组装中部容器（标题 + Focus Curve + ROI 预览）
        mid_container = QWidget()
        mid_layout = QVBoxLayout(mid_container)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)
        mid_layout.addWidget(mid_title)
        mid_layout.addWidget(self.focus_canvas, 3)

        # ROI 预览（复刻旧版 sample figure）
        self.roi_figure = Figure(figsize=(3, 1.5), dpi=100)
        self.roi_canvas = FigureCanvas(self.roi_figure)
        self.roi_ax = self.roi_figure.add_subplot(111)
        self.roi_ax.axis('off')
        self.roi_figure.patch.set_facecolor('none')
        self.roi_ax.set_facecolor(colors.LIGHT_BACKGROUND)
        mid_layout.addWidget(self.roi_canvas, 2)

        # 底部：设备关键参数监视（两列表格：键 | 值）
        keys = [
            ("Projection.Defocus", "-"),
            ("Stage (x,y,z,a,b)", "-"),
            ("Magnification", "-"),
            ("ImageSize", "-")
        ]
        self.kv_table = QTableWidget(len(keys), 2)
        self.kv_table.setHorizontalHeaderLabels(["键", "值"])
        self.kv_table.verticalHeader().setVisible(False)
        self.kv_table.horizontalHeader().setStretchLastSection(True)
        self.kv_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.kv_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.kv_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kv_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.kv_table.setFocusPolicy(Qt.NoFocus)
        self.kv_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {colors.DARK_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                gridline-color: {colors.BORDER_COLOR};
                border: 1px dashed #555;
                font-family: Microsoft YaHei;
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {colors.LIGHT_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                border: 1px solid {colors.BORDER_COLOR};
                font-weight: bold;
                padding: 4px;
            }}
        """)
        # 建立键到行索引映射，便于后续更新
        self._kv_row_map = {}
        for row, (k, v) in enumerate(keys):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            val_item = QTableWidgetItem(str(v))
            val_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.kv_table.setItem(row, 0, key_item)
            self.kv_table.setItem(row, 1, val_item)
            self._kv_row_map[k] = row
        # 使用垂直分割器组织三部分：顶部 tabs / 中部曲线 / 底部表格
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.tabs)
        splitter.addWidget(mid_container)
        splitter.addWidget(self.kv_table)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter)


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
        # 扩展：允许从 snapshot/状态中更新底部关键参数（若调用方提供）
        try:
            if not isinstance(snapshot, dict):
                return
            proj = snapshot.get('projection') or {}
            defocus = proj.get('defocus', '-')
            stage = snapshot.get('stage') or {}
            pos = stage.get('position', stage)
            x = pos.get('x', '-')
            y = pos.get('y', '-')
            z = pos.get('z', '-')
            a = pos.get('a', '-')
            b = pos.get('b', '-')
            acq = snapshot.get('acquisition') or {}
            mag = snapshot.get('illumination', {}).get('stem_magnification', '-')
            img_size = acq.get('acq_image_size', '-')
            # 更新表格中的值列
            if hasattr(self, 'kv_table') and hasattr(self, '_kv_row_map'):
                def set_val(key, value):
                    row = self._kv_row_map.get(key)
                    if row is None:
                        return
                    item = self.kv_table.item(row, 1)
                    if item is None:
                        item = QTableWidgetItem("")
                        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        self.kv_table.setItem(row, 1, item)
                    item.setText(str(value))

                set_val("Projection.Defocus", defocus)
                set_val("Stage (x,y,z,a,b)", f"({x}, {y}, {z}, {a}, {b})")
                set_val("Magnification", mag)
                set_val("ImageSize", img_size)
        except Exception:
            pass

    # ---------- Focus metric API ----------
    def reset_focus_curve(self):
        self._focus_x = []
        self._focus_y = []
        try:
            self.focus_ax.cla()
            self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
            self.focus_canvas.draw_idle()
            self.roi_ax.cla(); self.roi_ax.axis('off'); self.roi_canvas.draw_idle()
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

    def update_focus_curves(self, raw_x_m: list, raw_y: list, smooth_x_m: list, smooth_y: list):
        try:
            # 将米转换为微米以匹配坐标轴
            rx = [float(v) * 1e6 for v in (raw_x_m or [])]
            sx = [float(v) * 1e6 for v in (smooth_x_m or [])]
            ry = [float(v) for v in (raw_y or [])]
            sy = [float(v) for v in (smooth_y or [])]
            self.focus_ax.cla()
            self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
            if rx and ry:
                pairs = sorted(zip(rx, ry), key=lambda p: p[0])
                xs, ys = zip(*pairs)
                self.focus_ax.plot(xs, ys, color='orange', linewidth=1.0, marker='o', markersize=3, label='raw')
            if sx and sy:
                pairs_s = sorted(zip(sx, sy), key=lambda p: p[0])
                xs2, ys2 = zip(*pairs_s)
                self.focus_ax.plot(xs2, ys2, color='steelblue', linewidth=1.5, label='smoothed')
            self.focus_ax.grid(True, alpha=0.2)
            self.focus_ax.set_xlabel('Defocus (um)')
            self.focus_ax.set_ylabel('Definition')
            if (rx and ry) or (sx and sy):
                self.focus_ax.legend(loc='best', fontsize=8)
            self.focus_canvas.draw_idle()
        except Exception:
            pass

    def set_sample_roi(self, roi_array):
        try:
            if roi_array is None:
                return
            import numpy as np
            arr = np.asarray(roi_array)
            if arr.ndim == 3:
                arr = arr.mean(axis=2)
            self.roi_ax.cla(); self.roi_ax.axis('off')
            self.roi_ax.imshow(arr, cmap='gray')
            self.roi_canvas.draw_idle()
        except Exception:
            pass


