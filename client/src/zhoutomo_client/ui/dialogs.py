#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话框和弹出框模块 - 包含应用程序中使用的各种对话框和弹出框
"""

import sys
import os
from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QRadioButton, QLineEdit, QButtonGroup, 
                            QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem, QSizePolicy, QApplication)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QCursor
from zhoutomo_protocol import params_to_dict

# 添加项目根目录到路径以支持绝对导入
try:
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from zhoutomo_client.config.colors import colors
    from zhoutomo_client.ui.widgets import HorizontalSpinBox, HorizontalDoubleSpinBox
except ImportError:
    # 如果无法导入，创建一个简单的替代版本
    class SimpleColors:
        WHITE = "#ffffff"
        LIGHT_BACKGROUND = "#344550"
        BORDER_COLOR = "#cccccc"
        TEXT_NORMAL = "#FFFFFF"
        TEXT_ON_DARK = "#ffffff"
        TEXT_SECONDARY = "#666666"
        LIGHTER_BACKGROUND = "#4d6b7e"
        BUTTON_BACKGROUND = "#273945"
        BUTTON_HOVER = "#394e5c"
        BUTTON_BORDER_HOVER = "#3daee9"
        BUTTON_PRESSED = "#3daee9"
    colors = SimpleColors()
    
    # 如果无法导入自定义控件，使用标准控件
    HorizontalSpinBox = QSpinBox
    HorizontalDoubleSpinBox = QDoubleSpinBox


class BasePopup(QFrame):
    """弹出框基类"""
    
    # 定义信号
    dataSelected = pyqtSignal(dict)  # 数据选中信号
    popupClosed = pyqtSignal()       # 弹出框关闭信号
    
    def __init__(self, parent=None, title="", width=450, height=200):
        super().__init__(parent)
        self.title = title
        self.width = width
        self.height = height
        self.init_base_ui()
        self.init_content()
        
    def init_base_ui(self):
        """初始化基础UI"""
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFixedSize(self.width, self.height)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        
        # 标题标签
        if self.title:
            self.title_label = QLabel(self.title)
            self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                font-family: Microsoft YaHei;
                color: {colors.TEXT_NORMAL};
                border: none;
            }}
        """)
            self.main_layout.addWidget(self.title_label)
        
        # 内容区域布局
        self.content_layout = QVBoxLayout()
        self.main_layout.addLayout(self.content_layout)
        
        # 添加弹性空间
        self.main_layout.addStretch()
        
        # 按钮区域
        self.create_buttons()
        
        # 设置基础样式
        self.set_base_style()
    
    def init_content(self):
        """初始化内容 - 子类需要重写此方法"""
        pass
    
    def create_buttons(self):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.setFixedSize(80, 28)
        self.ok_button.clicked.connect(self.accept_data)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(80, 28)
        self.cancel_button.clicked.connect(self.close_popup)
        
        # 按钮样式
        button_style = f"""
            QPushButton {{
                padding: 6px 6px;
                font-size: 12px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                background-color: {colors.BUTTON_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
            }}
            QPushButton:hover {{
                background-color: {colors.BUTTON_HOVER};
                border-color: {colors.BUTTON_BORDER_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {colors.BUTTON_PRESSED};
                color: white;
            }}
        """
        self.ok_button.setStyleSheet(button_style)
        self.cancel_button.setStyleSheet(button_style)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addSpacing(0)
        button_layout.addWidget(self.cancel_button)
        self.main_layout.addLayout(button_layout)
    
    def set_base_style(self):
        """设置基础样式"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.LIGHT_BACKGROUND};
                border: 2px solid {colors.BORDER_COLOR};
                border-radius: 0px;
            }}
            QLabel {{
                color: {colors.TEXT_ON_DARK};
                background-color: transparent;
                border: none;
                font-size: 12px;
                font-family: Microsoft YaHei;
            }}
            QRadioButton {{
                font-size: 12px;
                color: {colors.TEXT_ON_DARK};
                spacing: 8px;
                background-color: transparent;
                font-family: Microsoft YaHei;
            }}
            QRadioButton::indicator {{
                width: 12px;
                height: 12px;
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {colors.BORDER_COLOR};
                border-radius: 6px;
                background-color: white;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {colors.BORDER_COLOR};
                border-radius: 6px;
                background-color: {colors.BUTTON_PRESSED};
            }}
            QLineEdit {{
                padding: 4px 8px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                font-size: 12px;
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
            }}
            QLineEdit:focus {{
                border: 1px solid {colors.BUTTON_PRESSED};
            }}
            QLineEdit:disabled {{
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_SECONDARY};
            }}
            QComboBox {{
                padding: 2px 6px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                font-size: 12px;
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                min-height: 16px;
                max-height: 24px;
                font-family: Microsoft YaHei;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {colors.TEXT_NORMAL};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {colors.BORDER_COLOR};
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                selection-background-color: {colors.BUTTON_PRESSED};
                font-family: Microsoft YaHei;
            }}
            QPushButton {{
                padding: 6px 6px;
                font-size: 12px;
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                background-color: {colors.BUTTON_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
            }}
            QPushButton:hover {{
                background-color: {colors.BUTTON_HOVER};
                border-color: {colors.BUTTON_BORDER_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {colors.BUTTON_PRESSED};
                color: white;
            }}
            QListWidget{{
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                font-family: Microsoft YaHei;
                font-size: 12px;
            }}
        """)
    
    def get_data(self):
        """获取数据 - 子类需要重写此方法"""
        return {}
    
    def accept_data(self):
        """确定数据"""
        data = self.get_data()
        if data is not None:
            # 如果子类重写了accept_data，调用子类的方法
            if hasattr(self, 'accept_data_async') and callable(getattr(self, 'accept_data_async')):
                # 使用QTimer来异步调用
                QTimer.singleShot(0, lambda: self._run_async_accept_data())
            else:
                # 直接发送数据
                self.dataSelected.emit(data)
                self.close_popup()
    
    def _run_async_accept_data(self):
        """运行异步的accept_data方法"""
        try:
            import asyncio
            import qasync
            
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                asyncio.create_task(self.accept_data_async())
            else:
                # 如果事件循环没有运行，直接运行
                loop.run_until_complete(self.accept_data_async())
        except Exception as e:
            print(f"运行异步accept_data时发生错误: {e}")
            # 回退到同步方式
            data = self.get_data()
            if data is not None:
                self.dataSelected.emit(data)
                self.close_popup()
    
    def close_popup(self):
        """关闭弹出框（不销毁内部数据）"""
        self.hide()
        self.popupClosed.emit()
    
    def show_at_position(self, pos):
        """在指定位置显示弹出框"""
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()


