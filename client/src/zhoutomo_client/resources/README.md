# 资源文件说明

## 图标文件命名规则

### 电镜控制功能图标

请将以下四个图标文件放置在 `resources/icons/` 目录下：

| 功能 | 文件名 | 说明 |
|------|--------|------|
| 连接电镜 | `connect_em.png` | 电镜连接图标 |
| 图像采集 | `image_capture.png` | 图像采集图标 |
| 自动聚焦 | `auto_focus.png` | 自动聚焦图标 |
| 自动倾转 | `auto_tilt.png` | 自动倾转图标 |

### 支持的图标格式

- PNG (.png) - 推荐，支持透明背景
- JPEG (.jpg, .jpeg)
- BMP (.bmp)
- GIF (.gif)
- ICO (.ico)
- SVG (.svg) - 矢量图标

### 推荐的图标规格

- **尺寸**: 64x64 像素或更高分辨率
- **格式**: PNG格式，透明背景
- **风格**: 简洁明了，线条清晰
- **颜色**: 单色或双色设计，避免过于复杂的颜色

### 目录结构

```
ZhouTomo_v2/
├── resources/
│   ├── icons/
│   │   ├── connect_em.png      # 连接电镜图标
│   │   ├── image_capture.png   # 图像采集图标
│   │   ├── auto_focus.png      # 自动聚焦图标
│   │   └── auto_tilt.png       # 自动倾转图标
│   ├── resource_manager.py     # 资源管理器
│   └── README.md              # 本说明文件
├── view/
│   └── main_window.py         # 主窗口
└── main.py                    # 程序入口
```

### 使用说明

1. 将图标文件按照上述命名规则放入 `resources/icons/` 目录
2. 程序会自动加载对应的图标文件
3. 如果找不到图标文件，按钮将只显示文字
4. 图标会自动缩放到64x64像素大小

### 添加新图标

如果需要添加新的图标：

1. 将图标文件放入 `resources/icons/` 目录
2. 在代码中使用 `resource_manager.get_icon('图标名', QSize(64, 64))` 加载
3. 图标名不需要包含文件扩展名

## 注意事项

- 确保图标文件名与代码中的引用名称完全一致
- 建议使用PNG格式的透明背景图标以获得最佳视觉效果
- 图标应该具有良好的可识别性，在小尺寸下也能清晰显示
