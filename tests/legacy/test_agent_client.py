import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import logging

from agent_client import AgentClient, AgentClientError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            print(f"✓ 开始采集结果: {start_result}")
            
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


if __name__ == "__main__":
    asyncio.run(microscope_control_example())
    asyncio.run(acquisition_control_example())
    asyncio.run(websocket_streaming_example())
