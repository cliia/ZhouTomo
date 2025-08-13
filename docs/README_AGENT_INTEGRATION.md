# AgentClient集成功能说明

## 功能概述

本项目已成功集成AgentClient，实现了与电镜代理服务器的通信功能，包括：

1. **电镜连接管理**：支持本地、远程和模拟三种连接模式
2. **状态信息获取**：实时获取电镜状态快照和组件信息
3. **图像采集控制**：通过AgentClient控制电镜进行图像采集
4. **异步通信处理**：使用asyncio处理异步通信，避免阻塞UI

## 架构设计

### 1. 核心组件

#### AgentClientManager类
- 管理AgentClient实例的生命周期
- 处理与电镜代理服务器的所有通信
- 提供统一的接口供UI层调用

#### MainWindow类
- 集成AgentClientManager
- 处理用户界面交互
- 显示电镜状态和图像信息

### 2. 通信流程

```
用户操作 → UI事件 → AgentClientManager → AgentClient → 电镜代理服务器
                ↓
            状态更新 → UI显示更新
```

## 使用方法

### 1. 连接电镜

#### 本地连接
1. 点击工具栏的"连接电镜"按钮
2. 选择"本地电镜"选项
3. 系统自动连接到 `http://localhost:9000`

#### 远程连接
1. 点击工具栏的"连接电镜"按钮
2. 选择"远程电镜"选项
3. 输入远程服务器URL
4. 系统连接到指定的远程服务器

#### 模拟模式
1. 点击工具栏的"连接电镜"按钮
2. 选择"模拟模式"选项
3. 系统启动模拟电镜服务

### 2. 图像采集

1. 确保电镜已连接
2. 点击工具栏的"图像采集"按钮
3. 系统通过AgentClient启动图像采集
4. 采集到的图像显示在主窗口中央

### 3. 状态监控

- 右侧信息面板显示电镜连接状态
- 状态栏显示操作进度和错误信息
- 实时更新电镜组件状态

## 技术实现

### 1. 异步通信

使用Python的asyncio库处理异步通信：

```python
async def connect_microscope(self, connection_type, server_url=None):
    """连接电镜"""
    try:
        # 创建AgentClient实例
        self.agent_client = AgentClient(self.server_url)
        
        # 异步连接服务器
        await self.agent_client.connect()
        
        # 检查连接状态
        if await self.agent_client.is_connected():
            self.is_connected = True
            self.connectionStatusChanged.emit(True)
            return True
    except Exception as e:
        self.errorOccurred.emit(f"连接电镜失败: {str(e)}")
        return False
```

### 2. 信号机制

使用PyQt5的信号机制实现组件间通信：

```python
class AgentClientManager(QObject):
    # 定义信号
    connectionStatusChanged = pyqtSignal(bool)  # 连接状态变化信号
    snapshotUpdated = pyqtSignal(dict)         # 状态快照更新信号
    acquisitionProgress = pyqtSignal(int, int) # 采集进度信号
    acquisitionCompleted = pyqtSignal()        # 采集完成信号
    acquisitionError = pyqtSignal(str)         # 采集错误信号
```

### 3. 错误处理

完善的错误处理机制：

```python
try:
    if not self.agent_client or not self.is_connected:
        raise Exception("电镜未连接")
    
    result = await self.agent_client.start_acquisition()
    return result
except Exception as e:
    self.acquisitionError.emit(f"开始图像采集失败: {str(e)}")
    return None
```

## 配置说明

### 1. 服务器配置

- **本地模式**：默认连接到 `http://localhost:9000`
- **远程模式**：用户指定的服务器URL
- **模拟模式**：使用模拟服务器进行测试

### 2. 连接参数

- **超时时间**：30秒（可在AgentClient中配置）
- **重试次数**：3次（可在AgentClient中配置）
- **心跳检测**：支持WebSocket心跳检测

## 测试验证

### 1. 运行测试脚本

```bash
# 测试AgentClient集成
python test_agent_integration.py

# 测试图像显示功能
python test_image_display.py
```

### 2. 功能验证清单

- [ ] 电镜连接功能正常
- [ ] 状态信息获取正常
- [ ] 图像采集功能正常
- [ ] 错误处理机制正常
- [ ] UI响应正常

## 扩展功能

### 1. 实时图像流

可以扩展实现实时图像流显示：

```python
async def subscribe_image_stream(self):
    """订阅图像流"""
    try:
        async for frame in self.agent_client.stream_frames():
            # 处理图像帧
            self.process_image_frame(frame)
    except Exception as e:
        self.errorOccurred.emit(f"图像流订阅失败: {str(e)}")
```

### 2. 参数设置

扩展电镜参数设置功能：

```python
async def set_microscope_params(self, component, params):
    """设置电镜参数"""
    try:
        result = await self.agent_client.set_params(component, params)
        return result
    except Exception as e:
        self.errorOccurred.emit(f"参数设置失败: {str(e)}")
        return None
```

### 3. 命令执行

扩展电镜命令执行功能：

```python
async def execute_microscope_command(self, component, command, parameters=None):
    """执行电镜命令"""
    try:
        result = await self.agent_client.execute_command(component, command, parameters)
        return result
    except Exception as e:
        self.errorOccurred.emit(f"命令执行失败: {str(e)}")
        return None
```

## 故障排除

### 1. 常见问题

#### 连接失败
- 检查服务器是否运行
- 验证服务器URL是否正确
- 检查网络连接状态

#### 图像采集失败
- 确认电镜已连接
- 检查电镜状态是否正常
- 查看错误日志信息

#### UI无响应
- 检查异步任务是否正常执行
- 验证信号连接是否正确
- 检查主线程是否阻塞

### 2. 调试方法

1. **启用详细日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查连接状态**
   ```python
   print(f"连接状态: {window.agent_manager.is_connected}")
   print(f"服务器URL: {window.agent_manager.server_url}")
   ```

3. **测试网络连接**
   ```python
   import requests
   response = requests.get("http://localhost:9000/health")
   print(f"服务器响应: {response.status_code}")
   ```

## 性能优化

### 1. 连接池管理

对于高并发场景，可以实现连接池：

```python
class ConnectionPool:
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.connections = []
    
    async def get_connection(self):
        # 获取可用连接
        pass
    
    async def release_connection(self, connection):
        # 释放连接
        pass
```

### 2. 缓存机制

实现状态信息缓存：

```python
class StateCache:
    def __init__(self, cache_timeout=5.0):
        self.cache_timeout = cache_timeout
        self.cached_data = {}
    
    def get_cached_state(self, key):
        # 获取缓存的状态信息
        pass
    
    def update_cache(self, key, data):
        # 更新缓存
        pass
```

## 安全考虑

### 1. 认证机制

- 支持API密钥认证
- 支持用户身份验证
- 支持访问权限控制

### 2. 数据加密

- 支持HTTPS/WSS加密通信
- 支持敏感数据加密存储
- 支持通信数据完整性验证

## 更新日志

- **v2.0**: 移除microscope_manager依赖
- **v2.1**: 集成AgentClient通信功能
- **v2.2**: 实现异步通信处理
- **v2.3**: 完善错误处理和状态管理
- **v2.4**: 添加实时状态监控功能

## 注意事项

1. **异步操作**：所有网络通信都是异步的，避免阻塞UI线程
2. **错误处理**：网络通信可能失败，需要完善的错误处理机制
3. **状态同步**：保持UI状态与服务器状态的同步
4. **资源管理**：及时释放网络连接和资源
5. **用户体验**：提供清晰的状态反馈和错误提示
