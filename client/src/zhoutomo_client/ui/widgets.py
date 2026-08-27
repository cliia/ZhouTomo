#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义控件模块 - 包含应用程序中使用的自定义UI控件
"""

import sys
import os
from PyQt5.QtWidgets import QLabel, QSizePolicy, QSpinBox, QDoubleSpinBox
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QEvent
from PyQt5.QtGui import QCursor, QPainter, QPen, QColor

try:
    # 添加项目根目录到路径以支持绝对导入
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from zhoutomo_client.config.colors import colors
except ImportError:
    # 如果无法导入，创建简单的颜色配置
    class SimpleColors:
        BORDER_COLOR = "#cccccc"
        LIGHTER_BACKGROUND = "#4d6b7e"
        TEXT_NORMAL = "#FFFFFF"
        BUTTON_BACKGROUND = "#273945"
        BUTTON_HOVER = "#394e5c"
        BUTTON_PRESSED = "#3daee9"
    colors = SimpleColors()


class ClickableLabel(QLabel):
    """可点击的标签控件"""
    clicked = pyqtSignal()
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)  # 防止文字换行
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HorizontalSpinBox(QSpinBox):
    """水平布局的SpinBox，支持按钮点击和双击编辑"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_mode = False
        self.setStyleSheet(self._get_style())
        self.setAlignment(Qt.AlignCenter)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def _get_style(self):
        """获取样式"""
        return f"""
            QSpinBox {{
                padding-left: 20px;
                padding-right: 20px;
                padding-top: 2px;
                padding-bottom: 2px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                font-size: 12px;
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                min-height: 16px;
                max-height: 24px;
                min-width: 80px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 18px;
                height: 22px;
                border: none;
                background-color: {colors.BUTTON_BACKGROUND};
                margin: 1px;
            }}
            QSpinBox::up-button {{
                subcontrol-position: center right;
            }}
            QSpinBox::down-button {{
                subcontrol-position: center left;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {colors.BUTTON_HOVER};
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: {colors.BUTTON_PRESSED};
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                image: none;
                width: 10px;
                height: 10px;
            }}
        """
    
    def paintEvent(self, event):
        """绘制自定义的+/-符号"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(colors.TEXT_NORMAL))
        pen.setWidth(2)
        painter.setPen(pen)
        
        rect = self.rect()
        
        # 绘制左侧减号 (-)
        painter.drawLine(6, rect.center().y(), 18, rect.center().y())
        
        # 绘制右侧加号 (+)
        x = rect.width() - 20
        y = rect.center().y()
        painter.drawLine(x + 4, y, x + 12, y)  # 水平线
        painter.drawLine(x + 8, y - 4, x + 8, y + 4)  # 垂直线
    
    def event(self, event):
        """事件处理"""
        if event.type() == QEvent.MouseButtonPress:
            return self._handle_mouse_press(event)
        elif event.type() == QEvent.MouseButtonDblClick:
            return self._handle_double_click(event)
        return super().event(event)
    
    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            rect = self.rect()
            left_area = rect.adjusted(0, 0, -(rect.width() - 20), 0)
            right_area = rect.adjusted(rect.width() - 20, 0, 0, 0)
            
            if left_area.contains(event.pos()):
                self.stepDown()
                return True
            elif right_area.contains(event.pos()):
                self.stepUp()
                return True
        return False
    
    def _handle_double_click(self, event):
        """处理双击事件"""
        if event.button() == Qt.LeftButton:
            rect = self.rect()
            left_area = rect.adjusted(0, 0, -(rect.width() - 20), 0)
            right_area = rect.adjusted(rect.width() - 20, 0, 0, 0)
            
            if not (left_area.contains(event.pos()) or right_area.contains(event.pos())):
                self.edit_mode = True
                self.setFocus()
                self.selectAll()
                return True
        return False
    
    def focusOutEvent(self, event):
        """失去焦点时退出编辑模式"""
        if self.edit_mode:
            self.edit_mode = False
        super().focusOutEvent(event)


class HorizontalDoubleSpinBox(QDoubleSpinBox):
    """水平布局的DoubleSpinBox，支持按钮点击和双击编辑"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_mode = False
        self.setStyleSheet(self._get_style())
        self.setAlignment(Qt.AlignCenter)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def _get_style(self):
        """获取样式"""
        return f"""
            QDoubleSpinBox {{
                padding-left: 20px;
                padding-right: 20px;
                padding-top: 2px;
                padding-bottom: 2px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                font-size: 12px;
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                min-height: 16px;
                max-height: 24px;
                min-width: 80px;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                width: 18px;
                height: 22px;
                border: none;
                background-color: {colors.BUTTON_BACKGROUND};
                margin: 1px;
            }}
            QDoubleSpinBox::up-button {{
                subcontrol-position: center right;
            }}
            QDoubleSpinBox::down-button {{
                subcontrol-position: center left;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors.BUTTON_HOVER};
            }}
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
                background-color: {colors.BUTTON_PRESSED};
            }}
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{
                image: none;
                width: 10px;
                height: 10px;
            }}
        """
    
    def paintEvent(self, event):
        """绘制自定义的+/-符号"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(colors.TEXT_NORMAL))
        pen.setWidth(2)
        painter.setPen(pen)
        
        rect = self.rect()
        
        # 绘制左侧减号 (-)
        painter.drawLine(6, rect.center().y(), 18, rect.center().y())
        
        # 绘制右侧加号 (+)
        x = rect.width() - 20
        y = rect.center().y()
        painter.drawLine(x + 4, y, x + 12, y)  # 水平线
        painter.drawLine(x + 8, y - 4, x + 8, y + 4)  # 垂直线
    
    def event(self, event):
        """事件处理"""
        if event.type() == QEvent.MouseButtonPress:
            return self._handle_mouse_press(event)
        elif event.type() == QEvent.MouseButtonDblClick:
            return self._handle_double_click(event)
        return super().event(event)
    
    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            rect = self.rect()
            left_area = rect.adjusted(0, 0, -(rect.width() - 20), 0)
            right_area = rect.adjusted(rect.width() - 20, 0, 0, 0)
            
            if left_area.contains(event.pos()):
                self.stepDown()
                return True
            elif right_area.contains(event.pos()):
                self.stepUp()
                return True
        return False
    
    def _handle_double_click(self, event):
        """处理双击事件"""
        if event.button() == Qt.LeftButton:
            rect = self.rect()
            left_area = rect.adjusted(0, 0, -(rect.width() - 20), 0)
            right_area = rect.adjusted(rect.width() - 20, 0, 0, 0)
            
            if not (left_area.contains(event.pos()) or right_area.contains(event.pos())):
                self.edit_mode = True
                self.setFocus()
                self.selectAll()
                return True
        return False
    
    def focusOutEvent(self, event):
        """失去焦点时退出编辑模式"""
        if self.edit_mode:
            self.edit_mode = False
        super().focusOutEvent(event)
