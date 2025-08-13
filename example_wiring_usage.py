"""
wiring.py 使用示例

本脚本展示了如何使用wiring.py模块来连接和控制显微镜。
"""

import logging
import time
from domain import MicroscopeParams, CameraParams, StageParams
from wiring import create_local_wiring, create_null_wiring

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_local_microscope():
    """本地显微镜使用示例"""
    print("=== 本地显微镜使用示例 ===")
    
    try:
        # 创建本地显微镜装配
        wiring = create_local_wiring()
        print(f"创建装配成功: {wiring.mode} 模式")
        
        # 获取装配信息
        info = wiring.get_info()
        print(f"装配信息: {info}")
        
        # 尝试连接（注意：这需要实际的temscript环境）
        print("尝试连接到本地显微镜...")
        if wiring.connect():
            print("连接成功！")
            
            # 获取状态快照
            snapshot = wiring.get_snapshot()
            if snapshot:
                print(f"获取快照成功，系统状态: {snapshot.system_status}")
            
            # 断开连接
            wiring.disconnect()
            print("已断开连接")
        else:
            print("连接失败（可能是temscript不可用）")
            
    except Exception as e:
        print(f"本地显微镜示例执行失败: {e}")


def example_null_microscope():
    """空显微镜（模拟器）使用示例"""
    print("\n=== 空显微镜使用示例 ===")
    
    try:
        # 创建空显微镜装配
        wiring = create_null_wiring()
        print(f"创建装配成功: {wiring.mode} 模式")
        
        # 获取装配信息
        info = wiring.get_info()
        print(f"装配信息: {info}")
        
        # 注意：空显微镜目前未实现，这里只是展示接口
        
    except Exception as e:
        print(f"空显微镜示例执行失败: {e}")


def example_parameter_manipulation():
    """参数操作示例"""
    print("\n=== 参数操作示例 ===")
    
    try:
        # 创建本地装配
        wiring = create_local_wiring()
        
        # 创建一些参数对象
        camera_params = CameraParams(
            exposure_time=500.0,  # 500ms
            gain=2.0,
            binning=2,
            frame_size=(2048, 2048)
        )
        
        stage_params = StageParams(
            speed=2.0,
            acceleration=1.5,
            backlash_compensation=True
        )
        
        print("创建参数对象成功:")
        print(f"  相机参数: 曝光时间={camera_params.exposure_time}ms, 增益={camera_params.gain}")
        print(f"  载物台参数: 速度={stage_params.speed}, 加速度={stage_params.acceleration}")
        
        # 注意：实际设置参数需要先连接显微镜
        
    except Exception as e:
        print(f"参数操作示例执行失败: {e}")


def example_command_execution():
    """命令执行示例"""
    print("\n=== 命令执行示例 ===")
    
    try:
        # 创建本地装配
        wiring = create_local_wiring()
        
        print("可执行的命令示例:")
        print("  1. 载物台移动: wiring.execute_command('stage', 'move_to', x=100, y=200)")
        print("  2. 相机采集: wiring.execute_command('camera', 'acquire')")
        print("  3. 开始采集: wiring.execute_command('acquisition', 'start')")
        print("  4. 停止采集: wiring.execute_command('acquisition', 'stop')")
        print("  5. 自动归一化: wiring.execute_command('auto_normalize', 'normalize')")
        
        # 注意：实际执行命令需要先连接显微镜
        
    except Exception as e:
        print(f"命令执行示例执行失败: {e}")


def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    try:
        # 尝试创建无效模式的装配
        from wiring import create_microscope_wiring
        
        try:
            invalid_wiring = create_microscope_wiring("invalid_mode")
        except Exception as e:
            print(f"预期的错误: {type(e).__name__}: {e}")
        
        # 尝试在未连接状态下执行操作
        wiring = create_local_wiring()
        
        # 获取快照（应该失败）
        snapshot = wiring.get_snapshot()
        if snapshot is None:
            print("预期的行为: 未连接状态下获取快照返回None")
        
        # 设置参数（应该失败）
        result = wiring.set_component_params("camera", CameraParams())
        if not result:
            print("预期的行为: 未连接状态下设置参数返回False")
            
    except Exception as e:
        print(f"错误处理示例执行失败: {e}")


def main():
    """主函数"""
    print("开始 wiring.py 使用示例...\n")
    
    try:
        # 运行各种示例
        example_local_microscope()
        example_null_microscope()
        example_parameter_manipulation()
        example_command_execution()
        example_error_handling()
        
        print("\n所有示例执行完成！")
        
    except Exception as e:
        print(f"示例执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
