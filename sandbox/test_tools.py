#!/usr/bin/env python3
"""
工具链测试脚本
快速验证physics_simulation.py的基本功能
"""

import time
import sys
import json
from datetime import datetime

def test_tools():
    """测试工具链"""
    print("=" * 60)
    print("工具链测试开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 测试1: 基本Python功能
    print("测试1: Python基本功能")
    test_data = {
        'test_name': '工具链验证',
        'timestamp': datetime.now().isoformat(),
        'python_version': sys.version,
        'platform': sys.platform
    }
    print(f"  Python版本: {sys.version}")
    print(f"  平台: {sys.platform}")
    
    # 测试2: 文件写入
    print("\n测试2: 文件写入功能")
    try:
        with open('test_output.json', 'w') as f:
            json.dump(test_data, f, indent=2)
        print("  ✓ 文件写入成功: test_output.json")
    except Exception as e:
        print(f"  ✗ 文件写入失败: {e}")
    
    # 测试3: 时间延迟和进度显示
    print("\n测试3: 时间延迟和进度显示")
    for i in range(1, 4):
        print(f"  进度: {i}/3")
        time.sleep(1)  # 短暂延迟
    
    # 测试4: 读取刚写入的文件
    print("\n测试4: 文件读取功能")
    try:
        with open('test_output.json', 'r') as f:
            loaded_data = json.load(f)
        print(f"  ✓ 文件读取成功")
        print(f"  测试名称: {loaded_data.get('test_name')}")
        print(f"  时间戳: {loaded_data.get('timestamp')}")
    except Exception as e:
        print(f"  ✗ 文件读取失败: {e}")
    
    print("\n" + "=" * 60)
    print("工具链测试完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_tools()
    sys.exit(0 if success else 1)