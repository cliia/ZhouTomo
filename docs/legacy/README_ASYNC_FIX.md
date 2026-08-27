# Asyncio事件循环问题解决方案

## 问题描述

在PyQt5中集成asyncio时，可能会遇到以下错误：

```
no running event loop
coroutine 'AgentClientManager.connect_microscope' was never awaited
```

这是因为PyQt5的主线程中没有运行中的asyncio事件循环。

## 解决方案

### 1. 使用qasync库

我们使用 `qasync` 库来解决这个问题，它专门为PyQt5和asyncio的集成而设计。

#### 安装qasync

```bash
pip install qasync
```

或者运行安装脚本：

```bash
python install_dependencies.py
```

### 2. 代码修改

#### 导入qasync

```python
import qasync
```

#### 创建事件循环

在MainWindow的 `__main__` 部分：

```python
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 创建qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()
    
    # 运行事件循环
    with loop:
        loop.run_forever()
```

#### 异步方法调用

使用 `asyncio.create_task()` 来运行异步方法：

```python
def on_connection_selected(self, connection_info):
    """处理连接选择"""
    if connection_info is None:
        self.status_bar.showMessage("连接失败：URL不能为空")
        return
    
    # 根据连接类型执行相应操作
    conn_type = connection_info["type"]
    try:
        if conn_type == "local":
            self.status_bar.showMessage("正在连接本地电镜...")
            # 使用qasync运行异步连接
            asyncio.create_task(self.agent_manager.connect_microscope("local"))
            
        elif conn_type == "remote":
            url = connection_info["url"]
            self.status_bar.showMessage(f"正在连接远程电镜: {url}")
            # 使用qasync运行异步连接
            asyncio.create_task(self.agent_manager.connect_microscope("remote", url))
            
        elif conn_type == "dummy":
            self.status_bar.showMessage("正在启动模拟模式...")
            # 使用qasync运行异步连接
            asyncio.create_task(self.agent_manager.connect_microscope("dummy"))
            
    except Exception as e:
        self.status_bar.showMessage(f"连接电镜时发生错误: {str(e)}")
        print(f"连接电镜时发生错误: {e}")
```

## 技术原理

### 1. qasync的工作原理

`qasync` 库创建了一个与PyQt5事件循环集成的asyncio事件循环：

- 将asyncio事件循环与PyQt5的事件循环合并
- 允许在PyQt5应用中运行异步代码
- 保持UI的响应性

### 2. 事件循环集成

```python
# 创建qasync事件循环
loop = qasync.QEventLoop(app)
asyncio.set_event_loop(loop)

# 运行事件循环
with loop:
    loop.run_forever()
```

### 3. 异步任务调度

使用 `asyncio.create_task()` 来调度异步任务：

```python
# 创建异步任务
asyncio.create_task(self.agent_manager.connect_microscope("remote", url))
```

## 使用方法

### 1. 安装依赖

```bash
# 方法1：使用pip直接安装
pip install qasync aiohttp websockets PyQt5

# 方法2：运行安装脚本
python install_dependencies.py
```

### 2. 运行应用

```bash
# 直接运行主窗口
python view/main_window.py

# 或者运行测试脚本
python test_agent_integration.py
```

### 3. 连接电镜

1. 启动应用程序
2. 点击工具栏的"连接电镜"按钮
3. 选择"远程电镜"模式
4. 输入服务器URL：`http://0.0.0.0:9000`
5. 点击连接

## 故障排除

### 1. 常见问题

#### qasync未安装
```
ModuleNotFoundError: No module named 'qasync'
```
**解决方案**：运行 `pip install qasync`

#### 事件循环错误
```
RuntimeError: There is no current event loop in thread
```
**解决方案**：确保在正确的位置创建事件循环

#### 异步方法未等待
```
RuntimeWarning: coroutine was never awaited
```
**解决方案**：使用 `asyncio.create_task()` 或 `await`

### 2. 调试方法

#### 检查事件循环状态
```python
import asyncio
print(f"当前事件循环: {asyncio.get_event_loop()}")
print(f"事件循环运行状态: {asyncio.get_event_loop().is_running()}")
```

#### 检查异步任务状态
```python
# 在异步方法中添加日志
async def connect_microscope(self, connection_type, server_url=None):
    print(f"开始连接电镜: {connection_type}")
    try:
        # ... 连接逻辑
        print("连接成功")
    except Exception as e:
        print(f"连接失败: {e}")
        raise
```

### 3. 性能优化

#### 避免阻塞操作
```python
# 错误：在主线程中等待异步操作
result = await self.agent_manager.connect_microscope("local")  # 这会阻塞UI

# 正确：使用create_task
asyncio.create_task(self.agent_manager.connect_microscope("local"))
```

#### 使用信号机制
```python
# 通过信号通知UI更新
self.connectionStatusChanged.emit(True)
```

## 最佳实践

### 1. 异步方法设计

- 所有网络通信都应该是异步的
- 使用信号机制通知UI更新
- 避免在异步方法中直接操作UI

### 2. 错误处理

- 在异步方法中捕获异常
- 通过信号发送错误信息
- 在UI中显示用户友好的错误消息

### 3. 资源管理

- 及时释放网络连接
- 使用上下文管理器管理资源
- 避免内存泄漏

## 扩展功能

### 1. 实时数据流

```python
async def subscribe_data_stream(self):
    """订阅数据流"""
    try:
        async for data in self.agent_client.stream_data():
            # 处理数据
            self.dataReceived.emit(data)
    except Exception as e:
        self.errorOccurred.emit(f"数据流订阅失败: {str(e)}")
```

### 2. 批量操作

```python
async def batch_operations(self, operations):
    """批量执行操作"""
    tasks = []
    for op in operations:
        task = asyncio.create_task(self.execute_operation(op))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## 总结

通过使用 `qasync` 库，我们成功解决了PyQt5中asyncio事件循环的问题：

1. **问题根源**：PyQt5主线程没有asyncio事件循环
2. **解决方案**：使用qasync集成两个事件循环
3. **实现方式**：创建QEventLoop并设置为asyncio事件循环
4. **使用方法**：通过asyncio.create_task()调度异步任务

现在您可以正常连接电镜并执行异步操作，而不会遇到事件循环相关的错误。
