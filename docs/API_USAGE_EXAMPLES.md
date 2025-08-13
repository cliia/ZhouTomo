# ZhouTomo API 使用示例

本文档提供了ZhouTomo FastAPI服务器的详细使用示例，包括HTTP端点和WebSocket端点的使用方法。

## 1. 服务器启动

### 基本启动
```bash
# 本地模式（直接控制电镜）
python run_agent.py --mode local

# 模拟器模式（离线调试）
python run_agent.py --mode null

# 远程模式（连接远程temscript server）
python run_agent.py --mode remote --server-url http://remote-server:9000
```

### 开发模式
```bash
# 启用自动重载和调试日志
python run_agent.py --mode local --reload --log-level debug --port 9000
```

## 2. HTTP API 端点

### 2.1 系统信息

#### 健康检查
```bash
curl http://localhost:9000/health
```

响应示例：
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0",
  "microscope_connected": true,
  "uptime": 3600.5
}
```

#### 获取版本信息
```bash
curl http://localhost:8000/version
```

#### 获取系统信息
```bash
curl http://localhost:8000/info
```

### 2.2 显微镜状态管理

#### 获取完整状态快照
```bash
curl http://localhost:8000/snapshot
```

#### 获取可用组件列表
```bash
curl http://localhost:8000/components
```

#### 获取特定组件状态
```bash
# 获取载物台状态
curl http://localhost:8000/components/stage/state

# 获取相机状态
curl http://localhost:8000/components/camera/state

# 获取电子枪状态
curl http://localhost:8000/components/gun/state
```

#### 获取默认参数
```bash
curl http://localhost:8000/params
```

### 2.3 参数设置

#### 设置载物台参数
```bash
curl -X PATCH http://localhost:8000/components/stage/params \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "speed": 2.0,
      "acceleration": 1.5,
      "backlash_compensation": true
    }
  }'
```

#### 设置相机参数
```bash
curl -X PATCH http://localhost:8000/components/camera/params \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "exposure_time": 200.0,
      "gain": 1.5,
      "binning": 2
    }
  }'
```

#### 设置照明参数
```bash
curl -X PATCH http://localhost:8000/components/illumination/params \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "spot_size": 3,
      "intensity": 50.0,
      "condenser_aperture": 2
    }
  }'
```

### 2.4 命令执行

#### 移动载物台
```bash
curl -X POST http://localhost:8000/components/stage/commands/move_to \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "x": 100.0,
      "y": 200.0,
      "z": 50.0,
      "alpha": 0.0,
      "beta": 0.0
    }
  }'
```

#### 切换工作模式
```bash
curl -X POST http://localhost:8000/components/mode/commands/switch_mode \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "target_mode": "stem"
    }
  }'
```

#### 开启/关闭电子枪
```bash
# 开启电子枪
curl -X POST http://localhost:8000/components/gun/commands/power_on

# 关闭电子枪
curl -X POST http://localhost:8000/components/gun/commands/power_off
```

#### 控制束流遮挡
```bash
# 遮挡束流
curl -X POST http://localhost:8000/components/blanker/commands/blank

# 取消遮挡
curl -X POST http://localhost:8000/components/blanker/commands/unblank
```

### 2.5 图像采集控制

#### 开始采集
```bash
curl -X POST http://localhost:8000/acquisition/start
```

#### 停止采集
```bash
curl -X POST http://localhost:8000/acquisition/stop
```

#### 获取采集状态
```bash
curl http://localhost:8000/acquisition/status
```

## 3. WebSocket 图像流

### 3.1 基本连接

使用Python客户端连接WebSocket：

```python
import asyncio
import websockets
import json

async def connect_to_frame_stream():
    uri = "ws://localhost:8000/ws/frames"
    
    async with websockets.connect(uri) as websocket:
        print("已连接到图像流")
        
        # 发送心跳
        await websocket.send(json.dumps({"type": "ping"}))
        
        # 接收图像数据
        async for message in websocket:
            data = json.loads(message)
            
            if data["type"] == "frame":
                print(f"收到图像帧: {data['data']['frame_id']}")
                print(f"时间戳: {data['data']['timestamp']}")
                print(f"元数据: {data['data']['metadata']}")
            elif data["type"] == "pong":
                print("收到心跳响应")
            elif data["type"] == "connection":
                print(f"连接确认: {data['message']}")

