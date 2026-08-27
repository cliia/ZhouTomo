#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZhouTomo desktop client entry point."""

import asyncio
import logging
import sys

import qasync
from PyQt5.QtWidgets import QApplication

from zhoutomo_client.config.colors import colors
from zhoutomo_client.ui.main_window import MainWindow
from zhoutomo_client.ui.splash_screen import SplashScreen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("main.log", encoding="utf-8"),
    ],
    force=True,
)
logger = logging.getLogger(__name__)


def main():
    """Run the ZhouTomo Qt desktop application."""
    app = QApplication(sys.argv)

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

    splash = SplashScreen()
    main_window = None

    def on_initialization_complete():
        nonlocal main_window
        main_window = MainWindow()
        splash.finish_splash(main_window)
        main_window.show()

    splash.initializationComplete.connect(on_initialization_complete)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        return loop.run_forever()


if __name__ == "__main__":
    sys.exit(main())
