import sys
import os
import asyncio
import logging
import qasync
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


try:
    # 添加项目根目录到路径以支持绝对导入
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    from resources.resource_manager import resource_manager
    from config.colors import colors, theme
    from agent_client import AgentClient, AgentClientError
    from view.agent_manager import AgentClientManager
    from model.targets import TargetModel, StagePose
    from autofocus.config import AutofocusSettings
    from autofocus.microscope_api import MicroscopeAPI
    from autofocus.controller import AutofocusController
    from autotilt.controller import AutoTiltController, AutoTiltSettings
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
    from view.dialogs import ConnectEMPopup
    from view.toolbar import MainToolbar
except ImportError:
    # 如果绝对导入失败，尝试相对导入
    try:
        from .widgets import ClickableLabel
        from .dialogs import ConnectEMPopup
        from .toolbar import MainToolbar
    except ImportError:
        # 如果都失败了，添加路径并导入
        import sys
        import os
        current_dir = os.path.dirname(__file__)
        sys.path.append(current_dir)
        from widgets import ClickableLabel
        from dialogs import ConnectEMPopup
        from toolbar import MainToolbar


class AsyncWorker(QThread):
    """异步工作线程，用于处理异步操作"""
    
    # 定义信号
    connectionResult = pyqtSignal(bool, str)  # 连接结果信号
    acquisitionResult = pyqtSignal(bool, object)  # 采集结果信号：成功时为结果dict，失败时为错误消息字符串
    errorOccurred = pyqtSignal(str)           # 错误信号
    
    def __init__(self, agent_manager):
        super().__init__()
        self.agent_manager = agent_manager
        self.operation = None
        self.operation_args = None
        # 复用同一个事件循环，避免跨事件循环使用同一ClientSession导致错误
        self.loop = asyncio.new_event_loop()
        # 当前正在执行的任务（便于shutdown时取消）
        self._current_task = None
        self._stopping = False
    
    def set_operation(self, operation, *args):
        """设置要执行的操作"""
        if self._stopping:
            return
        self.operation = operation
        self.operation_args = args
    
    def run(self):
        """运行异步操作"""
        try:
            if self.operation == "connect":
                self._run_connect()
            elif self.operation == "acquisition":
                self._run_acquisition()
            elif self.operation == "get_snapshot":
                self._run_get_snapshot()
        except Exception as e:
            self.errorOccurred.emit(f"异步操作执行失败: {str(e)}")
    
    def _run_connect(self):
        """运行连接操作"""
        try:
            # 复用工作线程事件循环
            asyncio.set_event_loop(self.loop)
            
            # 运行异步连接
            conn_type, server_url = self.operation_args
            coro = self.agent_manager.connect_microscope(conn_type, server_url)
            self._current_task = self.loop.create_task(coro)
            result = self.loop.run_until_complete(self._current_task)
            
            if result:
                self.connectionResult.emit(True, "连接成功")
            else:
                self.connectionResult.emit(False, "连接失败")
                
        except Exception as e:
            self.connectionResult.emit(False, f"连接错误: {str(e)}")
        finally:
            self._current_task = None
    
    def _run_acquisition(self):
        """运行图像采集操作"""
        try:
            # 复用工作线程事件循环
            asyncio.set_event_loop(self.loop)
            
            # 运行异步图像采集
            coro = self.agent_manager.start_acquisition()
            self._current_task = self.loop.create_task(coro)
            result = self.loop.run_until_complete(self._current_task)
            
            if result:
                self.acquisitionResult.emit(True, result)
            else:
                self.acquisitionResult.emit(False, "图像采集启动失败")
                
        except Exception as e:
            self.acquisitionResult.emit(False, f"图像采集错误: {str(e)}")
        finally:
            self._current_task = None

    def _run_get_snapshot(self):
        """运行获取快照操作（用于周期性刷新信息面板）"""
        try:
            # 复用工作线程事件循环
            asyncio.set_event_loop(self.loop)
            # 调用管理器获取快照（内部会通过信号发出 snapshotUpdated）
            coro = self.agent_manager.get_snapshot()
            self._current_task = self.loop.create_task(coro)
            self.loop.run_until_complete(self._current_task)
        except asyncio.CancelledError:
            # 关闭过程中取消，不视为错误
            pass
        except Exception as e:
            self.errorOccurred.emit(f"获取状态快照失败: {str(e)}")
        finally:
            self._current_task = None
    
    def stop(self):
        """停止异步工作线程"""
        try:
            self._stopping = True
            # 尽量取消当前任务
            try:
                if self.loop and self._current_task and not self._current_task.done():
                    self.loop.call_soon_threadsafe(self._current_task.cancel)
            except Exception:
                pass
            
            # 停止线程
            self.quit()
            try:
                # 尽量等待线程退出，避免与事件循环并发操作
                self.wait(5000)
            except Exception:
                pass
            
            # 清理事件循环
            if hasattr(self, 'loop') and self.loop:
                try:
                    if not self.loop.is_closed():
                        if not self.loop.is_running():
                            # 仅在未运行状态下进行协程清理
                            pending = asyncio.all_tasks(self.loop)
                            for task in pending:
                                task.cancel()
                            if pending:
                                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                            # 关闭事件循环
                            self.loop.close()
                        else:
                            # 事件循环仍在运行，跳过关闭以避免报错
                            pass
                except Exception as e:
                    print(f"清理AsyncWorker事件循环时出错: {e}")
                finally:
                    self.loop = None
                    
        except Exception as e:
            print(f"停止AsyncWorker时出错: {e}")


