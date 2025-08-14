import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtGui import QIcon, QPixmap, QCursor

try:
    # 添加项目根目录到路径以支持绝对导入
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from resources.resource_manager import resource_manager
    from config.colors import colors, theme
except ImportError:
    # 如果无法导入资源管理器，创建一个简单的替代版本
    class SimpleResourceManager:
        def get_icon(self, icon_name, size=None):
            return QIcon()
    
    class SimpleColors:
        DARK_BACKGROUND = "#1f2d36"
        LIGHT_BACKGROUND = "#344550"
        TOOLBAR_BACKGROUND = "#f0f0f0"
        BORDER_COLOR = "#cccccc"
        TEXT_NORMAL = "#333333"
        BUTTON_HOVER = "#e8f4fd"
        BUTTON_PRESSED = "#3daee9"
        TEXT_HOVER = "#0066cc"
    
    resource_manager = SimpleResourceManager()
    colors = SimpleColors()
    theme = None

# 导入自定义控件和对话框
try:
    from view.widgets import ClickableLabel
    from view.dialogs import ConnectEMPopup, ImageCapturePopup, AutofocusSettingsPopup, AutoTiltSettingsPopup
except ImportError:
    # 如果绝对导入失败，尝试相对导入
    try:
        from .widgets import ClickableLabel
        from .dialogs import ConnectEMPopup, ImageCapturePopup, AutofocusSettingsPopup, AutoTiltSettingsPopup
    except ImportError:
        # 如果都失败了，添加路径并导入
        import sys
        import os
        current_dir = os.path.dirname(__file__)
        sys.path.append(current_dir)
        from widgets import ClickableLabel
        from dialogs import ConnectEMPopup, ImageCapturePopup, AutofocusSettingsPopup, AutoTiltSettingsPopup


