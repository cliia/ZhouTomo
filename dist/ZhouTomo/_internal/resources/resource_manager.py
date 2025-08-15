#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源管理器 - 管理应用程序的图标和其他资源文件
"""

import os
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QSize, Qt


class ResourceManager:
    """资源管理器类"""
    
    def __init__(self):
        # 获取资源目录路径
        self.resource_dir = os.path.dirname(os.path.abspath(__file__))
        self.icons_dir = os.path.join(self.resource_dir, 'icons')
        
        # 确保图标目录存在
        if not os.path.exists(self.icons_dir):
            os.makedirs(self.icons_dir)
    
    def get_icon(self, icon_name, size=None, force_size=False):
        """
        获取图标
        
        Args:
            icon_name (str): 图标文件名（不含扩展名）
            size (QSize, optional): 图标大小
            force_size (bool): 是否强制缩放到指定大小（忽略长宽比）
            
        Returns:
            QIcon: 图标对象
        """
        # 支持的图标格式
        formats = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.ico', '.svg']
        
        icon_path = None
        for fmt in formats:
            potential_path = os.path.join(self.icons_dir, f"{icon_name}{fmt}")
            if os.path.exists(potential_path):
                icon_path = potential_path
                break
        
        if icon_path:
            if size:
                # 加载图片并缩放到指定大小
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # 选择缩放模式
                    aspect_ratio = Qt.IgnoreAspectRatio if force_size else Qt.KeepAspectRatio
                    
                    # 缩放图片到指定大小
                    scaled_pixmap = pixmap.scaled(
                        size.width(), 
                        size.height(), 
                        aspect_ratio,  # 长宽比模式
                        Qt.SmoothTransformation  # 平滑缩放
                    )
                    return QIcon(scaled_pixmap)
            
            # 如果没有指定大小，直接返回原图标
            return QIcon(icon_path)
        else:
            # 如果找不到图标文件，返回默认图标或空图标
            return QIcon()
    
    def get_icon_path(self, icon_name):
        """
        获取图标文件的完整路径
        
        Args:
            icon_name (str): 图标文件名（不含扩展名）
            
        Returns:
            str: 图标文件路径，如果不存在返回None
        """
        formats = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.ico', '.svg']
        
        for fmt in formats:
            potential_path = os.path.join(self.icons_dir, f"{icon_name}{fmt}")
            if os.path.exists(potential_path):
                return potential_path
        
        return None
    
    def list_available_icons(self):
        """
        列出所有可用的图标文件
        
        Returns:
            list: 图标文件名列表（不含扩展名）
        """
        if not os.path.exists(self.icons_dir):
            return []
        
        icons = []
        for file in os.listdir(self.icons_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.ico', '.svg')):
                icon_name = os.path.splitext(file)[0]
                if icon_name not in icons:
                    icons.append(icon_name)
        
        return sorted(icons)


# 全局资源管理器实例
resource_manager = ResourceManager()
