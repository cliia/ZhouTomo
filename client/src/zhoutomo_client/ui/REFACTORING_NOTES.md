# 工具栏重构说明

## 重构目标
将原本杂糅在 `main_window.py` 中的工具栏代码独立出来，提高代码的模块化和可维护性。

## 重构内容

### 1. 新建文件：`view/toolbar.py`
- 创建了 `MainToolbar` 类，继承自 `QWidget`
- 包含所有工具栏相关的逻辑：
  - 工具栏UI创建和布局
  - 按钮事件处理
  - 弹出窗口管理
  - 信号发射机制

### 2. 修改文件：`view/main_window.py`
- 移除了原来的工具栏创建代码
- 简化了 `create_tool_bar()` 方法
- 添加了信号连接逻辑
- 保留了连接选择处理逻辑

## 主要改进

### 1. 职责分离
- **MainWindow**: 负责主窗口布局和整体控制
- **MainToolbar**: 专门负责工具栏功能

### 2. 信号通信
- 使用 PyQt 信号槽机制进行组件间通信
- `connectionSelected`: 连接选择信号
- `statusUpdate`: 状态更新信号

### 3. 代码复用
- 工具栏代码独立后可以在其他地方复用
- 更容易进行单元测试

## 使用方式

```python
# 在主窗口中使用工具栏
self.toolbar_widget = MainToolbar(self)

# 连接信号
self.toolbar_widget.connectionSelected.connect(self.on_connection_selected)
self.toolbar_widget.statusUpdate.connect(self.update_status)

# 添加到QToolBar
self.toolBar.addWidget(self.toolbar_widget)
```

## 文件结构
```
view/
├── main_window.py      # 主窗口 (重构后)
├── toolbar.py          # 工具栏 (新建)
├── widgets.py          # 自定义控件
├── dialogs.py          # 对话框
└── README.md          # 说明文档
```

## 注意事项
- 保持了原有的所有功能
- 信号连接确保了数据流的正确性
- 工具栏样式和行为与原来完全一致
