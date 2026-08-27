#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动画面组件 - 显示程序启动时的欢迎界面
"""

import sys
import os
from PyQt5.QtWidgets import QSplashScreen, QApplication, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QEventLoop
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor

try:
    # 添加项目根目录到路径以支持绝对导入
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from config.colors import colors
except ImportError:
    # 如果无法导入，创建简单的颜色配置
    class SimpleColors:
        TEXT_NORMAL = "#FFFFFF"
        BUTTON_PRESSED = "#3daee9"
    
    colors = SimpleColors()


class SplashScreen(QSplashScreen):
    """自定义启动画面类"""
    
    # 定义信号
    progressUpdated = pyqtSignal(int, str)  # 进度更新信号
    initializationComplete = pyqtSignal()   # 初始化完成信号
    
    def __init__(self, background_path=None):
        """
        初始化启动画面
        
        Args:
            background_path: 背景图片路径
        """
        # 设置默认背景图片路径
        if background_path is None:
            background_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'resources', 'background', 'startup_background.jpg'
            )
        
        # 加载背景图片
        self.background_pixmap = self.load_background_image(background_path)
        
        # 初始化QSplashScreen
        super().__init__(self.background_pixmap, Qt.WindowStaysOnTopHint)
        
        # 设置窗口属性
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 初始化进度相关
        self.progress = 0
        self.status_text = "正在启动 ZhouTomo..."
        
        # 设置字体
        self.font = QFont("Microsoft YaHei", 12)
        self.title_font = QFont("Microsoft YaHei", 16, QFont.Bold)
        
        # 显示启动画面
        self.show()
        
        # 确保窗口显示在屏幕中央
        self.center_on_screen()
        
        # 启动初始化过程
        self.start_initialization()
    
    def load_background_image(self, image_path):
        """
        加载并处理背景图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            QPixmap: 处理后的图片
        """
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # 设置合适的大小
            if not pixmap.isNull():
                # 缩放到合适的启动画面大小
                scaled_pixmap = pixmap.scaled(600, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return scaled_pixmap
        
        # 如果图片加载失败，创建一个默认的启动画面
        pixmap = QPixmap(600, 400)
        pixmap.fill(QColor(39, 57, 69))  # 使用主题颜色
        
        # 在默认背景上绘制标题
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制标题
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 28, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "ZhouTomo\n图像处理工具")
        
        painter.end()
        return pixmap
    
    def center_on_screen(self):
        """将窗口居中显示"""
        screen = QApplication.desktop().screenGeometry()
        splash_geometry = self.geometry()
        x = (screen.width() - splash_geometry.width()) // 2
        y = (screen.height() - splash_geometry.height()) // 2
        self.move(x, y)
    
    def start_initialization(self):
        """启动初始化过程"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(10)  # 每100ms更新一次
        
        # 初始化步骤
        self.init_steps = [
            (10, "正在加载配置文件..."),
            (25, "正在初始化资源管理器..."),
            (40, "正在加载图标资源..."),
            (55, "正在创建用户界面..."),
            (70, "正在初始化工具栏..."),
            (85, "正在配置菜单系统..."),
            (95, "正在完成初始化..."),
            (100, "启动完成!")
        ]
        
        self.current_step = 0
        self.elapsed_time = 0
        self.min_display_time = 1000  # 最少显示3秒
    
    def update_progress(self):
        """更新进度条和状态文本"""
        self.elapsed_time += 100
        
        # 根据时间和步骤更新进度
        if self.current_step < len(self.init_steps):
            target_progress, status = self.init_steps[self.current_step]
            
            # 模拟加载过程
            if self.progress < target_progress:
                self.progress += 2
                if self.progress >= target_progress:
                    self.status_text = status
                    self.current_step += 1
            
            # 发送进度更新信号
            self.progressUpdated.emit(self.progress, self.status_text)
            
            # 重绘启动画面
            self.repaint()
        
        # 检查是否达到最小显示时间且初始化完成
        if self.elapsed_time >= self.min_display_time and self.progress >= 100:
            self.timer.stop()
            self.initializationComplete.emit()
    
    def drawContents(self, painter):
        """重写绘制内容方法"""
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明遮罩
        overlay = QColor(0, 0, 0, 120)
        painter.fillRect(self.rect(), overlay)
        
        # 设置文字颜色
        painter.setPen(QColor(255, 255, 255))
        
        # 绘制应用程序标题
        painter.setFont(self.title_font)
        title_rect = self.rect()
        title_rect.setBottom(title_rect.bottom() - 120)
        painter.drawText(title_rect, Qt.AlignCenter, "ZhouTomo 图像处理工具")
        
        # 绘制版本信息
        painter.setFont(QFont("Microsoft YaHei", 10))
        version_rect = self.rect()
        version_rect.setTop(version_rect.bottom() - 110)
        version_rect.setBottom(version_rect.bottom() - 90)
        painter.drawText(version_rect, Qt.AlignCenter, "Version 2.0")
        
        # 绘制状态文本
        painter.setFont(self.font)
        status_rect = self.rect()
        status_rect.setTop(status_rect.bottom() - 70)
        status_rect.setBottom(status_rect.bottom() - 50)
        painter.drawText(status_rect, Qt.AlignCenter, self.status_text)
        
        # 绘制进度条
        progress_rect = self.rect()
        progress_rect.setTop(progress_rect.bottom() - 40)
        progress_rect.setBottom(progress_rect.bottom() - 30)
        progress_rect.setLeft(progress_rect.left() + 50)
        progress_rect.setRight(progress_rect.right() - 50)
        
        # 进度条背景
        painter.setPen(QColor(100, 100, 100))
        painter.setBrush(QColor(50, 50, 50))
        painter.drawRoundedRect(progress_rect, 5, 5)
        
        # 进度条前景
        if self.progress > 0:
            filled_width = int(progress_rect.width() * self.progress / 100)
            filled_rect = progress_rect
            filled_rect.setWidth(filled_width)
            
            painter.setPen(QColor(61, 174, 233))
            painter.setBrush(QColor(61, 174, 233))
            painter.drawRoundedRect(filled_rect, 5, 5)
        
        # 绘制进度百分比
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 9))
        progress_text_rect = self.rect()
        progress_text_rect.setTop(progress_text_rect.bottom() - 25)
        progress_text_rect.setBottom(progress_text_rect.bottom() - 10)
        painter.drawText(progress_text_rect, Qt.AlignCenter, f"{self.progress}%")
    
    def showMessage(self, message, alignment=Qt.AlignBottom, color=Qt.white):
        """重写showMessage方法以自定义消息显示"""
        self.status_text = message
        self.repaint()
    
    def finish_splash(self, main_window):
        """完成启动画面并显示主窗口"""
        # 平滑过渡到主窗口
        self.finish(main_window)


def show_splash_screen():
    """显示启动画面的便利函数"""
    return SplashScreen()
