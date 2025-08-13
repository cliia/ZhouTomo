# 自定义水平SpinBox组件

## 概述
根据用户需求，创建了自定义的水平布局SpinBox组件，实现了左右按钮布局和鼠标拖拽功能。

## 新功能特性

### 1. 水平按钮布局
- **左侧按钮显示 "-" 符号**：点击减少数值
- **右侧按钮显示 "+" 符号**：点击增加数值
- **中间为数值显示/输入区域**：可直接点击输入

### 2. 鼠标拖拽调整
- **水平拖拽**：在中间数值区域按住鼠标左右拖拽
- **实时调整**：拖拽过程中数值实时变化
- **范围限制**：自动限制在设定的最小值和最大值范围内
- **灵敏度控制**：可调整拖拽灵敏度

### 3. 视觉反馈
- **鼠标悬停**：按钮区域悬停时高亮显示
- **光标变化**：在可拖拽区域显示水平调整光标(⟷)
- **按钮动画**：点击按钮时有按下效果

## 组件类型

### HorizontalSpinBox
用于整数数值输入：
- 继承自 `QSpinBox`
- 支持整数范围设置
- 适用于：亮度、对比度、分辨率、合并度等

### HorizontalDoubleSpinBox  
用于浮点数数值输入：
- 继承自 `QDoubleSpinBox`
- 支持小数精度设置
- 适用于：驻留时间等精确数值

## 技术实现

### 样式自定义
```python
def get_horizontal_style(self):
    """获取水平布局样式"""
    return f"""
        QSpinBox {{
            padding: 2px 30px 2px 30px;  # 为左右按钮留出空间
            # ... 其他样式
        }}
        QSpinBox::up-button {{
            subcontrol-position: center right;  # 右侧位置
            # ... 按钮样式
        }}
        QSpinBox::down-button {{
            subcontrol-position: center left;   # 左侧位置
            # ... 按钮样式
        }}
    """
```

### 符号绘制
```python
def paintEvent(self, event):
    """重写绘制事件，绘制+和-符号"""
    super().paintEvent(event)
    
    painter = QPainter(self)
    # 绘制左侧减号 (-)
    # 绘制右侧加号 (+)
```

### 拖拽功能
```python
def mousePressEvent(self, event):
    """检测点击位置，启动拖拽"""
    
def mouseMoveEvent(self, event):
    """计算拖拽距离，更新数值"""
    
def mouseReleaseEvent(self, event):
    """结束拖拽"""
```

## 使用方式

### 在弹出框中集成
已经在 `ImageCapturePopup` 中替换了所有标准SpinBox：

```python
# 原来的代码
self.brightness_spinbox = QSpinBox()

# 现在的代码  
self.brightness_spinbox = HorizontalSpinBox()
```

### 直接使用
```python
from view.custom_widgets import HorizontalSpinBox, HorizontalDoubleSpinBox

# 创建整数SpinBox
int_spinner = HorizontalSpinBox()
int_spinner.setRange(0, 100)
int_spinner.setValue(50)
int_spinner.setSuffix("%")

# 创建浮点数SpinBox
float_spinner = HorizontalDoubleSpinBox()
float_spinner.setRange(0.1, 1000.0)
float_spinner.setValue(10.0)
float_spinner.setSuffix(" μs")
float_spinner.setDecimals(1)
```

## 配置选项

### 拖拽灵敏度
```python
# 整数SpinBox（默认值：2）
spinbox.drag_sensitivity = 2  # 拖拽2像素改变1个数值

# 浮点数SpinBox（默认值：5）
spinbox.drag_sensitivity = 5  # 需要更大的灵敏度
```

### 步长设置
```python
# 整数SpinBox
spinbox.setSingleStep(1)  # 每次点击增减1

# 浮点数SpinBox
spinbox.setSingleStep(0.1)  # 每次点击增减0.1
```

## 用户交互

### 三种操作方式

1. **点击按钮**
   - 点击左侧 "-" 按钮：数值减少
   - 点击右侧 "+" 按钮：数值增加

2. **鼠标拖拽**
   - 在中间数值区域按住鼠标
   - 左右拖拽调整数值
   - 光标会变为水平调整样式(⟷)

3. **直接输入**
   - 点击数值区域
   - 直接输入新的数值
   - 按回车确认

### 视觉提示

- **可拖拽区域**：鼠标悬停时光标变为 ⟷
- **按钮区域**：鼠标悬停时背景高亮
- **拖拽中**：整个控件保持水平光标
- **按钮点击**：显示按下效果

## 测试

提供了独立测试脚本：
```bash
python test_horizontal_spinbox.py
```

可以测试：
- 不同类型的SpinBox
- 所有交互方式
- 样式效果

## 兼容性

- **向下兼容**：如果自定义控件加载失败，自动回退到标准QSpinBox
- **功能保持**：所有标准SpinBox的功能都保留
- **样式一致**：与整体UI风格保持一致

## 文件结构

```
view/
├── custom_widgets.py              # 自定义控件模块
│   ├── HorizontalSpinBox          # 水平整数SpinBox
│   └── HorizontalDoubleSpinBox    # 水平浮点数SpinBox
├── dialogs.py                     # 弹出框（已集成）
└── CUSTOM_SPINBOX_README.md       # 本说明文档

test_horizontal_spinbox.py         # 测试脚本
```

## 总结

通过自定义SpinBox组件，实现了：
- ✅ 左右按钮布局（- 和 +）
- ✅ 鼠标拖拽数值调整
- ✅ 保持所有原有功能
- ✅ 统一的UI风格
- ✅ 良好的用户体验
- ✅ 向下兼容性

这个设计大大提升了数值输入的便利性和用户体验，特别适合需要频繁调整参数的图像采集界面。
