#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧信息面板：上（Histogram/FFT tabs）、中（信息文本）、下（预留）。
对外暴露 update_analysis(image_array) 与 set_snapshot(snapshot)。
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from zhoutomo_client.config.colors import colors
import numpy as np


class InfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        # 节流定时器：聚焦曲线重绘集中处理，避免高频信号造成UI卡顿
        self._focus_redraw_timer = QTimer(self)
        self._focus_redraw_timer.setSingleShot(True)
        self._focus_redraw_timer.setInterval(50)  # 50ms内聚合多次更新
        self._focus_redraw_timer.timeout.connect(self._redraw_focus_curve)


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

        # Focus curve figure (defocus vs definition) - AF 面板内容
        self.focus_figure = Figure(figsize=(3, 2), dpi=100)
        self.focus_canvas = FigureCanvas(self.focus_figure)
        self.focus_ax = self.focus_figure.add_subplot(111)
        self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
        # 轴字体与边距设置（确保标签可见）
        self._focus_font = {'family': 'Arial', 'size': 14}
        try:
            self.focus_figure.subplots_adjust(left=0.18, bottom=0.22, right=0.98, top=0.98)
        except Exception:
            pass
        # 恢复 spines 并设置线宽
        try:
            for sp in self.focus_ax.spines.values():
                sp.set_visible(True)
                sp.set_linewidth(1)
        except Exception:
            pass
        # 恢复刻度显示并设置字体大小
        try:
            self.focus_ax.tick_params(axis='both', labelsize=self._focus_font['size'])
        except Exception:
            pass
        self.focus_figure.patch.set_facecolor('none')
        self.focus_figure.tight_layout()
        self._focus_x = []
        self._focus_y = []

        # ROI 预览（复刻旧版 sample figure） - AF 面板内容
        self.roi_figure = Figure(figsize=(3, 1.5), dpi=100)
        self.roi_canvas = FigureCanvas(self.roi_figure)
        self.roi_ax = self.roi_figure.add_subplot(111)
        self.roi_ax.axis('off')
        self.roi_figure.patch.set_facecolor('none')
        self.roi_ax.set_facecolor(colors.LIGHT_BACKGROUND)

        # ----- 中部：改为 TabWidget，包含 AF 与 AT 两个子页 -----
        self.automation_tabs = QTabWidget()
        self.automation_tabs.setTabPosition(QTabWidget.North)
        self.automation_tabs.setContentsMargins(0, 0, 0, 0)
        self.automation_tabs.setStyleSheet(f"""
            QTabWidget {{ background-color: {colors.DARK_BACKGROUND}; border: 0px; color: {colors.TEXT_NORMAL}; font-family: Microsoft YaHei; font-size: 12px; font-weight: bold; }}
            QTabWidget::pane {{ border: 1px solid {colors.BORDER_COLOR}; top: -1px; margin: 0px; padding: 0px; }}
            QStackedWidget {{ background-color: {colors.DARK_BACKGROUND}; border: 0px; margin: 0px; padding: 0px; }}
            QTabBar::tab {{ background-color: {colors.DARK_BACKGROUND}; border: 1px solid {colors.BORDER_COLOR}; color: {colors.TEXT_NORMAL}; font-family: Microsoft YaHei; font-size: 12px; font-weight: bold; padding: 5px 10px; }}
            QTabBar::tab:selected {{ background-color: {colors.BUTTON_HOVER}; color: {colors.TEXT_NORMAL}; }}
            QTabBar::tab:hover {{ background-color: {colors.BUTTON_HOVER}; color: {colors.TEXT_NORMAL}; }}
        """)

        # AF 子页
        af_tab = QWidget()
        af_layout = QVBoxLayout(af_tab)
        af_layout.setContentsMargins(0, 0, 0, 0)
        af_layout.setSpacing(4)
        af_layout.addWidget(self.focus_canvas, 3)
        af_layout.addWidget(self.roi_canvas, 2)

        # AT 子页：显示当前 alpha 与对焦状态
        at_tab = QWidget()
        at_layout = QVBoxLayout(at_tab)
        at_layout.setContentsMargins(8, 8, 8, 8)
        at_layout.setSpacing(8)
        row1 = QHBoxLayout();
        lbl_alpha_title = QLabel("当前 Alpha (°)：");
        lbl_alpha_title.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
                font-size: 12px;
            }}
        """)
        self.at_alpha_label = QLabel("-")
        row1.addWidget(lbl_alpha_title)
        row1.addWidget(self.at_alpha_label)
        row1.addStretch()
        row2 = QHBoxLayout();
        lbl_status_title = QLabel("对焦状态：");
        lbl_status_title.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
                font-size: 12px;
            }}
        """)
        self.at_status_label = QLabel("-")
        row2.addWidget(lbl_status_title)
        row2.addWidget(self.at_status_label)
        row2.addStretch()
        # 进度条
        self.at_progress = QProgressBar()
        self.at_progress.setRange(0, 100)
        self.at_progress.setValue(0)
        self.at_progress.setTextVisible(True)
        self.at_progress.setFormat("0% (0/0)")
        self.at_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {colors.DARK_BACKGROUND};
                border: 1px solid {colors.BORDER_COLOR};
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
                font-size: 12px;
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {colors.BUTTON_HOVER};
            }}
        """)
        # 角度列表表格
        self.at_table = QTableWidget(0, 3)
        self.at_table.setHorizontalHeaderLabels(["#", "Alpha (°)", "状态"])
        self.at_table.verticalHeader().setVisible(False)
        self.at_table.horizontalHeader().setStretchLastSection(True)
        self.at_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.at_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.at_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.at_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.at_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.at_table.setFocusPolicy(Qt.NoFocus)
        self.at_table.setStyleSheet(f"""
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
        # 内部状态
        self._at_plan = []  # List[float]
        self._at_row_map = {}  # alpha_key(str) -> row index
        self._at_completed = 0
        self._at_total = 0
        # 组装布局
        at_layout.addLayout(row1)
        at_layout.addLayout(row2)
        at_layout.addWidget(self.at_progress)
        at_layout.addWidget(self.at_table, 1)

        self.automation_tabs.addTab(af_tab, "Auto Focus")
        self.automation_tabs.addTab(at_tab, "Auto Tilt")

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
        splitter.addWidget(self.automation_tabs)
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
            # 统一样式（字体、spines、刻度与边距）
            try:
                self.focus_figure.subplots_adjust(left=0.18, bottom=0.22, right=0.98, top=0.98)
            except Exception:
                pass
            try:
                for sp in self.focus_ax.spines.values():
                    sp.set_visible(True)
                    sp.set_linewidth(1)
            except Exception:
                pass
            try:
                self.focus_ax.tick_params(axis='both', labelsize=self._focus_font['size'])
            except Exception:
                pass
            self.focus_canvas.draw_idle()
            self.roi_ax.cla(); self.roi_ax.axis('off'); self.roi_canvas.draw_idle()
        except Exception:
            pass

    def append_focus_point(self, defocus_um: float, definition_value: float):
        try:
            self._focus_x.append(float(defocus_um))
            self._focus_y.append(float(definition_value))
            # 触发节流重绘
            if not self._focus_redraw_timer.isActive():
                self._focus_redraw_timer.start()
        except Exception:
            pass

    def update_focus_curves(self, raw_x_m: list, raw_y: list, smooth_x_m: list, smooth_y: list):
        try:
            # 覆盖为最新曲线数据缓存（以便节流重绘）
            self._focus_raw_x_m = list(map(float, raw_x_m or []))
            self._focus_raw_y = list(map(float, raw_y or []))
            self._focus_smooth_x_m = list(map(float, smooth_x_m or []))
            self._focus_smooth_y = list(map(float, smooth_y or []))
            if not self._focus_redraw_timer.isActive():
                self._focus_redraw_timer.start()
        except Exception:
            pass

    def _redraw_focus_curve(self):
        """集中重绘聚焦曲线，合并 append_focus_point 与 update_focus_curves 的更新。"""
        try:
            self.focus_ax.cla()
            self.focus_ax.set_facecolor(colors.LIGHT_BACKGROUND)
            # 统一样式（字体、spines、刻度与边距）
            try:
                self.focus_figure.subplots_adjust(left=0.18, bottom=0.22, right=0.98, top=0.98)
            except Exception:
                pass
            try:
                for sp in self.focus_ax.spines.values():
                    sp.set_visible(True)
                    sp.set_linewidth(1)
            except Exception:
                pass
            try:
                self.focus_ax.tick_params(axis='both', labelsize=self._focus_font['size'])
            except Exception:
                pass
            # 先绘制原始采样点（append_focus_point 累积的点）
            if len(self._focus_x) >= 1 and len(self._focus_y) == len(self._focus_x):
                pairs_local = sorted(zip(self._focus_x, self._focus_y), key=lambda p: p[0])
                xs_l, ys_l = zip(*pairs_local)
                self.focus_ax.plot(xs_l, ys_l, color='orange', linewidth=1.0, marker='o', markersize=3, label='raw(local)')
            # 再绘制控制器提供的平滑曲线（若有）
            rx = [v * 1e6 for v in getattr(self, '_focus_raw_x_m', [])]
            ry = list(getattr(self, '_focus_raw_y', []))
            sx = [v * 1e6 for v in getattr(self, '_focus_smooth_x_m', [])]
            sy = list(getattr(self, '_focus_smooth_y', []))
            if rx and ry:
                pairs = sorted(zip(rx, ry), key=lambda p: p[0])
                xs, ys = zip(*pairs)
                self.focus_ax.plot(xs, ys, color='chocolate', linewidth=1.0, marker='.', markersize=2, alpha=0.7, label='raw(controller)')
            if sx and sy:
                pairs_s = sorted(zip(sx, sy), key=lambda p: p[0])
                xs2, ys2 = zip(*pairs_s)
                self.focus_ax.plot(xs2, ys2, color='steelblue', linewidth=1.5, label='smoothed')
            self.focus_ax.grid(True, alpha=0.2)
            self.focus_ax.set_xlabel('Defocus (um)', fontdict=self._focus_font)
            self.focus_ax.set_ylabel('Definition', fontdict=self._focus_font)
            has_any = (len(self._focus_x) > 0) or (rx and ry) or (sx and sy)
            if has_any:
                try:
                    self.focus_ax.legend(loc='best', prop={'family': self._focus_font['family'], 'size': self._focus_font['size']})
                except Exception:
                    self.focus_ax.legend(loc='best', fontsize=self._focus_font['size'])
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

    # ---------- Auto Tilt 面板 API ----------
    def set_autotilt_alpha(self, alpha_deg: float):
        try:
            if hasattr(self, 'at_alpha_label'):
                self.at_alpha_label.setText(f"{float(alpha_deg):.2f}")
            # 高亮当前行
            try:
                row = self._row_for_alpha(alpha_deg)
                if row is not None:
                    self._set_status_row(row, "进行中", QColor(255, 200, 120))
                    self.at_table.selectRow(row)
            except Exception:
                pass
        except Exception:
            pass

    def set_autotilt_status(self, status_text: str):
        try:
            if hasattr(self, 'at_status_label'):
                self.at_status_label.setText(str(status_text))
        except Exception:
            pass

    # ---------- Auto Tilt 进度/计划 API ----------
    def set_autotilt_plan(self, sequence):
        """设置将要采集的角度序列，并初始化表格与进度。"""
        try:
            seq = list(sequence or [])
            self._at_plan = [float(v) for v in seq]
            self._at_total = len(self._at_plan)
            self._at_completed = 0
            # 清表
            self.at_table.setRowCount(0)
            self._at_row_map = {}
            for idx, a in enumerate(self._at_plan, start=1):
                row = self.at_table.rowCount()
                self.at_table.insertRow(row)
                # 列0: 序号
                item_idx = QTableWidgetItem(str(idx))
                item_idx.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                # 列1: Alpha 值
                item_alpha = QTableWidgetItem(f"{a:.2f}")
                item_alpha.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                # 列2: 状态
                item_status = QTableWidgetItem("待采集")
                item_status.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.at_table.setItem(row, 0, item_idx)
                self.at_table.setItem(row, 1, item_alpha)
                self.at_table.setItem(row, 2, item_status)
                self._at_row_map[self._alpha_key(a)] = row
            # 重置进度
            self.set_autotilt_progress(0, self._at_total)
        except Exception:
            pass

    def set_autotilt_progress(self, completed: int, total: int):
        """设置进度条完成度。"""
        try:
            completed = max(0, int(completed))
            total = max(0, int(total))
            self._at_completed = completed
            self._at_total = total
            pct = int(round((completed / total) * 100)) if total > 0 else 0
            self.at_progress.setValue(pct)
            self.at_progress.setFormat(f"{pct}% ({completed}/{total})")
        except Exception:
            pass

    def mark_autotilt_angle_done(self, alpha_deg: float):
        """将指定角度标记为完成。"""
        try:
            row = self._row_for_alpha(alpha_deg)
            if row is not None:
                self._set_status_row(row, "✓ 完成", QColor(170, 220, 170))
                self.set_autotilt_progress(self._at_completed + 1, self._at_total)
        except Exception:
            pass

    # ---------- 内部辅助 ----------
    def _alpha_key(self, alpha: float) -> str:
        # 以两位小数规整，避免浮点比较误差
        try:
            return f"{float(alpha):.2f}"
        except Exception:
            return str(alpha)

    def _row_for_alpha(self, alpha: float):
        try:
            return self._at_row_map.get(self._alpha_key(alpha))
        except Exception:
            return None

    def _set_status_row(self, row: int, text: str, bg_color: QColor = None):
        try:
            item = self.at_table.item(row, 2)
            if item is None:
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.at_table.setItem(row, 2, item)
            item.setText(text)
            # 设置整行背景色以突出状态
            for col in range(self.at_table.columnCount()):
                ci = self.at_table.item(row, col)
                if ci is None:
                    ci = QTableWidgetItem("")
                    ci.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    self.at_table.setItem(row, col, ci)
                if bg_color is not None:
                    ci.setBackground(bg_color)
                else:
                    ci.setBackground(QColor(0,0,0,0))
        except Exception:
            pass