class ConnectEMPopup(BasePopup):
    """连接电镜弹出框（仅远程URL）"""
    
    # 定义信号 (保持向后兼容)
    connectionSelected = pyqtSignal(dict)  # 连接信息选中信号
    
    def __init__(self, parent=None):
        super().__init__(parent, "连接电镜 (远程URL)", 450, 120)
        # 转发基础信号
        self.dataSelected.connect(self.connectionSelected.emit)
        
    def init_content(self):
        """初始化内容"""
        self.LINE_HEIGHT = 24
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        grid_layout.setColumnStretch(0, 0)
        grid_layout.setColumnStretch(1, 1)
        
        # URL 标签
        url_label = QLabel("服务器URL：")
        url_label.setFixedWidth(90)
        grid_layout.addWidget(url_label, 0, 0, Qt.AlignRight)
        
        # URL 输入框（默认本机虚拟电镜）
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如：http://169.254.225.233:9000")
        self.url_input.setText("http://169.254.225.233:9000")
        self.url_input.setMinimumWidth(240)
        self.url_input.setFixedHeight(self.LINE_HEIGHT)
        grid_layout.addWidget(self.url_input, 0, 1, Qt.AlignVCenter)
        
        self.content_layout.addLayout(grid_layout)
    
    def get_data(self):
        """获取连接信息（统一为 remote）"""
        url = self.url_input.text().strip()
        if not url:
            return None
        return {"type": "remote", "url": url}
    

