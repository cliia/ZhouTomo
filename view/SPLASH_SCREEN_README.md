# 启动画面功能说明

## 功能概述
实现了类似Microsoft Word的启动画面效果，在程序初始化期间显示欢迎界面。

## 主要特性

### 1. 视觉效果
- 使用 `resources/background/startup_background.jpg` 作为背景图片
- 半透明遮罩层，确保文字清晰可读
- 圆角进度条，实时显示加载进度
- 应用程序标题和版本信息显示
- 抗锯齿渲染，界面美观流畅

### 2. 进度模拟
启动画面模拟以下初始化步骤：
- 正在加载配置文件... (10%)
- 正在初始化资源管理器... (25%)
- 正在加载图标资源... (40%)
- 正在创建用户界面... (55%)
- 正在初始化工具栏... (70%)
- 正在配置菜单系统... (85%)
- 正在完成初始化... (95%)
- 启动完成! (100%)

### 3. 时间控制
- **最小显示时间**: 3秒（确保用户能看到启动画面）
- **进度更新频率**: 每100ms更新一次
- **平滑过渡**: 使用信号槽机制确保流畅切换到主窗口

## 文件结构

```
view/
├── splash_screen.py    # 启动画面组件
└── main_window.py      # 主窗口（已修改）

main.py                 # 主入口（已重构）

resources/
└── background/
    └── startup_background.jpg  # 启动背景图片
```

## 使用方式

### 正常启动
```bash
python main.py
```

### 开发调试（跳过启动画面）
```bash
python view/main_window.py
```

## 技术实现

### 1. SplashScreen 类
- 继承自 `QSplashScreen`
- 自定义绘制方法 `drawContents()`
- 信号槽机制控制初始化流程

### 2. 主要方法
- `load_background_image()`: 加载和处理背景图片
- `start_initialization()`: 启动初始化流程
- `update_progress()`: 更新进度和状态
- `finish_splash()`: 完成启动画面

### 3. 信号定义
- `progressUpdated`: 进度更新信号
- `initializationComplete`: 初始化完成信号

## 自定义选项

### 修改显示时间
在 `splash_screen.py` 中修改：
```python
self.min_display_time = 3000  # 毫秒
```

### 修改进度步骤
在 `start_initialization()` 方法中修改 `init_steps` 列表。

### 修改背景图片
1. 替换 `resources/background/startup_background.jpg`
2. 或在创建 SplashScreen 时指定路径：
```python
splash = SplashScreen("/path/to/your/image.jpg")
```

## 故障排除

### 背景图片不显示
- 检查图片路径是否正确
- 确保图片格式支持（JPG, PNG等）
- 如果图片缺失，会显示默认的深色背景

### 启动画面不显示
- 检查PyQt5安装是否完整
- 确保main.py正确导入了splash_screen模块

### 进度更新异常
- 检查QTimer是否正常工作
- 确保信号槽连接正确