class ImageDisplayThread(QThread):
    """图像显示线程"""
    imageReceived = pyqtSignal(object)  # 图像数据接收信号
    errorOccurred = pyqtSignal(str)     # 错误信号
    
    def __init__(self, agent_client=None):
        super().__init__()
        self.agent_client = agent_client
        self.is_running = False
        
    def run(self):
        """运行图像接收循环"""
        if not self.agent_client:
            self.errorOccurred.emit("AgentClient未初始化")
            return
            
        self.is_running = True
        try:
            # 这里应该实现异步图像接收
            # 由于PyQt5的限制，我们使用定时器模拟
            pass
        except Exception as e:
            self.errorOccurred.emit(f"图像接收错误: {str(e)}")
        finally:
            self.is_running = False
    
    def stop(self):
        """停止图像接收"""
        self.is_running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.toolbar_widget = None
        self.image_display_thread = None
        self.current_image = None
        self._shutting_down = False
        # 当前显示目标（None 表示显示的是实时/普通图像栈）
        self._displaying_target_id = None
        # 最近一次服务器状态快照（用于在创建 Target 时绑定）
        self._latest_snapshot = None
        # 目标单选组（确保只选择一个目标）
        self.target_radio_group = QButtonGroup(self)
        self.target_radio_group.setExclusive(True)
        
        # 创建AgentClient管理器
        self.agent_manager = AgentClientManager()
        self.setup_agent_connections()
        
        # 创建异步工作线程
        self.async_worker = AsyncWorker(self.agent_manager)
        self.setup_async_worker()
        
        self.init_ui()

        self.init_timer()
    
    def setup_agent_connections(self):
        """设置AgentClient管理器信号连接"""
        # 连接状态变化信号
        self.agent_manager.connectionStatusChanged.connect(self.on_connection_status_changed)
        
        # 状态快照更新信号
        self.agent_manager.snapshotUpdated.connect(self.on_snapshot_updated)
        
        # 采集进度信号
        self.agent_manager.acquisitionProgress.connect(self.on_acquisition_progress)
        
        # 采集完成信号
        self.agent_manager.acquisitionCompleted.connect(self.on_acquisition_completed)
        
        # 采集错误信号
        self.agent_manager.acquisitionError.connect(self.on_acquisition_error)
        
        # 样品台移动完成信号
        self.agent_manager.stageMoved.connect(self.on_stage_moved)
        
        # 错误信号
        self.agent_manager.errorOccurred.connect(self.on_error_occurred)
    
    def setup_async_worker(self):
        """设置异步工作线程信号连接"""
        # 连接结果信号
        self.async_worker.connectionResult.connect(self.on_connection_result)
        self.async_worker.acquisitionResult.connect(self.on_acquisition_result)
        self.async_worker.errorOccurred.connect(self.on_async_error)
    
    def on_connection_result(self, success, message):
        """处理连接结果"""
        if success:
            self.status_bar.showMessage(message)
            # 获取状态快照
            self.async_worker.set_operation("get_snapshot")
            self.async_worker.start()
        else:
            self.status_bar.showMessage(message)
    
    def on_acquisition_result(self, success, payload):
        """处理图像采集结果"""
        if success:
            result = payload or {}
            frames_b64 = result.get("frames", []) if isinstance(result, dict) else []
            # 兼容性处理：确保frames_b64始终为列表
            try:
                if isinstance(frames_b64, (str, bytes, bytearray, memoryview)):
                    # 单帧字符串或字节：包装为列表
                    if not isinstance(frames_b64, str):
                        import base64
                        frames_b64 = [base64.b64encode(bytes(frames_b64)).decode('ascii')]
                    else:
                        frames_b64 = [frames_b64]
                elif not isinstance(frames_b64, list):
                    # 其他类型（例如None/数字/对象），不尝试展开，置为空
                    frames_b64 = []
            except Exception:
                frames_b64 = []
            if frames_b64:
                self.status_bar.showMessage(f"收到 {len(frames_b64)} 张图像")
                # 同步携带可选元数据（若服务器提供）
                shapes = result.get("frame_shapes") if isinstance(result, dict) else None
                dtypes = result.get("frame_dtypes") if isinstance(result, dict) else None
                byteorders = result.get("frame_byteorders") if isinstance(result, dict) else None
                # 若服务端上报 dtype 为 int32/float 等，提示并仍尝试按元数据解码
                try:
                    if dtypes and len(dtypes) > 0 and isinstance(dtypes[0], str):
                        dt0 = dtypes[0].lower()
                        if dt0 not in ("uint8", "uint16", "u1", "u2"):
                            self.status_bar.showMessage(f"注意: 帧dtype={dt0}，将按元数据解码")
                except Exception:
                    pass
                self.show_image_stack(frames_b64, shapes, dtypes, byteorders)
            else:
                self.status_bar.showMessage("采集成功，但未返回图像数据")
        else:
            self.status_bar.showMessage(str(payload))
    
    def on_async_error(self, error_message):
        """处理异步操作错误"""
        self.status_bar.showMessage(f"异步操作错误: {error_message}")
    
    def on_connection_status_changed(self, connected: bool):
        """处理连接状态变化"""
        self.update_ui_connection_state(connected)
        if connected:
            self.status_bar.showMessage("电镜连接成功")
            self.set_interactive_locked(False)
            # 连接成功后，若工具栏的图像采集弹窗已创建，则基于服务器状态初始化其参数
            try:
                if hasattr(self, 'toolbar_widget') and self.toolbar_widget and hasattr(self.toolbar_widget, 'image_capture_popup'):
                    popup = self.toolbar_widget.image_capture_popup
                    if popup is not None and hasattr(popup, 'reload_from_acquisition_state'):
                        popup.reload_from_acquisition_state()
            except Exception:
                pass
        else:
            self.status_bar.showMessage("电镜连接断开")
            self.set_interactive_locked(True)
    
    def on_snapshot_updated(self, snapshot):
        """处理状态快照更新"""
        # 保存全局快照
        try:
            self._latest_snapshot = snapshot
        except Exception:
            pass
        self.update_info_panel(snapshot)
    
    def on_acquisition_progress(self, current_frame: int, total_frames: int):
        """处理采集进度"""
        progress = (current_frame / total_frames) * 100 if total_frames > 0 else 0
        self.status_bar.showMessage(f"图像采集进度: {progress:.1f}% ({current_frame}/{total_frames})")
    
    def on_acquisition_completed(self):
        """处理采集完成"""
        self.status_bar.showMessage("图像采集完成")
    
    def on_acquisition_error(self, error_msg: str):
        """处理采集错误"""
        self.status_bar.showMessage(f"图像采集错误: {error_msg}")
    
    def on_stage_moved(self, x: float, y: float, z: float, alpha: float, beta: float):
        """处理样品台移动完成"""
        self.status_bar.showMessage(f"样品台移动完成: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
    
    def on_error_occurred(self, error_msg: str):
        """处理错误"""
        self.status_bar.showMessage(f"错误: {error_msg}")
    
    def closeEvent(self, event):
        """窗口关闭事件，自动断开与服务器的连接"""
        try:
            print("正在关闭主窗口，断开与服务器的连接...")
            # 标记关闭并停止刷新定时器，避免关闭过程中新任务进入
            self._shutting_down = True
            try:
                if hasattr(self, '_timer') and self._timer:
                    self._timer.stop()
            except Exception:
                pass
            
            # 检查是否已连接
            if hasattr(self, 'agent_manager') and self.agent_manager.is_connected:
                # 使用同步方式断开连接
                self._disconnect_sync()
            
            # 停止异步工作线程
            if hasattr(self, 'async_worker'):
                print("正在停止异步工作线程...")
                self.async_worker.stop()
                if not self.async_worker.wait(5000):  # 等待最多5秒
                    print("警告: 异步工作线程未能及时停止，强制终止")
                    self.async_worker.terminate()
                    self.async_worker.wait(2000)
            
            # 停止图像显示线程
            if hasattr(self, 'image_display_thread') and self.image_display_thread:
                print("正在停止图像显示线程...")
                self.image_display_thread.stop()
                if not self.image_display_thread.wait(5000):  # 等待最多5秒
                    print("警告: 图像显示线程未能及时停止，强制终止")
                    self.image_display_thread.terminate()
                    self.image_display_thread.wait(2000)
            
            print("主窗口关闭完成")
            event.accept()
            
        except Exception as e:
            print(f"关闭窗口时发生错误: {e}")
            event.accept()  # 即使出错也要关闭窗口
    
    def _disconnect_sync(self):
        """同步断开连接（在关闭事件中使用）"""
        try:
            print("正在断开与服务器的连接...")
            
            # 创建新的事件循环来执行异步断开操作
            import asyncio
            import qasync
            
            # 创建临时事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 设置超时
                async def disconnect_with_timeout():
                    try:
                        await asyncio.wait_for(
                            self.agent_manager.disconnect_microscope(), 
                            timeout=10.0  # 10秒超时
                        )
                    except asyncio.TimeoutError:
                        print("断开连接超时，强制断开")
                        # 强制断开连接
                        self.agent_manager.is_connected = False
                        self.agent_manager.agent_client = None
                
                # 运行断开连接操作
                loop.run_until_complete(disconnect_with_timeout())
                print("已断开与服务器的连接")
                
            except Exception as e:
                print(f"断开连接时发生错误: {e}")
                # 强制断开连接
                self.agent_manager.is_connected = False
                self.agent_manager.agent_client = None
            finally:
                # 清理事件循环
                try:
                    if not loop.is_closed():
                        loop.close()
                except Exception as e:
                    print(f"清理事件循环时出错: {e}")
                
        except Exception as e:
            print(f"断开连接时发生错误: {e}")
            # 强制断开连接
            self.agent_manager.is_connected = False
            self.agent_manager.agent_client = None
    
    def resizeEvent(self, event):
        """窗口大小变化事件，自动重新缩放图像"""
        super().resizeEvent(event)
        
        print(f"窗口大小变化: {event.size().width()}x{event.size().height()}")
        
        # 延迟重新缩放，避免频繁触发
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        else:
            from PyQt5.QtCore import QTimer
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._refresh_image_display)
        
        # 300ms后重新缩放图像
        self._resize_timer.start(300)
        print("已设置重新缩放定时器")
    
    def _refresh_image_display(self):
        """刷新图像显示（重新缩放）"""
        try:
            print(f"刷新图像显示，当前帧索引: {getattr(self, '_current_frame_index', 'None')}")
            
            # 检查是否有原始图像数据
            if not hasattr(self, '_original_frames_data') or not self._original_frames_data:
                # print("没有原始图像数据，无法刷新")
                return
            
            # 检查是否有图像标签
            if not hasattr(self, '_current_image_label') or not self._current_image_label:
                # print("没有图像标签引用，无法刷新")
                return
            
            # 获取当前帧数据
            current_frame_index = getattr(self, '_current_frame_index', 0)
            if current_frame_index >= len(self._original_frames_data):
                # print(f"当前帧索引超出范围: {current_frame_index} >= {len(self._original_frames_data)}")
                return
            
            # print(f"重新渲染第 {current_frame_index + 1} 帧")
            
            # 重新解码当前帧
            import base64
            b64 = self._original_frames_data[current_frame_index]
            data = base64.b64decode(b64)
            
            # 重新创建图像
            import math
            n = len(data)
            side = int(math.sqrt(n))
            if side * side != n:
                img = QImage(512, 512, QImage.Format_Grayscale8)
                img.fill(128)
            else:
                img = QImage(data, side, side, side, QImage.Format_Grayscale8)
            
            # 创建QPixmap并重新缩放
            pix = QPixmap.fromImage(img)
            scaled_pix = self._scale_image_to_fit(pix)
            
            # 更新图像标签
            self._current_image_label.setPixmap(scaled_pix)
            
            # print(f"图像刷新完成，新尺寸: {scaled_pix.width()}x{scaled_pix.height()}")
            
        except Exception as e:
            print(f"刷新图像显示时发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    def update_ui_connection_state(self, connected: bool):
        """更新UI连接状态"""
        if hasattr(self, 'toolbar_widget') and self.toolbar_widget:
            # 更新工具栏连接状态
            pass
    
    def update_info_panel(self, snapshot):
        """更新信息面板：改由 InfoPanel 渲染。"""
        if hasattr(self, 'info_panel') and self.info_panel and snapshot:
            # 填充补充字段，便于 InfoPanel 渲染
            s = dict(snapshot)
            s['server_url'] = getattr(self.agent_manager, 'server_url', '未知')
            s['connection_type'] = getattr(self.agent_manager, 'connection_type', '未知')
            self.info_panel.set_snapshot(s)
        # 同步把快照转发给中部图像面板，以便右键属性对话框读取放大倍数/位置
        try:
            # 若当前正在显示某个目标，则不要用全局快照覆盖画布的目标快照
            if hasattr(self, 'image_panel') and self.image_panel and snapshot and not getattr(self, '_displaying_target_id', None):
                self.image_panel.set_snapshot(snapshot)
        except Exception:
            pass
    
    def init_timer(self):
        """初始化定时器"""
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start()

    def _on_timer_tick(self):
        """每秒轮询一次服务器快照并刷新信息面板"""
        try:
            if self._shutting_down:
                return
            if not getattr(self.agent_manager, 'is_connected', False):
                return
            # 避免与其他长任务（connect/acquisition）竞争，同一时刻只跑一个
            if hasattr(self, 'async_worker') and self.async_worker and not self.async_worker.isRunning():
                self.async_worker.set_operation("get_snapshot")
                self.async_worker.start()
        except Exception:
            pass
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("ZhouTomo - 数据自动采集用户可视化软件")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_tool_bar()
        
        # 创建中央窗口部件
        self.create_central_widget()
        
        # 创建状态栏
        self.create_status_bar()
        
        # 连接工具栏的图像采集信号
        self.connect_image_capture_signals()

        # 启动时进入“未连接锁定”模式
        self.set_interactive_locked(True)
    
    def connect_image_capture_signals(self):
        """连接图像采集相关信号"""
        if hasattr(self, 'toolbar_widget') and self.toolbar_widget:
            # 连接图像采集按钮的信号
            self.toolbar_widget.imageCaptureRequested.connect(self.start_image_acquisition)
            # 连接选择目标信号
            self.toolbar_widget.selectTargetRequested.connect(self.start_select_target)  # 兼容旧逻辑
            self.toolbar_widget.selectTargetToggled.connect(self.on_select_target_toggled)
            print("图像采集信号已连接")
        # 画布图像更新 -> 同步刷新Histogram/FFT
        # 面板化后：图像更新信号由 image_panel 转发
        if hasattr(self, 'image_panel') and self.image_panel:
            try:
                self.image_panel.imageUpdated.connect(self.update_analysis_panels)
            except Exception:
                pass
    
    # ==================================
    # ======== 各类 Toolbar 回调 ========
    # ==================================
    
    # 接收自动聚焦参数并存储
    def on_autofocus_settings_selected(self, data):
        try:
            if not data:
                return
            dm = self._ensure_data_model()
            dm['autofocus_settings'] = data
            self.status_bar.showMessage(
                f"自动聚焦参数已保存: OFRS={data['ofrs_step_nm']}nm, FRS={data['frs_step_nm']}nm, iters={data['max_iterations']}"
            )
        except Exception as e:
            self.status_bar.showMessage(f"保存自动聚焦参数失败: {e}")

    # 接收自动倾转参数并存储
    def on_autotilt_settings_selected(self, data):
        try:
            if not data:
                return
            dm = self._ensure_data_model()
            dm['autotilt_settings'] = data
            seq = data.get('sequence', []) if isinstance(data, dict) else []
            hrm = data.get('hr_magnification', None)
            self.status_bar.showMessage(
                f"自动倾转参数已保存: 角度数={len(seq)}, HR倍率={hrm if hrm else '未设置'}"
            )
            # 立即在信息面板展示计划角度列表
            try:
                if hasattr(self, 'info_panel') and self.info_panel:
                    self.info_panel.set_autotilt_plan(list(seq))
            except Exception:
                pass
        except Exception as e:
            self.status_bar.showMessage(f"保存自动倾转参数失败: {e}")

    # 执行自动聚焦
    def on_auto_focus_requested(self):
        """执行自动聚焦"""
        try:
            self.status_bar.showMessage("正在执行自动聚焦...")

            # 1) 取得选中的目标 target_id
            target_id = None
            # 遍历左侧列表，找被勾选的单选框
            # 从 FilePanel 读取（遍历其 list）
            if hasattr(self, 'file_panel') and self.file_panel and hasattr(self.file_panel, 'list'):
                flist = self.file_panel.list
                for i in range(flist.count()):
                    item = flist.item(i)
                    widget = flist.itemWidget(item)
                    if widget and hasattr(widget, 'radio') and widget.radio.isChecked():
                        target_id = item.data(Qt.UserRole)
                        break
            if not target_id:
                self.status_bar.showMessage("请先在左侧选择一个目标（单选框）")
                return

            dm = self._ensure_data_model()
            target_models = dm.get('target_models', {})
            if target_id not in target_models:
                self.status_bar.showMessage("内部错误：未找到目标数据模型")
                return
            target_model = target_models[target_id]

            # 2) 读取自动聚焦参数
            cfg = AutofocusSettings.from_dict(dm.get('autofocus_settings', {}))

            # 3) 显微镜 API + 控制器
            if not hasattr(self, 'agent_manager') or not self.agent_manager:
                self.status_bar.showMessage("未连接显微镜，无法执行自动聚焦")
                return
            api = MicroscopeAPI(self.agent_manager)
            controller = AutofocusController(api, target_model, cfg, parent=self)
            self._af_controller = controller  # 保存引用，便于取消

            # 4) 连接信号更新 UI
            controller.frame.connect(lambda arr: self.image_panel.set_image_array(arr) if hasattr(self, 'image_panel') and self.image_panel else None)
            controller.progress.connect(lambda step, msg: self.status_bar.showMessage(f"[AF] {step}: {msg}"))
            controller.error.connect(lambda msg: self.status_bar.showMessage(f"自动聚焦错误: {msg}"))
            # 动态曲线更新
            try:
                if hasattr(self, 'info_panel') and self.info_panel and hasattr(self.info_panel, 'append_focus_point'):
                    controller.focusMetric.connect(self._on_focus_metric)
                    # 复刻旧版：曲线与样张联动
                    if hasattr(self.info_panel, 'update_focus_curves'):
                        controller.focusCurvesUpdated.connect(lambda rx, ry, sx, sy: self.info_panel.update_focus_curves(rx, ry, sx, sy))
                    if hasattr(self.info_panel, 'set_sample_roi'):
                        controller.sampleROI.connect(self.info_panel.set_sample_roi)
            except Exception:
                pass
            # 清晰度曲线：启动前重置；过程中追加点；结束时可保留
            try:
                if hasattr(self, 'info_panel') and self.info_panel:
                    self.info_panel.reset_focus_curve()
            except Exception:
                pass
            controller.focusMetric.connect(self._on_focus_metric)
            def on_finish(ok, info):
                if ok:
                    self.status_bar.showMessage("自动聚焦完成")
                else:
                    self.status_bar.showMessage(f"自动聚焦失败: {info}")
            controller.finished.connect(on_finish)

            # 5) 启动
            controller.start()
        except Exception as e:
            self.status_bar.showMessage(f"启动自动聚焦失败: {e}")

    def _on_focus_metric(self, defocus_um: float, definition_value: float, step_idx: int):
        try:
            if hasattr(self, 'info_panel') and self.info_panel:
                self.info_panel.append_focus_point(defocus_um, definition_value)
        except Exception:
            pass

    # 执行自动倾转
    def on_auto_tilt_requested(self):
        try:
            self.status_bar.showMessage("正在执行自动倾转...")
            # 1) 取得选中的目标 target_id
            target_id = None
            if hasattr(self, 'file_panel') and self.file_panel and hasattr(self.file_panel, 'list'):
                flist = self.file_panel.list
                for i in range(flist.count()):
                    item = flist.item(i)
                    widget = flist.itemWidget(item)
                    if widget and hasattr(widget, 'radio') and widget.radio.isChecked():
                        target_id = item.data(Qt.UserRole)
                        break
            if not target_id:
                self.status_bar.showMessage("请先在左侧选择一个目标（单选框）")
                return
            dm = self._ensure_data_model()
            target_models = dm.get('target_models', {})
            if target_id not in target_models:
                self.status_bar.showMessage("内部错误：未找到目标数据模型")
                return
            target_model = target_models[target_id]
            # 2) 读取自动倾转参数 + 自动聚焦参数
            at_cfg = AutoTiltSettings.from_dict(dm.get('autotilt_settings', {}))
            af_cfg_dict = dm.get('autofocus_settings', {})
            # 3) 显微镜 API + 控制器
            if not hasattr(self, 'agent_manager') or not self.agent_manager:
                self.status_bar.showMessage("未连接显微镜，无法执行自动倾转")
                return
            api = MicroscopeAPI(self.agent_manager)
            controller = AutoTiltController(api, target_model, at_cfg, af_cfg_dict, parent=self)
            self._at_controller = controller
            # 4) 连接信号更新 UI
            controller.frame.connect(lambda arr: self.image_panel.set_image_array(arr) if hasattr(self, 'image_panel') and self.image_panel else None)
            controller.progress.connect(lambda step, msg: self.status_bar.showMessage(f"[AT] {step}: {msg}"))
            # 同步当前 alpha & 对焦状态显示：在 progress 回调里解析 alpha 文本
            def _on_at_progress(step, msg):
                self.status_bar.showMessage(f"[AT] {step}: {msg}")
                try:
                    if hasattr(self, 'info_panel') and self.info_panel and 'alpha=' in str(msg):
                        import re
                        m = re.search(r"alpha=([\-0-9\.]+)", str(msg))
                        if m:
                            self.info_panel.set_autotilt_alpha(float(m.group(1)))
                    # 同步更新计划（当用户刚打开时先把计划显示出来）
                    if hasattr(self, 'info_panel') and self.info_panel and hasattr(at_cfg, 'sequence'):
                        if not getattr(self.info_panel, '_at_plan', None):
                            self.info_panel.set_autotilt_plan(list(at_cfg.sequence))
                except Exception:
                    pass
            controller.progress.disconnect()
            controller.progress.connect(_on_at_progress)
            controller.error.connect(lambda msg: self.status_bar.showMessage(f"自动倾转错误: {msg}"))
            def on_finish(ok, info):
                if ok:
                    self.status_bar.showMessage("自动倾转完成")
                else:
                    self.status_bar.showMessage(f"自动倾转失败: {info}")
            controller.finished.connect(on_finish)
            # 5) 启动
            controller.start()
        except Exception as e:
            self.status_bar.showMessage(f"启动自动倾转失败: {e}")

    def _on_export_tilt_series_requested(self, target_id: str):
        try:
            if not target_id:
                return
            dm = self._ensure_data_model()
            tm = dm.get('target_models', {}).get(target_id)
            if tm is None:
                self.status_bar.showMessage("未找到目标数据")
                return
            import numpy as np
            alphas = np.array(getattr(tm, 'tilt_alpha_series', []) or [], dtype=np.float32)
            globals_stack = [gi.image for gi in getattr(tm, 'tilt_global_series', []) if getattr(gi, 'image', None) is not None]
            hrs_stack = [hi.image for hi in getattr(tm, 'tilt_highres_series', []) if getattr(hi, 'image', None) is not None]
            if not len(alphas):
                self.status_bar.showMessage("该目标暂无倾转数据")
                return
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "保存倾转序列", f"{tm.name}_tilt_series.npz", "Numpy Zip (*.npz)")
            if not path:
                return
            np.savez_compressed(path,
                                alpha=alphas,
                                globals=np.array(globals_stack, dtype=object),
                                highs=np.array(hrs_stack, dtype=object))
            self.status_bar.showMessage(f"已保存倾转序列到: {path}")
        except Exception as e:
            self.status_bar.showMessage(f"保存倾转序列失败: {e}")

    # def open_autofocus_settings(self):
    #     """打开自动聚焦参数设置弹窗，并保存参数到数据模型"""
    #     try:
    #         from view.dialogs import AutofocusSettingsPopup
    #         dlg = AutofocusSettingsPopup(self)
    #         def on_selected(data):
    #             if not data:
    #                 return
    #             dm = self._ensure_data_model()
    #             dm['autofocus_settings'] = data
    #             self.status_bar.showMessage(
    #                 f"自动聚焦参数已保存: OFRS={data['ofrs_step_nm']}nm, FRS={data['frs_step_nm']}nm, iters={data['max_iterations']}"
    #             )
    #         dlg.dataSelected.connect(on_selected)
    #         pos = self.mapToGlobal(QPoint(160, 120))
    #         dlg.show_at_position(pos)
    #     except Exception as e:
    #         self.status_bar.showMessage(f"打开自动聚焦参数弹窗失败: {e}")

    # ========================= 选择目标（框选）相关 =========================
    def start_select_target(self):
        """进入框选模式：允许在图像显示区域拖拽绘制矩形，完成后生成目标缩略并加入左侧文件列表"""
        try:
            if hasattr(self, 'image_panel') and self.image_panel:
                # 确保画布拥有焦点，避免键鼠事件被父级抢占
                self.image_panel.image_canvas.setFocus()
                self.image_panel.enable_selection(True)
                self.status_bar.showMessage("框选模式：在图像上拖拽选择目标")
        except Exception as e:
            self.status_bar.showMessage(f"进入框选模式失败: {e}")

    def on_select_target_toggled(self, checked: bool):
        """工具栏按钮按下/松开 -> 开启/关闭框选模式"""
        try:
            if hasattr(self, 'image_panel') and self.image_panel:
                if checked:
                    self.image_panel.image_canvas.setFocus()
                self.image_panel.enable_selection(bool(checked))
                if not checked:
                    # 关闭时清空当前可视选择
                    try:
                        self.image_panel.clear_selection()
                    except Exception:
                        pass
                self.status_bar.showMessage("框选模式：在图像上拖拽选择目标" if checked else "已退出框选模式")
            # 同步 toolbar 按钮状态，避免外部调用时状态不同步
            if hasattr(self, 'toolbar_widget') and self.toolbar_widget and hasattr(self.toolbar_widget, 'set_select_target_checked'):
                self.toolbar_widget.set_select_target_checked(bool(checked))
        except Exception as e:
            self.status_bar.showMessage(f"切换框选模式失败: {e}")

    def _on_canvas_selection(self, x0: float, y0: float, x1: float, y1: float):
        """接收 Matplotlib 选择的矩形（数据坐标），完成裁剪与入库。
        坚决使用像素对齐策略：x 使用 floor/ceil 到最近像素边界，避免 off-by-one。
        """
        try:
            import math
            # 使用 floor/ceil 保证包含期望像素区域
            x_min_f, x_max_f = (min(x0, x1), max(x0, x1))
            y_min_f, y_max_f = (min(y0, y1), max(y0, y1))
            x_min, x_max = (math.floor(x_min_f), math.ceil(x_max_f))
            y_min, y_max = (math.floor(y_min_f), math.ceil(y_max_f))
            if x_max <= x_min or y_max <= y_min:
                return

            # 获取当前 numpy 图像
            img = None
            if hasattr(self, 'image_panel') and self.image_panel:
                img = self.image_panel.get_current_image_array()
            if img is None:
                return

            # 裁剪区域（注意数组索引 [y, x]）
            y_min = max(0, y_min)
            x_min = max(0, x_min)
            y_max = min(img.shape[0], y_max)
            x_max = min(img.shape[1], x_max)
            cropped_arr = img[y_min:y_max, x_min:x_max]
            if cropped_arr.size == 0:
                return

            # 转为 QPixmap 以便预览（使用拷贝方式，避免临时缓冲区失效）
            from PyQt5.QtGui import QImage, QPixmap
            import numpy as np
            arr = np.ascontiguousarray(cropped_arr)
            # 统一进行到 8bit 的线性归一化，避免 int32/float 直接截断导致全白/全黑
            if arr.dtype == np.uint16:
                maxv = int(arr.max()) if arr.size else 65535
                maxv = max(1, maxv)
                arr8 = (arr.astype(np.float32) * (255.0 / maxv)).clip(0, 255).astype(np.uint8)
            elif arr.dtype == np.uint8:
                arr8 = arr
            else:
                arr_f = arr.astype(np.float32)
                try:
                    # 使用分位数抑制极端值，提升可视效果
                    vmin = float(np.percentile(arr_f, 1))
                    vmax = float(np.percentile(arr_f, 99))
                except Exception:
                    vmin = float(arr_f.min()) if arr_f.size else 0.0
                    vmax = float(arr_f.max()) if arr_f.size else 1.0
                if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
                    arr8 = np.clip(arr_f, 0, 255).astype(np.uint8)
                else:
                    scale = 255.0 / (vmax - vmin)
                    arr8 = ((arr_f - vmin) * scale).clip(0, 255).astype(np.uint8)

            if arr8.ndim == 2:
                h, w = arr8.shape
                bytes_per_line = w
                qimg = QImage(arr8.tobytes(), w, h, bytes_per_line, QImage.Format_Grayscale8)
            elif arr8.ndim == 3 and arr8.shape[2] >= 3:
                h, w, c = arr8.shape
                # 若为RGBA，先取前3通道
                if c > 3:
                    arr8 = arr8[:, :, :3].copy()
                    c = 3
                bytes_per_line = w * c
                qimg = QImage(arr8.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
            else:
                # 无法识别，创建占位图
                qimg = QImage(64, 64, QImage.Format_Grayscale8)
                qimg.fill(128)
            pix = QPixmap.fromImage(qimg.copy())

            # 左侧列表预览改为在 _save_target_to_model 中统一处理

            # 存入数据模型（保存原图 id、矩形等）
            rect = (x_min, y_min, x_max - x_min, y_max - y_min)
            # 在保存时传入完整帧，便于写入 TargetModel.global_images 与绑定快照
            self._save_target_to_model(pix, rect, full_image=img)
            self._target_counter = getattr(self, '_target_counter', 0) + 1
            self.status_bar.showMessage("框选完成")
            # 完成一次框选后自动退出框选模式，防止连续误画
            self.on_select_target_toggled(False)
        except Exception as e:
            self.status_bar.showMessage(f"处理框选失败: {e}")

    def _handle_selection_rect(self, rect: QRect):
        """根据视口矩形，在当前显示图像上裁剪目标缩略，并加入左侧文件列表与数据模型"""
        try:
            if not hasattr(self, '_current_image_label') or self._current_image_label is None:
                # 如果当前是初始 image_label
                target_label = getattr(self, 'image_label', None)
            else:
                target_label = self._current_image_label
            if target_label is None or target_label.pixmap() is None:
                return

            # 旧的基于 QLabel 的裁剪逻辑已被 Matplotlib 替代
            pass
        except Exception as e:
            self.status_bar.showMessage(f"处理框选失败: {e}")

    # ========================= 数据模型 =========================
    def _ensure_data_model(self):
        if not hasattr(self, '_data_model'):
            self._data_model = {
                'images': [],      # [{'id': str, 'frames': [...]}]
                'targets': [],     # [{'id': str, 'thumb': QPixmap, 'rect': (x,y,w,h), 'source_image_id': str}]
                'target_models': {}  # target_id -> TargetModel
            }
        return self._data_model

    def _save_target_to_model(self, pixmap: QPixmap, rect=None, full_image=None):
        model = self._ensure_data_model()
        from uuid import uuid4
        target_id = str(uuid4())
        model['targets'].append({
            'id': target_id,
            'thumb': pixmap,
            'rect': rect,
            'source_image_id': None
        })
        # 同步创建 TargetModel
        try:
            display_name = f"目标 {getattr(self, '_target_counter', 0) + 1}"
            tm = TargetModel(target_id=target_id, name=display_name, preview_pixmap=pixmap, rect=rect)
            # 绑定创建时的快照
            try:
                if isinstance(getattr(self, '_latest_snapshot', None), dict):
                    tm.snapshot = dict(self._latest_snapshot)
            except Exception:
                pass
            # 同步写入 GlobalImage
            try:
                if full_image is not None:
                    mag = None
                    try:
                        if isinstance(tm.snapshot, dict):
                            mag = tm.snapshot.get('illumination', {}).get('stem_magnification')
                    except Exception:
                        mag = None
                    mag_val = float(mag) if isinstance(mag, (int, float)) else 0.0
                    tm.add_global(full_image, magnification=mag_val)
            except Exception:
                pass
            model['target_models'][target_id] = tm
        except Exception:
            pass
        # 使用自定义小部件，左上角带单选框
        if hasattr(self, 'file_panel') and self.file_panel is not None:
            display_name = f"目标 {getattr(self, '_target_counter', 0) + 1}"
            self.file_panel.add_target(target_id, pixmap, display_name)

    def set_interactive_locked(self, locked: bool):
        """未连接前锁定交互：仅允许工具栏中的“连接电镜”按钮和标签可用。"""
        try:
            # 工具栏条目处理
            if hasattr(self, 'toolbar_widget') and self.toolbar_widget:
                if locked:
                    self.toolbar_widget.set_pre_connection_mode(True)
                else:
                    self.toolbar_widget.set_all_enabled(True)

            # 中央区控件禁用
            if hasattr(self, 'image_scroll') and self.image_scroll:
                self.image_scroll.setEnabled(not locked)
            if hasattr(self, 'file_panel') and self.file_panel:
                self.file_panel.setEnabled(not locked)
            if hasattr(self, 'info_text') and self.info_text:
                self.info_text.setReadOnly(True)
                self.info_text.setEnabled(not locked)

            # 菜单栏
            mb = self.menuBar()
            if mb:
                mb.setEnabled(not locked)
        except Exception:
            pass
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        # 新建项目动作
        new_action = QAction('新建项目', self)
        new_action.setShortcut('Ctrl+N')
        new_action.setStatusTip('创建新的项目')
        file_menu.addAction(new_action)
        
        # 打开项目动作
        open_action = QAction('打开项目', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('打开现有项目')
        file_menu.addAction(open_action)
        
        # 保存项目动作
        save_action = QAction('保存项目', self)
        save_action.setShortcut('Ctrl+S')
        save_action.setStatusTip('保存当前项目')
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('退出应用程序')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        
        # 设置动作
        settings_action = QAction('设置', self)
        settings_action.setStatusTip('打开设置对话框')
        edit_menu.addAction(settings_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        
        # 工具栏动作
        toolbar_action = QAction('工具栏', self)
        toolbar_action.setCheckable(True)
        toolbar_action.setChecked(True)
        toolbar_action.triggered.connect(self.toggle_toolbar)
        view_menu.addAction(toolbar_action)
        
        # 状态栏动作
        statusbar_action = QAction('状态栏', self)
        statusbar_action.setCheckable(True)
        statusbar_action.setChecked(True)
        statusbar_action.triggered.connect(self.toggle_statusbar)
        view_menu.addAction(statusbar_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        # 关于动作
        about_action = QAction('关于', self)
        about_action.setStatusTip('显示关于对话框')
        help_menu.addAction(about_action)
    
    def toggle_toolbar(self, checked):
        """切换工具栏显示状态"""
        if checked:
            self.toolBar.show()
        else:
            self.toolBar.hide()
    
    def toggle_statusbar(self, checked):
        """切换状态栏显示状态"""
        if checked:
            self.status_bar.show()
        else:
            self.status_bar.hide()
    
    def create_tool_bar(self):
        """创建工具栏"""
        # 创建工具栏实例
        self.toolbar_widget = MainToolbar(self)
        
        # 连接信号
        self.toolbar_widget.connectionSelected.connect(self.on_connection_selected)
        self.toolbar_widget.statusUpdate.connect(self.update_status)
        
        # 将工具栏添加到主窗口
        self.toolBar = QToolBar()
        self.toolBar.setStyleSheet(f"""
            QToolBar {{
                background-color: {colors.TOOLBAR_BACKGROUND};
                border: 0px solid {colors.BORDER_COLOR};
            }}
        """)
        self.toolBar.addWidget(self.toolbar_widget)
        self.toolBar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolBar)
    
    def update_status(self, message):
        """更新状态栏消息"""
        self.status_bar.showMessage(message)
    
    def on_connection_selected(self, connection_info):
        """处理连接选择"""
        if connection_info is None:
            self.status_bar.showMessage("连接失败：URL不能为空")
            return
        
        # 统一为远程URL连接
        try:
            url = connection_info.get("url", "").strip()
            if not url:
                self.status_bar.showMessage("连接失败：URL不能为空")
                return
            self.status_bar.showMessage(f"正在连接电镜: {url}")
            self.async_worker.set_operation("connect", "remote", url)
            self.async_worker.start()
        except Exception as e:
            self.status_bar.showMessage(f"连接电镜时发生错误: {str(e)}")
            print(f"连接电镜时发生错误: {e}")
    
    # =============================
    # ======== 中央窗口部件 ========
    # =============================
    def create_central_widget(self):
        """创建中央窗口部件（使用拆分后的面板组件）"""
        # 延迟导入，避免循环依赖
        from view.panels.file_panel import FilePanel
        from view.panels.image_panel import ImagePanel
        from view.panels.info_panel import InfoPanel
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: {colors.LIGHT_BACKGROUND};")
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        # 设置 splitter 的样式
        splitter.setStyleSheet(f"""
            QSplitter {{
                background-color: {colors.DARK_BACKGROUND};
                border: 0px solid {colors.BORDER_COLOR};
            }}
        """)

        main_layout.addWidget(splitter)
        
        # 左：目标列表
        self.file_panel = FilePanel()
        self.file_panel.set_button_group(self.target_radio_group)
        splitter.addWidget(self.file_panel)
        # 双击目标 -> 显示其 GlobalImage
        try:
            self.file_panel.list.itemDoubleClicked.connect(self._on_file_item_double_clicked)
        except Exception:
            pass
        # 右键菜单导出倾转序列
        try:
            self.file_panel.targetExportTiltSeries.connect(self._on_export_tilt_series_requested)
        except Exception:
            pass
        
        # 中：图像面板
        self.image_panel = ImagePanel()
        splitter.addWidget(self.image_panel)
        # 桥接信号
        self.image_panel.selectionMade.connect(self._on_canvas_selection)
        self.image_panel.imageUpdated.connect(self.update_analysis_panels)
        
        # 右：信息面板
        self.info_panel = InfoPanel()
        splitter.addWidget(self.info_panel)
        
        # 设置分割器比例
        splitter.setSizes([250, 600, 350])
    
    def create_image_panel(self, parent):
        """已拆分为 panels/image_panel.ImagePanel。保留空壳以兼容旧调用（不再使用）。"""
        from view.panels.image_panel import ImagePanel
        self.image_panel = ImagePanel()
        self.image_panel.selectionMade.connect(self._on_canvas_selection)
        parent.addWidget(self.image_panel)
    
    # =============================
    # ======== 左侧目标选择 ========
    # =============================
    # create_file_panel 已拆分到 panels/file_panel.py

    # 自定义目标项小部件
    # _TargetItemWidget 已迁移到 panels/file_panel.py

    # 右键菜单：选择、删除、重命名
    # 目标上下文菜单处理迁移到 panels/file_panel.py
    
    # =============================
    # ======== 右侧信息面板 ========
    # =============================
    # 右侧信息面板已拆分到 panels/info_panel.py

    # Histogram/FFT 已拆分到 panels/info_panel.py

    # 信息文本面板已拆分到 panels/info_panel.py


    def update_analysis_panels(self, image_array):
        """根据当前图像刷新右侧 Histogram 和 FFT 面板"""
        if hasattr(self, 'info_panel') and self.info_panel:
            self.info_panel.update_analysis(image_array)
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态栏样式
        self.status_bar.setStyleSheet("""
            QStatusBar {
                border-top: 1px solid #cccccc;
                background-color: #f0f0f0;
            }
        """)
        
        self.status_bar.showMessage("就绪")
    
    def update_image_info(self, image):
        """更新图像信息面板"""
        try:
            if not image or image.isNull():
                return
            
            # 获取图像信息
            width = image.width()
            height = image.height()
            format_name = image.format()
            depth = image.depth()
            
            # 格式化信息文本
            info_text = f"""图像信息:
            
文件名: {getattr(self, 'current_image_path', '未知')}
图像尺寸: {width} x {height} 像素
颜色深度: {depth} 位
图像格式: {format_name}
文件大小: {getattr(self, 'current_image_size', '未知')}
创建时间: {getattr(self, 'current_image_created', '未知')}
修改时间: {getattr(self, 'current_image_modified', '未知')}"""
            
            # 更新信息面板
            if hasattr(self, 'info_text'):
                self.info_text.setPlainText(info_text)
                
        except Exception as e:
            print(f"更新图像信息时发生错误: {e}")
    
    def show_error_message(self, message):
        """显示错误消息"""
        self.image_label.setText(f"错误: {message}")
        self.image_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.TEXT_NORMAL};
                font-size: 14px;
                background-color: {colors.LIGHT_BACKGROUND};
                border: 1px solid {colors.BORDER_COLOR};
                padding: 20px;
            }}
        """)
        self.status_bar.showMessage(f"图像显示错误: {message}")
    
    # def clear_image(self):
    #     """清除当前图像"""
    #     self.current_image = None
    #     self.image_label.setText("请选择图像文件或点击图像采集按钮")
    #     self.image_label.setStyleSheet(f"""
    #         QLabel {{
    #             color: #666666;
    #             font-size: 14px;
    #             background-color: {colors.DARK_BACKGROUND};
    #             border: none;
    #             padding: 20px;
    #         }}
    #     """)
        
    #     # 清除信息面板
    #     if hasattr(self, 'info_text'):
    #         self.info_text.setPlainText("电镜信息将在此显示...\n\n连接状态: 未连接\n服务器URL: \n连接类型: \n组件数量: \n状态: ")
        
    #     self.status_bar.showMessage("图像已清除")
    
    def start_image_acquisition(self):
        """开始图像采集"""
        try:
            self.status_bar.showMessage("正在启动图像采集...")
            
            # 检查电镜连接状态
            if not self.agent_manager.is_connected:
                self.status_bar.showMessage("电镜未连接，请先连接电镜")
                return
            
            # 使用异步工作线程
            self.async_worker.set_operation("acquisition")
            self.async_worker.start()
            
        except Exception as e:
            self.show_error_message(f"启动图像采集时发生错误: {str(e)}")

    def show_image_stack(self, frames_b64_list, frame_shapes=None, frame_dtypes=None, frame_byteorders=None):
        """将帧栈交由 ImagePanel 处理并刷新右侧分析。"""
        try:
            # 回到普通图像显示模式
            self._displaying_target_id = None
            if not hasattr(self, 'image_panel') or not self.image_panel:
                return
            self.image_panel.set_image_stack(frames_b64_list, frame_shapes, frame_dtypes, frame_byteorders)
            first = self.image_panel.get_current_image_array()
            if first is not None:
                self.update_analysis_panels(first)
        except Exception as e:
            self.status_bar.showMessage(f"图像堆栈显示错误: {str(e)}")

    def _on_file_item_double_clicked(self, item):
        """双击左侧目标 -> 显示该目标的最新 GlobalImage，并设置画布快照为目标快照。"""
        try:
            if item is None:
                return
            target_id = item.data(Qt.UserRole)
            if not target_id:
                return
            dm = self._ensure_data_model()
            tm = dm.get('target_models', {}).get(target_id)
            if tm is None:
                self.status_bar.showMessage("未找到目标数据")
                return
            if not getattr(tm, 'global_images', None):
                self.status_bar.showMessage("该目标尚无 GlobalImage")
                return
            gi = tm.global_images[-1]
            arr = getattr(gi, 'image', None)
            if arr is None:
                self.status_bar.showMessage("GlobalImage 无图像数据")
                return
            self._displaying_target_id = target_id
            if hasattr(self, 'image_panel') and self.image_panel:
                self.image_panel.set_image_array(arr)
                if isinstance(getattr(tm, 'snapshot', None), dict):
                    self.image_panel.set_snapshot(tm.snapshot)
            self.update_analysis_panels(arr)
            self.status_bar.showMessage(f"显示 {getattr(tm, 'name', '目标')} 的 GlobalImage")
        except Exception as e:
            self.status_bar.showMessage(f"显示目标图像失败: {e}")

    def _on_frame_slider_changed(self, value: int):
        try:
            # 重定向到 ImagePanel 的滑块处理（向后兼容旧接口调用）
            idx = max(1, int(value))
            if hasattr(self, 'image_panel') and self.image_panel:
                self.image_panel._on_frame_slider_changed(idx)
        except Exception:
            pass

    def _on_frame_edit_finished(self):
        try:
            # 兼容旧调用：把文本取自 image_panel
            if not hasattr(self, 'image_panel') or not self.image_panel:
                return
            total = len(getattr(self.image_panel, '_original_frames_data', []) )
            text = self.image_panel.frame_edit.text().strip()
            original_text = text
            # 支持“n / m”或仅“n”
            if '/' in text:
                left = text.split('/', 1)[0].strip()
            else:
                left = text
            frame_num = int(left)
            if 1 <= frame_num <= total:
                # 触发滑块更新 -> 会自动刷新图像并写回文本
                self.image_panel.frame_slider.setValue(frame_num)
            else:
                # 超界恢复
                self.image_panel.frame_edit.setText(f"{self.image_panel._current_frame_index + 1} / {total}")
        except Exception:
            # 解析失败恢复
            if hasattr(self, 'image_panel') and self.image_panel:
                total = len(getattr(self.image_panel, '_original_frames_data', []))
                self.image_panel.frame_edit.setText(f"{getattr(self.image_panel, '_current_frame_index', 0) + 1} / {total}")
    
    def _scale_image_to_fit(self, pixmap):
        """缩放图像以适应显示区域"""
        try:
            if not hasattr(self, 'image_scroll') or not self.image_scroll:
                return pixmap
            
            # 获取显示区域大小
            scroll_size = self.image_scroll.size()
            available_width = scroll_size.width() - 40  # 减去边距
            available_height = scroll_size.height() - 80  # 减去边距和控件高度
            
            # 计算缩放比例，保持宽高比
            scale_x = available_width / pixmap.width() if pixmap.width() > 0 else 1
            scale_y = available_height / pixmap.height() if pixmap.height() > 0 else 1
            scale = min(scale_x, scale_y, 1.0)  # 不放大，只缩小
            
            # 缩放图像
            if scale < 1.0:
                scaled_pix = pixmap.scaled(
                    int(pixmap.width() * scale),
                    int(pixmap.height() * scale),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                return scaled_pix
            else:
                return pixmap
                
        except Exception as e:
            print(f"缩放图像时发生错误: {e}")
            return pixmap


if __name__ == '__main__':
    # 如果直接运行此文件，显示主窗口（用于开发调试）
    app = QApplication(sys.argv)
    
    # 创建qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()
    
    # 运行事件循环
    with loop:
        loop.run_forever()