class ImageCapturePopup(BasePopup):
    """图像采集弹出框"""
    
    # 定义信号
    captureSettingsSelected = pyqtSignal(dict)  # 采集设置选中信号
    
    def __init__(self, parent=None, agent_manager=None):
        super().__init__(parent, "图像采集参数设置", 300, 320)
        self.agent_manager = agent_manager
        self.current_state = None
        # 连接信号
        self.dataSelected.connect(self.captureSettingsSelected.emit)
        
        # 初始化完成后从服务器加载当前acquisition状态（异步），失败则回退到默认
        QTimer.singleShot(100, self._run_async_load_current_state)

    def init_content(self):
        """初始化内容"""
        self.LINE_HEIGHT = 32
        # 创建网格布局
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.setColumnStretch(0, 0)  # 标签列固定宽度
        grid_layout.setColumnStretch(1, 1)  # 控件列可拉伸

        combo_style_sheet = f"""
            QComboBox {{
                border: 1px solid {colors.BORDER_COLOR};
                border-radius: 0px;
                padding: 4px 8px;
                background: {colors.LIGHTER_BACKGROUND};
                font-size: 12px;
                font-family: Microsoft YaHei;
                color: {colors.TEXT_NORMAL};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {colors.TEXT_NORMAL};
            }}
        """
        row = 0
        
        # 尺寸设置
        size_label = QLabel("尺  寸：")
        size_label.setFixedWidth(60)
        size_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei; ")
        grid_layout.addWidget(size_label, row, 0, Qt.AlignRight)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["0", "1", "2"])  # 与服务端 Enum 对齐
        self.size_combo.setFixedHeight(self.LINE_HEIGHT)
        self.size_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.size_combo, row, 1)
        row += 1
        
        # 驻留时间设置
        dwell_label = QLabel("驻留时：")
        dwell_label.setFixedWidth(60)
        dwell_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei;")
        grid_layout.addWidget(dwell_label, row, 0, Qt.AlignRight)
        
        self.dwell_combo = QComboBox()
        self.dwell_combo.setEditable(True)
        self.dwell_combo.addItems(["0.5", "1.0", "2.0", "5.0", "10.0", "20.0", "50.0", "100.0"])
        self.dwell_combo.setFixedHeight(self.LINE_HEIGHT)
        self.dwell_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.dwell_combo, row, 1)
        row += 1
        
        # 亮度设置
        brightness_label = QLabel("亮  度：")
        brightness_label.setFixedWidth(60)
        brightness_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei;")
        grid_layout.addWidget(brightness_label, row, 0, Qt.AlignRight)
        
        self.brightness_combo = QComboBox()
        self.brightness_combo.setEditable(True)
        self.brightness_combo.addItems(["10", "25", "45", "65", "85", "100"])
        self.brightness_combo.setFixedHeight(self.LINE_HEIGHT)
        self.brightness_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.brightness_combo, row, 1)
        row += 1
        
        # 对比度设置
        contrast_label = QLabel("对比度：")
        contrast_label.setFixedWidth(60)
        contrast_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei;")
        grid_layout.addWidget(contrast_label, row, 0, Qt.AlignRight)
        
        self.contrast_combo = QComboBox()
        self.contrast_combo.setEditable(True)
        self.contrast_combo.addItems(["10", "25", "45", "65", "85", "100"])
        self.contrast_combo.setFixedHeight(self.LINE_HEIGHT)
        self.contrast_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.contrast_combo, row, 1)
        row += 1
        
        # 合并度设置
        binning_label = QLabel("合并度：")
        binning_label.setFixedWidth(60)
        binning_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei;")
        grid_layout.addWidget(binning_label, row, 0, Qt.AlignRight)
        
        self.binning_combo = QComboBox()
        self.binning_combo.addItems(["1", "2", "4", "8"])  # 与服务端 Enum 对齐
        self.binning_combo.setFixedHeight(self.LINE_HEIGHT)
        self.binning_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.binning_combo, row, 1)
        row += 1
        
        # 帧数设置
        frames_label = QLabel("帧  数：")
        frames_label.setFixedWidth(60)
        frames_label.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-size: 12px; font-family: Microsoft YaHei;")
        grid_layout.addWidget(frames_label, row, 0, Qt.AlignRight)
        
        self.frames_combo = QComboBox()
        self.frames_combo.setEditable(True)
        self.frames_combo.addItems(["1", "2", "3", "5", "10", "20", "50", "100"])
        self.frames_combo.setFixedHeight(self.LINE_HEIGHT)
        self.frames_combo.setStyleSheet(combo_style_sheet)
        grid_layout.addWidget(self.frames_combo, row, 1)
        self.content_layout.addLayout(grid_layout)
    
    async def load_current_state(self):
        """异步加载当前采集状态（从服务器）"""
        if not self.agent_manager or not self.agent_manager.is_connected:
            return
        try:
            # 通过AgentManager获取当前状态（dict）
            state_dict = await self.agent_manager.get_component_state("acquisition")
            if not state_dict or not isinstance(state_dict, dict):
                raise ValueError("无效的acquisition状态数据")
            # 将字典转为 AcquisitionState，便于后续属性访问
            from zhoutomo_protocol import AcquisitionState
            self.current_state = AcquisitionState(
                acq_image_size=int(state_dict.get("acq_image_size", 1)),
                dwell_time=float(state_dict.get("dwell_time", 2.0)),
                brightness=float(state_dict.get("brightness", 45.0)),
                contrast=float(state_dict.get("contrast", 45.0)),
                binnings=int(state_dict.get("binnings", 4)),
                frames=int(state_dict.get("frames", 1))
            )
            # 更新UI
            self.update_ui_from_state()
        except Exception as e:
            print(f"加载采集状态失败: {e}")
    
    def load_current_state_sync(self):
        """同步加载当前采集状态"""
        try:
            # 获取acquisition组件的状态
            from zhoutomo_protocol import AcquisitionState
            
            # 这里应该通过API获取当前状态，暂时使用默认值
            # 实际实现中应该调用 agent_manager.get_component_state("acquisition")
            self.current_state = AcquisitionState(
                acq_image_size=1,
                dwell_time=2.0,
                brightness=45.0,
                contrast=45.0,
                binnings=4,
                frames=1
            )
            
            # 更新UI显示
            self.update_ui_from_state()
            
        except Exception as e:
            print(f"加载采集状态失败: {e}")

    def _run_async_load_current_state(self):
        """在Qt环境中调度异步的load_current_state执行，失败回退到默认"""
        try:
            import asyncio
            import qasync
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.load_current_state())
            else:
                loop.run_until_complete(self.load_current_state())
        except Exception as e:
            print(f"异步加载采集状态失败，使用默认: {e}")
            self.load_current_state_sync()

    def reload_from_acquisition_state(self):
        """对外方法：重新从服务器拉取acquisition状态并更新UI"""
        QTimer.singleShot(0, self._run_async_load_current_state)
    
    def update_ui_from_state(self):
        """根据状态更新UI"""
        if not self.current_state:
            return
        
        try:
            # 更新尺寸
            size_index = self.get_combo_index_by_value(self.size_combo, self.current_state.acq_image_size)
            if size_index >= 0:
                self.size_combo.setCurrentIndex(size_index)
            
            # 更新驻留时间
            self.dwell_combo.setCurrentText(f"{self.current_state.dwell_time}")
            
            # 更新亮度
            self.brightness_combo.setCurrentText(f"{self.current_state.brightness}")
            
            # 更新对比度
            self.contrast_combo.setCurrentText(f"{self.current_state.contrast}")
            
            # 更新合并度
            binning_index = self.get_combo_index_by_value(self.binning_combo, self.current_state.binnings)
            if binning_index >= 0:
                self.binning_combo.setCurrentIndex(binning_index)
            
            # 更新帧数
            self.frames_combo.setCurrentText(f"{self.current_state.frames}")
            
        except Exception as e:
            print(f"更新UI失败: {e}")
    
    def get_combo_index_by_value(self, combo, value):
        """根据值精确匹配下拉项文本（文本即数字字符串）。"""
        target = str(value).strip()
        for i in range(combo.count()):
            if combo.itemText(i).strip() == target:
                return i
        return -1
    
    def get_data(self):
        """获取采集参数设置"""
        try:
            # 解析尺寸值
            size_text = self.size_combo.currentText()
            acq_image_size = int(size_text.split()[0])
            
            # 解析驻留时间
            dwell_time = float(self.dwell_combo.currentText())
            
            # 解析亮度
            brightness = float(self.brightness_combo.currentText())
            
            # 解析对比度
            contrast = float(self.contrast_combo.currentText())
            
            # 解析合并度
            binning_text = self.binning_combo.currentText()
            binnings = int(binning_text.split()[0])
            
            # 解析帧数
            frames = int(self.frames_combo.currentText())
            
            # 创建参数对象
            from zhoutomo_protocol import AcquisitionParams
            params = AcquisitionParams(
                acq_image_size=acq_image_size,
                dwell_time=dwell_time,
                brightness=brightness,
                contrast=contrast,
                binnings=binnings,
                frames=frames
            )
            
            return {
                "params": params,
                "raw_values": {
                    "acq_image_size": acq_image_size,
                    "dwell_time": dwell_time,
                    "brightness": brightness,
                    "contrast": contrast,
                    "binnings": binnings,
                    "frames": frames
                }
            }
            
        except Exception as e:
            print(f"获取采集参数失败: {e}")
            return None
    
    async def accept_data_async(self):
        """确认设置并更新服务器参数"""
        data = self.get_data()
        if not data:
            return
        
        try:
            if self.agent_manager and self.agent_manager.is_connected:
                # 通过agent更新acquisition组件的参数
                success = await self.agent_manager.set_component_params("acquisition", data["params"])

                if success:
                    print("采集参数更新成功")
                    self.dataSelected.emit(data)
                    self.close_popup()
                else:
                    print("采集参数更新失败")
                    # 这里可以显示错误提示
            else:
                print("电镜未连接，无法更新参数")
                # 这里可以显示错误提示
                
        except Exception as e:
            print(f"更新采集参数时发生错误: {e}")
            # 这里可以显示错误提示