# 运行客户端
asyncio.run(connect_to_frame_stream())
```

### 3.2 控制帧间隔

```python
import asyncio
import websockets
import json

async def control_frame_interval():
    uri = "ws://localhost:8000/ws/frames"
    
    async with websockets.connect(uri) as websocket:
        # 设置帧间隔为2秒
        await websocket.send(json.dumps({
            "type": "control",
            "command": "set_frame_interval",
            "interval": 2.0
        }))
        
        # 接收响应
        response = await websocket.recv()
        data = json.loads(response)
        print(f"控制响应: {data}")

asyncio.run(control_frame_interval())
```

### 3.3 JavaScript客户端示例

```javascript
// 连接WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/frames');

ws.onopen = function() {
    console.log('已连接到图像流');
    
    // 发送心跳
    setInterval(() => {
        ws.send(JSON.stringify({type: 'ping'}));
    }, 30000);
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'frame':
            console.log('收到图像帧:', data.data.frame_id);
            // 处理图像数据
            handleFrame(data.data);
            break;
            
        case 'pong':
            console.log('心跳响应');
            break;
            
        case 'connection':
            console.log('连接确认:', data.message);
            break;
            
        default:
            console.log('未知消息类型:', data.type);
    }
};

ws.onerror = function(error) {
    console.error('WebSocket错误:', error);
};

ws.onclose = function() {
    console.log('WebSocket连接已关闭');
};

function handleFrame(frameData) {
    // 处理图像帧数据
    console.log('处理帧:', frameData.frame_id);
    console.log('元数据:', frameData.metadata);
}
```

## 4. 错误处理

### 4.1 HTTP错误响应

所有API端点都返回标准的HTTP状态码和错误信息：

```json
{
  "error": "ValidationError",
  "message": "Invalid parameter value",
  "timestamp": "2024-01-15T10:30:00",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 4.2 常见错误码

- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 组件或端点不存在
- `422 Unprocessable Entity`: 参数验证失败
- `500 Internal Server Error`: 服务器内部错误
- `503 Service Unavailable`: 显微镜未连接

## 5. 性能优化建议

### 5.1 状态查询

- 使用 `/snapshot` 端点一次性获取所有状态，避免多次请求
- 对于实时性要求不高的数据，考虑缓存机制

### 5.2 图像流

- 根据网络条件调整帧间隔
- 考虑图像压缩和格式优化
- 实现客户端缓冲机制

### 5.3 错误处理

- 实现指数退避重试机制
- 记录详细的错误日志
- 提供用户友好的错误信息

## 6. 安全考虑

### 6.1 生产环境配置

```bash
# 限制CORS来源
# 在server_fastapi.py中修改CORS配置

# 添加身份验证
# 实现API密钥或JWT认证

# 启用HTTPS
# 使用反向代理（如Nginx）
```

### 6.2 网络安全

- 限制服务器绑定地址
- 配置防火墙规则
- 监控异常访问模式

## 7. 监控和日志

### 7.1 日志配置

```bash
# 启动时指定日志级别
python run_agent.py --mode local --log-level debug

# 日志文件位置
logs/agent.log
```

### 7.2 健康监控

```bash
# 定期检查服务状态
curl http://localhost:8000/health

# 监控关键指标
curl http://localhost:8000/info
```

## 8. 故障排除

### 8.1 常见问题

1. **显微镜连接失败**
   - 检查temscript安装
   - 验证硬件连接
   - 查看错误日志

2. **WebSocket连接断开**
   - 检查网络稳定性
   - 实现自动重连机制
   - 调整心跳间隔

3. **性能问题**
   - 监控CPU和内存使用
   - 优化图像处理流程
   - 调整并发连接数

### 8.2 调试技巧

```bash
# 启用详细日志
python run_agent.py --mode local --log-level debug

# 使用开发模式（自动重载）
python run_agent.py --mode local --reload

# 检查端口占用
netstat -an | grep 8000
```

## 9. 扩展开发

### 9.1 添加新的API端点

参考现有端点实现，在 `server_fastapi.py` 中添加新的路由。

### 9.2 自定义中间件

在 `server_fastapi.py` 中添加自定义中间件处理特定需求。

### 9.3 集成第三方服务

在 `ServerState` 类中添加对其他服务的集成支持。