class MainToolbar(QWidget):
    """主工具栏类"""
    
    # 定义信号
    connectionSelected = pyqtSignal(dict)  # 连接选择信号
    statusUpdate = pyqtSignal(str)  # 状态更新信号
    imageCaptureRequested = pyqtSignal()  # 图像采集请求信号
    selectTargetRequested = pyqtSignal()  # 选择目标请求（兼容旧逻辑）
    selectTargetToggled = pyqtSignal(bool)  # 选择目标开关
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.connect_popup = None
        self.image_capture_popup = None
        self.connect_em_label = None
        self.image_capture_label = None
        self.connect_em_button = None
        self._icon_buttons = []
        self._text_labels = []
        self.select_target_button = None
        self.init_toolbar()
    
    def init_toolbar(self):
        """初始化工具栏"""
        # 长度常数
        self.ICON_WIDTH = 90
        self.ICON_HEIGHT = 64
        self.TEXT_HEIGHT = 24
        
        # 设置工具栏属性
        self.setObjectName("toolbar_container")
        self.setFixedHeight(self.ICON_HEIGHT+self.TEXT_HEIGHT)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.TOOLBAR_BACKGROUND};
                border-bottom: 0px solid {colors.BORDER_COLOR};
            }}
        """)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建图标按钮行
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(0)
        
        # 创建文字标签行
        text_layout = QHBoxLayout()
        text_layout.setSpacing(0)

        # 创建顶部横向分隔符
        top_horizontal_separator = self.create_horizontal_separator()
        main_layout.addWidget(top_horizontal_separator)

        # 按钮数据：[图标名, 显示文本, 执行函数, 设置函数]
        button_data = [
            ('connect_em', '连接电镜', self.settings_connect_em, self.settings_connect_em),
            ('image_capture', '图像采集', self.execute_image_capture, self.settings_image_capture),
            ('select_target', '选择目标', self.execute_select_target, self.settings_select_target),
            ('auto_focus', '自动聚焦', self.execute_auto_focus, self.settings_auto_focus),
            ('auto_tilt', '自动倾转', self.execute_auto_tilt, self.settings_auto_tilt)
        ]
        
        # 创建按钮和标签
        for i, (icon_name, text, exec_func, settings_func) in enumerate(button_data):
            # 创建图标按钮
            icon_button = QPushButton()
            icon_button.setIcon(resource_manager.get_icon(icon_name, QSize(int(self.ICON_WIDTH/2), int(self.ICON_HEIGHT/2)), force_size=False))
            icon_button.setIconSize(QSize(int(self.ICON_WIDTH/2), int(self.ICON_HEIGHT/2)))
            icon_button.setFixedSize(self.ICON_WIDTH, self.ICON_HEIGHT)
            icon_button.setStyleSheet(f"""
                QPushButton {{
                    border: 0px solid transparent;
                    border-radius: 0px;
                    background-color: {colors.BUTTON_BACKGROUND};
                    padding: 0px;
                }}
                QPushButton:hover {{
                    border: 0px solid {colors.BUTTON_BORDER_HOVER};
                    background-color: {colors.BUTTON_HOVER};
                }}
                QPushButton:pressed {{
                    background-color: {colors.BUTTON_PRESSED};
                }}
                QPushButton::icon {{
                    width: {self.ICON_WIDTH-4}px;
                    height: {self.ICON_HEIGHT-4}px;
                }}
            """)
            icon_button.setStatusTip(f'执行{text}')
            icon_button.clicked.connect(exec_func)
            if text == "选择目标":
                icon_button.setCheckable(True)
                # 同步切换信号（使用lambda确保参数转发）
                icon_button.toggled.connect(lambda checked, s=self: s.selectTargetToggled.emit(checked))
            
            # 创建文字标签（添加向下箭头）
            text_label = ClickableLabel(f"{text} ⌄")
            text_label.setFixedSize(self.ICON_WIDTH, self.TEXT_HEIGHT)
            
            # 保存标签引用
            if text == "连接电镜":
                self.connect_em_label = text_label
                self.connect_em_button = icon_button
            elif text == "图像采集":
                self.image_capture_label = text_label
            elif text == "选择目标":
                self.select_target_button = icon_button
            text_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors.TEXT_ON_DARK};
                    background-color: {colors.TOOLBAR_TEXT_COLORORDER[i % 4]};
                    font-size: 12px;
                    font-weight: normal;
                    border: none;
                    border-radius: 0px;
                    padding: 0px;
                    margin: 0px;
                    text-align: center;
                }}
                QLabel:hover {{
                    color: {colors.TEXT_HOVER};
                    background-color: {colors.BUTTON_HOVER};
                    border: none;
                }}
            """)
            text_label.setStatusTip(f'{text}设置')
            text_label.clicked.connect(settings_func)
            
            # 添加到布局
            icon_layout.addWidget(icon_button)
            text_layout.addWidget(text_label)
            # 保存引用列表
            self._icon_buttons.append(icon_button)
            self._text_labels.append(text_label)
            
            # 添加分隔符
            icon_layout.addWidget(self.create_separator(height=self.ICON_HEIGHT))
            text_layout.addWidget(self.create_separator(height=self.TEXT_HEIGHT))
        
        # 添加弹性空间
        icon_layout.addStretch()
        text_layout.addStretch()
        
        # 添加到主布局
        main_layout.addLayout(icon_layout)
        
        # 添加横向分隔符
        bottom_horizontal_separator = self.create_horizontal_separator()
        main_layout.addWidget(bottom_horizontal_separator)
        
        main_layout.addLayout(text_layout)

        # 创建底部横向分隔符
        bottom_horizontal_separator = self.create_horizontal_separator()
        main_layout.addWidget(bottom_horizontal_separator)

    def set_pre_connection_mode(self, pre_connection: bool):
        """在未连接前，仅允许“连接电镜”按钮和其标签交互，其余禁用。"""
        try:
            if pre_connection:
                # 锁定：仅“连接电镜”按钮和标签可用
                for btn in self._icon_buttons:
                    btn.setEnabled(btn is self.connect_em_button)
                for lbl in self._text_labels:
                    lbl.setEnabled(lbl is self.connect_em_label)
            else:
                # 解锁：全部可用
                for btn in self._icon_buttons:
                    btn.setEnabled(True)
                for lbl in self._text_labels:
                    lbl.setEnabled(True)
        except Exception:
            # 兜底：如有异常不影响主流程
            pass

    def set_all_enabled(self, enabled: bool):
        """统一启用/禁用工具栏上的所有按钮和标签。"""
        for btn in self._icon_buttons:
            btn.setEnabled(enabled)
        for lbl in self._text_labels:
            lbl.setEnabled(enabled)
    
    def create_separator(self, height=70):
        """创建竖直分隔符"""
        separator = QFrame()
        # flat 的分隔符
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedSize(1, height)
        separator.setStyleSheet(f"QFrame {{ color: {colors.SEPARATOR_COLOR}; }}")
        return separator
    
    def create_horizontal_separator(self):
        """创建水平分隔符"""
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"QFrame {{ color: {colors.SEPARATOR_COLOR}; }}")
        return separator
    
    # 执行函数
    def execute_connect_em(self):
        """执行连接电镜"""
        self.statusUpdate.emit("正在连接电镜...")
        print("执行连接电镜操作")
    
    def execute_image_capture(self):
        """执行图像采集"""
        self.statusUpdate.emit("正在采集图像...")
        # 最后的接收对象是 self.agent_manager.start_acquisition()
        self.imageCaptureRequested.emit()
    
    def execute_select_target(self):
        """执行选择目标"""
        self.statusUpdate.emit("正在执行选择目标...")

    def execute_auto_focus(self):
        """执行自动聚焦（交由主窗口处理）"""
        try:
            self.parent_window.on_auto_focus_requested()
        except Exception:
            pass
    
    def execute_auto_tilt(self):
        """执行自动倾转"""
        self.statusUpdate.emit("正在执行自动倾转...")
        try:
            if hasattr(self.parent_window, 'on_auto_tilt_requested'):
                self.parent_window.on_auto_tilt_requested()
            else:
                print("执行自动倾转操作")
        except Exception:
            print("执行自动倾转操作")

    # 新增：选择目标执行与设置（设置同执行，弹出可能由主窗口实现）
    def execute_select_target(self):
        """执行选择目标"""
        self.statusUpdate.emit("正在执行选择目标...")
        print("执行选择目标操作")
        self.selectTargetRequested.emit()

    def settings_select_target(self):
        """选择目标设置（占位，可由主窗口处理）"""
        # 文字标签点击同样切换按钮选中状态
        if self.select_target_button:
            self.select_target_button.toggle()

    def set_select_target_checked(self, checked: bool):
        """由外部控制“选择目标”按钮按下状态"""
        if self.select_target_button:
            self.select_target_button.setChecked(bool(checked))
    
    
    
    # 设置函数
    def settings_connect_em(self):
        """连接电镜设置"""
        # 如果弹出框不存在，创建它
        if self.connect_popup is None:
            self.connect_popup = ConnectEMPopup(self)
            self.connect_popup.connectionSelected.connect(self.on_connection_selected)
            self.connect_popup.popupClosed.connect(self.on_popup_closed)
        
        # 使用保存的连接电镜标签引用
        if hasattr(self, 'connect_em_label') and self.connect_em_label:
            # 计算弹出框位置
            label_pos = self.connect_em_label.mapToGlobal(self.connect_em_label.rect().bottomLeft())
            popup_pos = QPoint(label_pos.x(), label_pos.y())
            self.connect_popup.show_at_position(popup_pos)
        else:
            # 如果找不到标签，在工具栏下方显示
            toolbar_pos = self.mapToGlobal(self.rect().bottomLeft())
            popup_pos = QPoint(toolbar_pos.x(), toolbar_pos.y())
            self.connect_popup.show_at_position(popup_pos)
    
    def on_connection_selected(self, connection_info):
        """处理连接选择"""
        if connection_info is None:
            self.statusUpdate.emit("连接失败：URL不能为空")
            return
        # 统一为远程URL
        url = connection_info.get("url", "").strip()
        if not url:
            self.statusUpdate.emit("连接失败：URL不能为空")
            return
        self.statusUpdate.emit(f"正在连接电镜: {url}")
        print(f"连接电镜: {url}")
        # 向父窗口发送连接选择信号
        self.connectionSelected.emit({"type": "remote", "url": url})
    
    def on_popup_closed(self):
        """处理弹出框关闭"""
        print("连接电镜弹出框已关闭")
    
    def settings_image_capture(self):
        """图像采集设置"""
        # 如果弹出框不存在，创建它
        if self.image_capture_popup is None:
            # 从父窗口获取agent_manager
            agent_manager = None
            try:
                agent_manager = self.parent_window.agent_manager
            except Exception:
                raise Exception("致命错误：获取agent_manager失败，父窗口无 agent manager")
            
            self.image_capture_popup = ImageCapturePopup(self, agent_manager=agent_manager)
            self.image_capture_popup.captureSettingsSelected.connect(self.on_capture_settings_selected)
            self.image_capture_popup.popupClosed.connect(self.on_capture_popup_closed)
        
        # 使用保存的图像采集标签引用
        if hasattr(self, 'image_capture_label') and self.image_capture_label:
            # 计算弹出框位置
            label_pos = self.image_capture_label.mapToGlobal(self.image_capture_label.rect().bottomLeft())
            popup_pos = QPoint(label_pos.x(), label_pos.y())
            self.image_capture_popup.show_at_position(popup_pos)
        else:
            # 如果找不到标签，在工具栏下方显示
            toolbar_pos = self.mapToGlobal(self.rect().bottomLeft())
            popup_pos = QPoint(toolbar_pos.x() + 90, toolbar_pos.y())  # 偏移到图像采集按钮位置
            self.image_capture_popup.show_at_position(popup_pos)
    
    def on_capture_settings_selected(self, settings_info):
        """处理图像采集设置选择"""
        if settings_info is None:
            self.statusUpdate.emit("图像采集设置取消")
            return
        
        try:
            # 获取原始值
            raw_values = settings_info.get("raw_values", {})
            
            # 显示设置摘要
            acq_image_size = raw_values.get("acq_image_size", "未设置")
            dwell_time = raw_values.get("dwell_time", "未设置")
            brightness = raw_values.get("brightness", "未设置")
            contrast = raw_values.get("contrast", "未设置")
            binnings = raw_values.get("binnings", "未设置")
            frames = raw_values.get("frames", "未设置")
            
            self.statusUpdate.emit(f"图像采集设置已更新: 尺寸={acq_image_size}, 驻留时间={dwell_time}μs, 亮度={brightness}%, 对比度={contrast}%, 合并度={binnings}, 帧数={frames}")
            print(f"图像采集设置: {settings_info}")
            
        except Exception as e:
            self.statusUpdate.emit(f"处理图像采集设置时出错: {e}")
            print(f"处理图像采集设置时出错: {e}")
    
    def on_capture_popup_closed(self):
        """处理图像采集弹出框关闭"""
        print("图像采集设置弹出框已关闭")
    
    def settings_select_target(self):
        """选择目标设置"""
        self.statusUpdate.emit("打开选择目标设置...")
        print("打开选择目标设置界面")

    def settings_auto_focus(self):
        """自动聚焦设置（在自动聚焦标签下呼出参数弹窗）"""
        self.statusUpdate.emit("打开自动聚焦设置...")
        try:
            # 复用弹窗实例，避免信号断开/对象被GC
            if not hasattr(self, 'autofocus_popup') or self.autofocus_popup is None:
                self.autofocus_popup = AutofocusSettingsPopup(self)
                # 将选择的参数向上传递给主窗口（由主窗口负责存储）
                def on_selected(data):
                    try:
                        self.parent_window.on_autofocus_settings_selected(data)
                    except Exception:
                        pass
                self.autofocus_popup.dataSelected.connect(on_selected)
                # 关闭时释放引用
                self.autofocus_popup.popupClosed.connect(lambda: setattr(self, 'autofocus_popup', None))
            # 以标签为基准定位弹窗
            label_pos = None
            for lbl in self._text_labels:
                if isinstance(lbl, ClickableLabel) and '自动聚焦' in lbl.text():
                    label_pos = lbl.mapToGlobal(lbl.rect().bottomLeft())
                    break
            if label_pos is None:
                label_pos = self.mapToGlobal(self.rect().bottomLeft())
            self.autofocus_popup.show_at_position(label_pos)
        except Exception as e:
            print(f"打开自动聚焦弹窗失败: {e}")
    
    def settings_auto_tilt(self):
        """自动倾转设置"""
        self.statusUpdate.emit("打开自动倾转设置...")
        try:
            if not hasattr(self, 'autotilt_popup') or self.autotilt_popup is None:
                self.autotilt_popup = AutoTiltSettingsPopup(self)
                # 将选择结果交给父窗口保存（若有对应方法）
                def on_selected(data):
                    try:
                        if hasattr(self.parent_window, 'on_autotilt_settings_selected'):
                            self.parent_window.on_autotilt_settings_selected(data)
                        else:
                            # 作为回退，在状态栏简要提示
                            self.statusUpdate.emit(f"自动倾转程序已设定，共 {len(data.get('sequence', []))} 个角度")
                    except Exception:
                        pass
                self.autotilt_popup.dataSelected.connect(on_selected)
                # 不销毁实例，保持状态以便下次打开仍显示
            # 定位到“自动倾转”文字标签下方
            label_pos = None
            for lbl in self._text_labels:
                if isinstance(lbl, ClickableLabel) and '自动倾转' in lbl.text():
                    label_pos = lbl.mapToGlobal(lbl.rect().bottomLeft())
                    break
            if label_pos is None:
                label_pos = self.mapToGlobal(self.rect().bottomLeft())
            self.autotilt_popup.show_at_position(label_pos)
        except Exception as e:
            print(f"打开自动倾转弹窗失败: {e}")