class AutofocusSettingsPopup(BasePopup):
    """自动聚焦参数设置弹出框（OFRS步长、FRS步长、最大迭代次数）"""

    def __init__(self, parent=None):
        super().__init__(parent, "自动聚焦参数设置", 360, 240)

    def init_content(self):
        self.LINE_HEIGHT = 28
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        # 算法选择
        algo_label = QLabel("算法：")
        algo_label.setFixedWidth(120)
        algo_label.setAlignment(Qt.AlignRight)
        grid.addWidget(algo_label, 0, 0, Qt.AlignRight)
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["基础（两阶段步进）", "高级（黄金分割）"])  # 返回时映射为 basic/advanced
        self.algo_combo.setCurrentIndex(1)  # 默认高级
        self.algo_combo.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.algo_combo, 0, 1)

        # OFRS 步长 (nm)
        ofrs_label = QLabel("OFRS步长 (nm)：")
        ofrs_label.setFixedWidth(120)
        ofrs_label.setAlignment(Qt.AlignRight)
        grid.addWidget(ofrs_label, 1, 0, Qt.AlignRight)
        self.ofrs_step = QLineEdit()
        self.ofrs_step.setText("10.0")
        self.ofrs_step.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.ofrs_step, 1, 1)

        # FRS 步长 (nm)
        frs_label = QLabel("FRS步长 (nm)：")
        frs_label.setFixedWidth(120)
        frs_label.setAlignment(Qt.AlignRight)
        grid.addWidget(frs_label, 2, 0, Qt.AlignRight)
        self.frs_step = QLineEdit()
        self.frs_step.setText("75.0")
        self.frs_step.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.frs_step, 2, 1)

        # 最大迭代次数
        iter_label = QLabel("最大迭代次数：")
        iter_label.setFixedWidth(120)
        iter_label.setAlignment(Qt.AlignRight)
        grid.addWidget(iter_label, 3, 0, Qt.AlignRight)
        self.max_iters = QLineEdit()
        self.max_iters.setText("10")
        self.max_iters.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.max_iters, 3, 1)

        # 阶段4（超精细微扫）开关
        row_ultra = 4
        lbl_ultra = QLabel("阶段4：超精细微扫（±10nm）")
        lbl_ultra.setFixedWidth(120)
        lbl_ultra.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl_ultra, row_ultra, 0, Qt.AlignRight)
        from PyQt5.QtWidgets import QCheckBox
        self.ultra_enable = QCheckBox("启用")
        self.ultra_enable.setChecked(True)
        self.ultra_enable.setStyleSheet(f"color: {colors.TEXT_NORMAL}; font-family: Microsoft YaHei;")
        grid.addWidget(self.ultra_enable, row_ultra, 1)

        self.content_layout.addLayout(grid)

    def set_from_dict(self, d: dict):
        try:
            if not isinstance(d, dict):
                return
            if 'ofrs_step_nm' in d:
                self.ofrs_step.setText(str(float(d.get('ofrs_step_nm'))))
            if 'frs_step_nm' in d:
                self.frs_step.setText(str(float(d.get('frs_step_nm'))))
            if 'max_iterations' in d:
                self.max_iters.setText(str(int(d.get('max_iterations'))))
            if 'enable_ultra_fine' in d:
                val = d.get('enable_ultra_fine')
                try:
                    if isinstance(val, str):
                        val = val.strip().lower() in ("1", "true", "yes", "y", "on")
                    self.ultra_enable.setChecked(bool(val))
                except Exception:
                    pass
        except Exception:
            pass

    def get_data(self):
        try:
            # 算法映射
            algo_text = self.algo_combo.currentText().strip()
            algo_val = 'advanced' if '高级' in algo_text else 'basic'
            return {
                "algorithm": algo_val,
                "ofrs_step_nm": float(self.ofrs_step.text()),
                "frs_step_nm": float(self.frs_step.text()),
                "max_iterations": int(self.max_iters.text()),
                "enable_ultra_fine": bool(self.ultra_enable.isChecked()),
            }
        except Exception as e:
            print(f"读取自动聚焦参数失败: {e}")
            return None


