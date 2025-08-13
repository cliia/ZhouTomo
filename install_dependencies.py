#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装依赖脚本
"""

import subprocess
import sys
import os

def install_package(package):
    """安装Python包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ 成功安装 {package}")
        return True
    except subprocess.CalledProcessError:
        print(f"✗ 安装 {package} 失败")
        return False

def main():
    """主函数"""
    print("正在安装ZhouTomo项目依赖...")
    print("=" * 50)
    
    # 需要安装的包
    packages = [
        "qasync>=0.24.0",
        "aiohttp>=3.8.0", 
        "websockets>=10.0",
        "PyQt5>=5.15.0"
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        print(f"正在安装 {package}...")
        if install_package(package):
            success_count += 1
        print()
    
    print("=" * 50)
    print(f"安装完成！成功安装 {success_count}/{total_count} 个包")
    
    if success_count == total_count:
        print("✓ 所有依赖已成功安装，可以运行项目了！")
    else:
        print("⚠ 部分依赖安装失败，请检查错误信息并手动安装")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()
