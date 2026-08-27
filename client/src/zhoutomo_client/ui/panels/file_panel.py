#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧目标文件面板：封装 QListWidget 自定义项（带单选按钮），对外提供添加/选择/删除/重命名 API。
"""

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QListView, QAbstractItemView, QSizePolicy, QMenu, QAction, QInputDialog, QGridLayout, QHBoxLayout, QRadioButton
from PyQt5.QtGui import QPixmap

from zhoutomo_client.config.colors import colors


class FilePanel(QWidget):
    """目标列表面板。"""

    targetSelected = pyqtSignal(str)
    targetDeleted = pyqtSignal(str)
    targetRenamed = pyqtSignal(str, str)
    targetExportTiltSeries = pyqtSignal(str)
    targetExportTiltSeriesMat = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._radio_group = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 0, 0)
        layout.setSpacing(0)

        title = QLabel("目标列表")
        title.setStyleSheet(f"""
            QLabel {{ font-weight: bold; font-size: 12px; font-family: Microsoft YaHei; color: {colors.TEXT_NORMAL}; padding: 0px; background-color: {colors.DARK_BACKGROUND}; border: 1px solid {colors.BORDER_COLOR}; }}
        """)
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(True)
        self.list.setMovement(QListView.Static)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setIconSize(QSize(120, 120))
        self.list.setGridSize(QSize(140, 160))
        self.list.setSpacing(0)
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(True)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list.setStyleSheet(f"""
            QListWidget {{ border: 1px solid {colors.BORDER_COLOR}; background-color: {colors.LIGHT_BACKGROUND}; }}
            QListWidget::item {{ padding: 4px; }}
            QListWidget::item:selected {{ background: {colors.BUTTON_HOVER}; }}
        """)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list)

    # ------------- 对外 API -------------
    def set_button_group(self, group):
        self._radio_group = group

    def add_target(self, target_id: str, pixmap: QPixmap, name: str):
        widget = _TargetItemWidget(pixmap, name, target_id, self._radio_group, self.list)
        item = QListWidgetItem(self.list)
        item.setSizeHint(QSize(140, 160))
        item.setData(Qt.UserRole, target_id)
        self.list.addItem(item)
        self.list.setItemWidget(item, widget)
        self.list.scrollToBottom()
        return item

    def find_item_by_target_id(self, target_id: str):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item and item.data(Qt.UserRole) == target_id:
                return item
        return None

    # ------------- 私有 -------------
    def _on_context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        a_select = QAction("选择", self)
        a_export = QAction("导出倾转序列", self)
        a_export_mat = QAction("导出倾转序列为 MATLAB (.mat)", self)
        a_rename = QAction("重命名", self)
        a_delete = QAction("删除", self)
        menu.addAction(a_select)
        menu.addAction(a_export)
        menu.addAction(a_export_mat)
        menu.addSeparator()
        menu.addAction(a_rename)
        menu.addAction(a_delete)

        def do_select():
            self.list.setCurrentItem(item)
            widget = self.list.itemWidget(item)
            if widget and hasattr(widget, 'radio'):
                widget.radio.setChecked(True)
            tid = item.data(Qt.UserRole)
            self.targetSelected.emit(tid)

        def do_rename():
            widget = self.list.itemWidget(item)
            if widget and hasattr(widget, 'name_label'):
                new_name, ok = QInputDialog.getText(self, "重命名", "名称:", text=widget.name_label.text())
                if ok and new_name.strip():
                    widget.name_label.setText(new_name.strip())
                    self.targetRenamed.emit(item.data(Qt.UserRole), new_name.strip())

        def do_delete():
            row = self.list.row(item)
            tid = item.data(Qt.UserRole)
            it = self.list.takeItem(row)
            del it
            self.targetDeleted.emit(tid)

        a_select.triggered.connect(do_select)
        a_export.triggered.connect(lambda: self.targetExportTiltSeries.emit(item.data(Qt.UserRole)))
        a_export_mat.triggered.connect(lambda: self.targetExportTiltSeriesMat.emit(item.data(Qt.UserRole)))
        a_rename.triggered.connect(do_rename)
        a_delete.triggered.connect(do_delete)
        menu.exec_(self.list.mapToGlobal(pos))


class _TargetItemWidget(QWidget):
    def __init__(self, pixmap: QPixmap, name: str, target_id: str, radio_group, parent=None):
        super().__init__(parent)
        self.target_id = target_id
        self.setFixedSize(140, 160)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)
        # 顶部图像容器
        img_container = QWidget(self)
        img_container.setFixedSize(132, 124)
        img_container.setStyleSheet("background: transparent;")
        grid = QGridLayout(img_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        # 图片
        img_label = QLabel(img_container)
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        grid.addWidget(img_label, 0, 0, 1, 1)
        # 覆盖单选
        overlay = QWidget(img_container)
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        overlay_layout = QHBoxLayout(overlay)
        overlay_layout.setContentsMargins(2, 2, 0, 0)
        overlay_layout.setSpacing(0)
        radio = QRadioButton(overlay)
        radio.setFixedSize(16, 16)
        radio.setStyleSheet("QRadioButton::indicator { width: 16px; height: 16px; }")
        overlay_layout.addWidget(radio, 0, Qt.AlignLeft | Qt.AlignTop)
        grid.addWidget(overlay, 0, 0, 1, 1, Qt.AlignLeft | Qt.AlignTop)
        v.addWidget(img_container, 0, Qt.AlignCenter)
        # 名称
        name_label = QLabel(name, self)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(f"""
            QLabel {{ font-size: 12px; font-weight: normal; font-family: Microsoft YaHei; color: {colors.TEXT_NORMAL}; background-color: transparent; }}
        """)
        name_label.setWordWrap(True)
        v.addWidget(name_label, 0)
        self.radio = radio
        self.name_label = name_label
        if radio_group is not None:
            radio_group.addButton(radio)