class AutoTiltSettingsPopup(BasePopup):
    """自动倾转参数设置弹出框
    - 允许设定一个或多个 alpha 倾角程序：按区间和步长生成序列
    - 支持在下方“新增/删除下一个转角程序”
    - 底部展示当前所有转角程序（合并预览）
    """

    def __init__(self, parent=None):
        # 初始高度较小，后续根据内容自适应
        super().__init__(parent, "自动倾转参数设置", 420, 320)
        self.programs = []  # 每个元素为 {'alpha_min': float, 'alpha_max': float, 'step': float, 'sequence': List[float]}
        # 允许根据内容高度自适应
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        # 在关闭/确定后再次打开时，保留先前的程序
        self._persisted_programs = []

    def init_content(self):
        self.LINE_HEIGHT = 28
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        # alpha_min
        lbl_min = QLabel("从 alpha 最小 (deg)：")
        lbl_min.setFixedWidth(110)
        lbl_min.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl_min, 0, 0, Qt.AlignRight)
        self.alpha_min = QLineEdit("-10.0")
        self.alpha_min.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.alpha_min, 0, 1)

        # alpha_max
        lbl_max = QLabel("至 alpha 最大 (deg)：")
        lbl_max.setFixedWidth(110)
        lbl_max.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl_max, 1, 0, Qt.AlignRight)
        self.alpha_max = QLineEdit("10.0")
        self.alpha_max.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.alpha_max, 1, 1)

        # step
        lbl_step = QLabel("步长 (deg)：")
        lbl_step.setFixedWidth(110)
        lbl_step.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl_step, 2, 0, Qt.AlignRight)
        self.alpha_step = QLineEdit("1.0")
        self.alpha_step.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.alpha_step, 2, 1)

        # HR 放大倍率
        lbl_hrmag = QLabel("HR放大倍率：")
        lbl_hrmag.setFixedWidth(110)
        lbl_hrmag.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl_hrmag, 3, 0, Qt.AlignRight)
        self.hr_magnification = QLineEdit("")
        self.hr_magnification.setPlaceholderText("例如：11000000")
        self.hr_magnification.setFixedHeight(self.LINE_HEIGHT)
        grid.addWidget(self.hr_magnification, 3, 1)

        # 操作按钮：新增/删除下一个转角程序
        btns = QHBoxLayout()
        self.btn_add = QPushButton("新增程序")
        self.btn_del = QPushButton("删除选中")
        for b in (self.btn_add, self.btn_del):
            b.setFixedHeight(self.LINE_HEIGHT)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)

        # 列表：展示各个程序
        self.list_programs = QListWidget()
        self.list_programs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # 底部：合并预览（当前设定的转角程序）
        self.preview_label = QLabel("当前转角序列：[]")
        self.preview_label.setWordWrap(True)

        # 绑定事件
        self.btn_add.clicked.connect(self._on_add_program)
        self.btn_del.clicked.connect(self._on_delete_program)
        self.list_programs.itemSelectionChanged.connect(self._refresh_preview)

        # 组装
        self.content_layout.addLayout(grid)
        self.content_layout.addLayout(btns)
        self.content_layout.addWidget(self.list_programs)
        self.content_layout.addWidget(self.preview_label)
        # 初始调整高度
        QTimer.singleShot(0, self._resize_to_contents)
        # 若存在持久化数据，恢复（弹窗显示后再恢复，避免控件尚未布局完成）
        QTimer.singleShot(0, self._restore_persisted)

    def _restore_persisted(self):
        try:
            if getattr(self, '_persisted_programs', None):
                self.programs = []
                self.list_programs.clear()
                for info in self._persisted_programs:
                    seq = self._build_sequence(info['alpha_min'], info['alpha_max'], info['step'])
                    add = {"alpha_min": info['alpha_min'], "alpha_max": info['alpha_max'], "step": info['step'], "sequence": seq}
                    self.programs.append(add)
                    item = QListWidgetItem(f"[{info['alpha_min']} → {info['alpha_max']}] Δ={info['step']}° 共{len(seq)}步")
                    item.setData(Qt.UserRole, add)
                    self.list_programs.addItem(item)
                self._refresh_preview()
                self._resize_to_contents()
        except Exception:
            pass

    def _build_sequence(self, amin: float, amax: float, step: float):
        # 允许 amin > amax 的倒序；step 必须为正值
        if step <= 0:
            raise ValueError("步长必须为正")
        if amin <= amax:
            num = int((amax - amin) / step + 0.5)  # 近似四舍五入到整数步数
            seq = [round(amin + i * step, 6) for i in range(num + 1)]
            # 修正尾点
            if seq and seq[-1] != amax:
                seq[-1] = amax
        else:
            num = int((amin - amax) / step + 0.5)
            seq = [round(amin - i * step, 6) for i in range(num + 1)]
            if seq and seq[-1] != amax:
                seq[-1] = amax
        return seq

    def _on_add_program(self):
        try:
            amin = float(self.alpha_min.text())
            amax = float(self.alpha_max.text())
            step = float(self.alpha_step.text())
            seq = self._build_sequence(amin, amax, step)
            info = {"alpha_min": amin, "alpha_max": amax, "step": step, "sequence": seq}
            self.programs.append(info)
            item = QListWidgetItem(f"[{amin} → {amax}] Δ={step}° 共{len(seq)}步")
            item.setData(Qt.UserRole, info)
            self.list_programs.addItem(item)
            self._refresh_preview()
            self._resize_to_contents()
        except Exception as e:
            print(f"新增程序失败: {e}")

    def _on_delete_program(self):
        try:
            row = self.list_programs.currentRow()
            if row >= 0:
                self.list_programs.takeItem(row)
                if 0 <= row < len(self.programs):
                    self.programs.pop(row)
            self._refresh_preview()
            self._resize_to_contents()
        except Exception as e:
            print(f"删除程序失败: {e}")

    def _refresh_preview(self):
        # 展示合并后的总序列（顺序按程序加入顺序拼接）
        merged = []
        for i in range(self.list_programs.count()):
            item = self.list_programs.item(i)
            info = item.data(Qt.UserRole)
            merged.extend(info.get("sequence", []))
        # 控制显示长度，避免过长
        if len(merged) > 80:
            head = ", ".join(str(x) for x in merged[:40])
            tail = ", ".join(str(x) for x in merged[-40:])
            text = f"当前转角序列（{len(merged)}）: {head}, ... , {tail}"
        else:
            text = f"当前转角序列（{len(merged)}）: {merged}"
        self.preview_label.setText(text)
        # 在预览更新后也尝试自适应
        QTimer.singleShot(0, self._resize_to_contents)

    def _resize_to_contents(self):
        try:
            # 根据内容计算合适高度，避免与输入控件重叠
            self.list_programs.setMinimumHeight(min(220, 40 + self.list_programs.count() * 22))
            hint = self.sizeHint()
            w = max(self.width, hint.width()) if hasattr(self, 'width') else hint.width()
            h = hint.height()
            # 限制最大高度，避免超出屏幕
            screen = QApplication.primaryScreen()
            if screen:
                max_h = int(screen.availableGeometry().height() * 0.8)
                h = min(h, max_h)
            self.setFixedSize(max(360, w), max(280, h))
        except Exception:
            pass

    def get_data(self):
        try:
            # 返回所有程序与合并后的序列
            merged = []
            programs_out = []
            for i in range(self.list_programs.count()):
                item = self.list_programs.item(i)
                info = item.data(Qt.UserRole)
                programs_out.append({k: info[k] for k in ("alpha_min", "alpha_max", "step")})
                merged.extend(info.get("sequence", []))
            result = {
                "programs": programs_out,
                "sequence": merged,
                # 若未填写则置为 None，由主流程回退到当前倍率或目标快照倍率
                "hr_magnification": (float(self.hr_magnification.text()) if self.hr_magnification.text().strip() else None),
            }
            # 不关闭弹窗时也可读取
            # 持久化已定义的程序，确保下次打开依然显示
            self._persisted_programs = [dict(p) for p in programs_out]
            return result
        except Exception as e:
            print(f"读取自动倾转参数失败: {e}")
            return None


