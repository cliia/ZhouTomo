#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZhouTomo 图像处理工具 - 主程序入口
"""

import sys
import os
import logging
import asyncio
import qasync
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# 添加view模块到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'view'))

from view.splash_screen import SplashScreen
from view.main_window import MainWindow
from config.colors import colors

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('main.log', encoding='utf-8')
    ],
    force=True
)
logger = logging.getLogger(__name__)


def main():
    """主程序入口函数"""
    app = QApplication(sys.argv)
    
    # 全局滚动条样式（统一扁平化风格）
    def _build_global_scrollbar_qss():
        return f"""
        QScrollBar:vertical {{
            background: {colors.LIGHT_BACKGROUND};
            width: 12px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {colors.BUTTON_HOVER};
            min-height: 24px;
            border-radius: 4px;
            border: 1px solid {colors.BORDER_COLOR};
        }}
        QScrollBar::handle:vertical:hover {{
            background: {colors.BUTTON_PRESSED};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: {colors.LIGHT_BACKGROUND};
        }}

        QScrollBar:horizontal {{
            background: {colors.LIGHT_BACKGROUND};
            height: 12px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {colors.BUTTON_HOVER};
            min-width: 24px;
            border-radius: 4px;
            border: 1px solid {colors.BORDER_COLOR};
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {colors.BUTTON_PRESSED};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: {colors.LIGHT_BACKGROUND};
        }}
        """

    qss = _build_global_scrollbar_qss()
    app.setStyleSheet(app.styleSheet() + qss if app.styleSheet() else qss)
    
    # 创建并显示启动画面
    splash = SplashScreen()
    
    # 创建主窗口（但不立即显示）
    main_window = None
    
    def on_initialization_complete():
        """初始化完成后的回调"""
        nonlocal main_window
        
        # 创建主窗口
        main_window = MainWindow()
        
        # 结束启动画面并显示主窗口
        splash.finish_splash(main_window)
        main_window.show()
    
    # 连接初始化完成信号
    splash.initializationComplete.connect(on_initialization_complete)
    
    # 使用 qasync 集成 Qt 与 asyncio，避免异步任务阻塞 UI
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        return loop.run_forever()


if __name__ == '__main__':
    sys.exit(main())
