"""
AgentClient使用示例

本文件展示了如何使用AgentClient类与远程显微镜代理服务器通信
"""

import asyncio
import logging
from agent_client import AgentClient, AgentClientError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_usage_example():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 创建客户端实例
    client = AgentClient("http://localhost:9000")
    
    try:
        # 连接服务器
        await client.connect()
        print("✓ 已连接到服务器")
        
        # 检查连接状态
        if await client.is_connected():
            print("✓ 服务器连接正常")
            
            # 获取服务器健康状态
            health = await client.get_health()
            print(f"✓ 服务器状态: {health['status']}")
            
            # 获取API版本
            version = await client.get_version()
            print(f"✓ API版本: {version['version']}")
            
            # 获取系统信息
            info = await client.get_info()
            print(f"✓ 系统信息: {info}")
            
        else:
            print("✗ 无法连接到服务器")
            
    except AgentClientError as e:
        print(f"✗ 客户端错误: {e}")
    except Exception as e:
        print(f"✗ 未知错误: {e}")
    finally:
        # 断开连接
        await client.disconnect()
        print("✓ 已断开连接")


async def microscope_control_example():
    """显微镜控制示例"""
    print("\n=== 显微镜控制示例 ===")
    
    async with AgentClient("http://localhost:9000") as client:
        try:
            # 获取显微镜状态快照
            snapshot = await client.get_snapshot()
            print(f"✓ 获取到显微镜状态，包含 {len(snapshot)} 个组件")
            
            # 获取可用组件列表
            components = await client.get_components()
            print(f"✓ 可用组件: {components['components']}")
            
            # 获取相机状态
            camera_state = await client.get_component_state("camera")
            print(f"✓ 相机状态: {camera_state}")
            
            # 获取参数配置
            params = await client.get_params()
            print(f"✓ 参数配置: {params}")
            
        except AgentClientError as e:
            print(f"✗ 控制错误: {e}")


async def parameter_setting_example():
    """参数设置示例"""
    print("\n=== 参数设置示例 ===")
    
    async with AgentClient("http://localhost:9000") as client:
        # 设置相机参数
        try:
            camera_params = {
                "exposure_time": 100.0,
                "gain": 1.5
            }
            result = await client.set_component_params("camera", camera_params)
            print(f"✓ 相机参数设置结果: {result}")
        except AgentClientError as e:
            print(f"✗ 相机参数设置错误: {e}")
            return
        
        # 执行相机命令
        try:
            command_result = await client.execute_command(
                "camera", 
                "capture", 
                {"format": "jpeg", "quality": 90}
            )
            print(f"✓ 相机命令执行结果: {command_result}")
        except AgentClientError as e:
            print(f"✗ 相机命令执行错误: {e}")


async def acquisition_control_example():
    """采集控制示例"""
    print("\n=== 采集控制示例 ===")
    
    async with AgentClient("http://localhost:9000") as client:
        try:
            # 获取采集状态
            status = await client.get_acquisition_status()
            print(f"✓ 当前采集状态: {status}")
            
            # 开始采集
            start_result = await client.start_acquisition()
            print(f"✓ 开始采集结果: {len(start_result)}")
            
            # 等待一段时间
            await asyncio.sleep(2)
            
            # 获取更新后的状态
            status = await client.get_acquisition_status()
            print(f"✓ 更新后的采集状态: {status}")
            
            # 停止采集
            stop_result = await client.stop_acquisition()
            print(f"✓ 停止采集结果: {stop_result}")
            
        except AgentClientError as e:
            print(f"✗ 采集控制错误: {e}")


async def websocket_streaming_example():
    """WebSocket流式数据示例"""
    print("\n=== WebSocket流式数据示例 ===")
    
    async with AgentClient("http://localhost:9000") as client:
        try:
            print("开始订阅图像帧流...")
            print("(按Ctrl+C停止)")
            
            # 订阅图像帧流
            frame_count = 0
            async for frame in client.stream_frames():
                frame_count += 1
                print(f"✓ 接收到第 {frame_count} 帧: {frame.get('frame_id', 'unknown')}")
                
                # 只接收5帧作为示例
                if frame_count >= 5:
                    break
                    
        except AgentClientError as e:
            print(f"✗ WebSocket错误: {e}")
        except KeyboardInterrupt:
            print("\n✓ 用户停止订阅")


async def error_handling_example():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    # 测试无效URL
    try:
        client = AgentClient("invalid_url")
        print("✗ 应该抛出异常")
    except ValueError as e:
        print(f"✓ 正确捕获无效URL错误: {e}")
    
    # 测试连接失败
    try:
        client = AgentClient("http://nonexistent-server:9999")
        await client.connect()
        print("✗ 应该抛出连接错误")
    except Exception as e:
        print(f"✓ 正确捕获连接错误: {e}")


async def performance_test_example():
    """性能测试示例"""
    print("\n=== 性能测试示例 ===")
    
    async with AgentClient("http://localhost:9000") as client:
        try:
            # 测试连接延迟
            latency = await client.ping()
            if latency >= 0:
                print(f"✓ 连接延迟: {latency:.2f}ms")
            else:
                print("✗ 无法测量延迟")
                
            # 测试批量操作
            import time
            start_time = time.time()
            
            # 并行执行多个请求
            tasks = [
                client.get_health(),
                client.get_version(),
                client.get_info()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            print(f"✓ 批量操作完成，耗时: {duration:.2f}ms")
            print(f"✓ 成功请求数: {len([r for r in results if not isinstance(r, Exception)])}")
            
        except Exception as e:
            print(f"✗ 性能测试错误: {e}")


async def main():
    """主函数"""
    print("ZhouTomo AgentClient 使用示例")
    print("=" * 50)
    
    # 运行所有示例
    examples = [
        basic_usage_example,
        microscope_control_example,
        parameter_setting_example,
        acquisition_control_example,
        websocket_streaming_example,
        error_handling_example,
        performance_test_example
    ]
    
    for example in examples:
        try:
            await example()
            print()  # 空行分隔
        except Exception as e:
            print(f"示例 {example.__name__} 执行失败: {e}")
            print()
    
    print("所有示例执行完成！")


if __name__ == "__main__":
    # 运行示例
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断执行")
    except Exception as e:
        print(f"执行失败: {e}")