class ImagePropertiesPopup(BasePopup):
    """图像属性弹出框：使用表格展示键值信息（只读）。"""

    def __init__(self, parent=None, title="图像属性", width=360, height=220):
        super().__init__(parent, title, width, height)
        self._props = {}

    def init_content(self):
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["属性", "值"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        # 显式样式，避免深色主题下文字不可见
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {colors.LIGHTER_BACKGROUND};
                color: {colors.TEXT_NORMAL};
                gridline-color: {colors.BORDER_COLOR};
                border: 1px solid {colors.BORDER_COLOR};
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
        self.content_layout.addWidget(self.table)

    def set_properties(self, props: dict):
        try:
            from PyQt5.QtWidgets import QTableWidgetItem
            if not isinstance(props, dict):
                return
            self._props = dict(props)
            items = list(self._props.items())
            # 预设行数并填充，避免某些平台上 insertRow 表现异常
            self.table.clearContents()
            self.table.setRowCount(len(items))
            # 设回表头
            self.table.setHorizontalHeaderLabels(["属性", "值"])
            for row, (key, value) in enumerate(items):
                ki = QTableWidgetItem(str(key))
                ki.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                vi = QTableWidgetItem(str(value))
                vi.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row, 0, ki)
                self.table.setItem(row, 1, vi)
            try:
                self.table.resizeColumnsToContents()
                self.table.resizeRowsToContents()
            except Exception:
                pass
        except Exception:
            pass

    def get_data(self):
        # 只读展示，无需返回数据
        return None