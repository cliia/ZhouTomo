# 弹出框系统重构说明

## 概述
基于用户需求，为"图像采集"Label创建了新的popup弹出框，并重构了整个弹出框系统，采用面向对象的继承设计模式。

## 架构设计

### 基类：BasePopup
创建了 `BasePopup` 作为所有弹出框的父类，提供统一的基础功能：

**主要特性：**
- 统一的窗口属性设置
- 标准化的布局管理
- 通用的按钮区域
- 一致的样式设置
- 信号槽机制

**核心方法：**
- `init_base_ui()`: 初始化基础UI结构
- `init_content()`: 内容初始化（子类重写）
- `get_data()`: 数据获取（子类重写）
- `accept_data()`: 数据确认处理
- `show_at_position()`: 定位显示

### 子类实现

#### 1. ConnectEMPopup（重构）
继承 `BasePopup`，保持原有功能：
- 本地/远程/模拟连接选择
- URL输入框动态启用
- 向后兼容性保持

#### 2. ImageCapturePopup（新建）
全新的图像采集参数设置弹出框：

**五个核心参数：**

1. **亮度设置**
   - 下拉选择：自动/低/中/高/自定义
   - 自定义时启用数值输入框（0-100%）

2. **对比度设置**
   - 下拉选择：自动/低/中/高/自定义
   - 自定义时启用数值输入框（0-100%）

3. **分辨率设置**
   - 预设选项：512×512, 1024×1024, 2048×2048, 4096×4096
   - 自定义时启用宽度×高度输入框（64-8192）

4. **驻留时间设置**
   - 预设选项：极快(1μs), 快速(5μs), 标准(10μs), 慢速(50μs)
   - 自定义时启用浮点数输入框（0.1-1000.0μs）

5. **合并度设置**
   - 预设选项：无合并(1×1), 2×2, 4×4, 8×8合并
   - 自定义时启用整数输入框（1-16×）

## 使用方式

### 在工具栏中集成

```python
# 在 MainToolbar 中
def settings_image_capture(self):
    if self.image_capture_popup is None:
        self.image_capture_popup = ImageCapturePopup(self)
        self.image_capture_popup.captureSettingsSelected.connect(self.on_capture_settings_selected)
        self.image_capture_popup.popupClosed.connect(self.on_capture_popup_closed)
    
    # 定位显示
    label_pos = self.image_capture_label.mapToGlobal(self.image_capture_label.rect().bottomLeft())
    self.image_capture_popup.show_at_position(QPoint(label_pos.x(), label_pos.y()))
```

### 数据结构

**图像采集设置返回的数据格式：**
```python
{
    "brightness": {"mode": "自动", "value": "自动"},
    "contrast": {"mode": "中", "value": "中"},
    "resolution": {"mode": "1024x1024", "value": "1024x1024"},
    "dwell_time": {"mode": "标准 (10μs)", "value": "标准 (10μs)"},
    "binning": {"mode": "无合并 (1×1)", "value": "无合并 (1×1)"}
}
```

**自定义值示例：**
```python
{
    "brightness": {"mode": "自定义", "value": 75},
    "contrast": {"mode": "自定义", "value": 60},
    "resolution": {"mode": "自定义", "value": "1280x720"},
    "dwell_time": {"mode": "自定义", "value": 25.5},
    "binning": {"mode": "自定义", "value": 3}
}
```

## 技术特性

### 1. 智能UI控制
- 下拉框选择自动启用/禁用对应的输入控件
- 预设值自动同步到输入控件
- 实时验证用户输入

### 2. 样式一致性
- 继承BasePopup的统一样式
- 支持主题色彩系统
- 响应式布局设计

### 3. 信号槽通信
- `captureSettingsSelected`: 设置选择信号
- `popupClosed`: 弹出框关闭信号
- 向父组件传递设置数据

### 4. 错误处理
- 输入值范围验证
- 格式错误自动修正
- 异常情况的优雅处理

## 扩展性

### 添加新的弹出框
1. 继承 `BasePopup` 类
2. 重写 `init_content()` 方法
3. 重写 `get_data()` 方法
4. 定义特定的信号
5. 在工具栏中集成

### 示例代码框架
```python
class NewPopup(BasePopup):
    # 定义信号
    dataSelected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent, "标题", 宽度, 高度)
        self.dataSelected.connect(self.specific_signal.emit)
    
    def init_content(self):
        # 添加具体的UI控件
        pass
    
    def get_data(self):
        # 返回具体的数据字典
        return {}
```

## 测试

提供了 `test_popups.py` 测试脚本，可以独立测试两个弹出框的功能：

```bash
python test_popups.py
```

## 文件结构

```
view/
├── dialogs.py                  # 弹出框模块（重构）
│   ├── BasePopup              # 基类
│   ├── ConnectEMPopup         # 连接电镜弹出框（重构）
│   └── ImageCapturePopup      # 图像采集弹出框（新建）
├── toolbar.py                 # 工具栏（已集成）
└── POPUP_DIALOGS_README.md    # 本说明文档

test_popups.py                 # 测试脚本
```

## 总结

通过采用面向对象的继承设计，实现了：
- ✅ 代码复用和模块化
- ✅ 统一的用户体验
- ✅ 易于维护和扩展
- ✅ 完整的功能覆盖
- ✅ 良好的性能表现

这个设计为将来添加更多弹出框（如自动聚焦、自动倾转设置）奠定了坚实的基础。
