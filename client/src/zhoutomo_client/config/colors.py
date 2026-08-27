#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
颜色配置文件 - 定义应用程序的全局颜色主题
"""

class Colors:
    """全局颜色配置类"""
    
    # 主题底色
    DARK_BACKGROUND = "#273945"      # 深底色
    LIGHT_BACKGROUND = "#344550"     # 浅底色
    LIGHTER_BACKGROUND = "#4d6b7e"     # 更浅底色
    
    # 常用UI颜色
    WHITE = "#ffffff"
    BLACK = "#000000"
    
    # 边框和分隔线
    BORDER_COLOR = "#273945"
    SEPARATOR_COLOR = "#1f2d36"
    
    # 按钮和交互元素
    BUTTON_BACKGROUND = "#273945"    # 按钮背景色
    BUTTON_HOVER = "#394e5c"         # 按钮悬停背景色
    BUTTON_PRESSED = "#3daee9"       # 按钮按下背景色
    BUTTON_BORDER_HOVER = "#3daee9"  # 按钮悬停边框色
    
    # 文字颜色
    TEXT_NORMAL = "#FFFFFF"          # 普通文字颜色
    TEXT_BACKGROUND = "#21323d"      # 文字背景色
    TEXT_HOVER = "#0066cc"           # 悬停文字颜色
    TEXT_SECONDARY = "#666666"       # 次要文字颜色
    TEXT_ON_DARK = "#ffffff"         # 深色背景上的文字
    TEXT_ON_LIGHT = "#333333"        # 浅色背景上的文字
    
    # 状态颜色
    SUCCESS = "#28a745"              # 成功状态
    WARNING = "#ffc107"              # 警告状态
    ERROR = "#dc3545"                # 错误状态
    INFO = "#17a2b8"                 # 信息状态
    
    # 工具栏和面板
    TOOLBAR_BACKGROUND = "#273945"   # 工具栏背景色
    TOOLBAR_TEXT_COLORORDER = ["#0c505b", "#4a3e58", "#628181", "#353b5e"]
    PANEL_BACKGROUND = "#f8f8f8"     # 面板背景色
    PANEL_HEADER = "#e0e0e0"         # 面板标题背景色


class Theme:
    """主题配置类"""
    
    @staticmethod
    def get_dark_theme():
        """获取深色主题配置"""
        return {
            'background': Colors.DARK_BACKGROUND,
            'surface': Colors.LIGHT_BACKGROUND,
            'text': Colors.TEXT_ON_DARK,
            'border': Colors.BORDER_COLOR,
        }
    
    @staticmethod
    def get_light_theme():
        """获取浅色主题配置"""
        return {
            'background': Colors.WHITE,
            'surface': Colors.LIGHT_BACKGROUND,
            'text': Colors.TEXT_ON_LIGHT,
            'border': Colors.BORDER_COLOR,
        }
    
    @staticmethod
    def get_custom_theme():
        """获取自定义主题配置"""
        return {
            'background': Colors.LIGHT_BACKGROUND,
            'surface': Colors.DARK_BACKGROUND,
            'text': Colors.TEXT_ON_DARK,
            'border': Colors.BORDER_COLOR,
        }


# 全局颜色实例
colors = Colors()
theme = Theme()
