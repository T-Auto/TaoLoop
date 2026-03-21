#!/usr/bin/env python3
"""
CLI工具测试程序
运行90秒，每隔10秒输出一次心跳日志
用于验证run_command等工具的正常工作
"""

import time
import sys
from datetime import datetime

def test_cli_tools():
    """测试CLI工具功能"""
    print("🔧 CLI工具测试开始")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  计划运行: 90秒")
    print(f"📊 日志间隔: 10秒")
    print("-" * 50)
    
    start_time = time.time()
    checkpoints = 0
    
    try:
        while True:
            elapsed = time.time() - start_time
            
            # 每10秒输出一次心跳
            if elapsed >= checkpoints * 10:
                checkpoints += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 心跳 #{checkpoints}")
                print(f"   运行时间: {elapsed:.1f}秒")
                print(f"   系统时间: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                print(f"   检查点: {checkpoints}/9")
                print("-" * 30)
            
            # 达到90秒后退出
            if elapsed >= 90:
                break
            
            # 短暂休眠
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return False
    
    # 测试完成
    final_time = time.time() - start_time
    print("=" * 50)
    print("✅ CLI工具测试完成")
    print(f"📅 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  实际运行: {final_time:.2f}秒")
    print(f"📊 心跳次数: {checkpoints}次")
    
    # 验证结果
    if final_time >= 85 and final_time <= 95:
        print(f"🎯 测试结果: 成功 (运行时间: {final_time:.1f}秒)")
        return True
    else:
        print(f"❌ 测试结果: 异常 (运行时间: {final_time:.1f}秒)")
        return False

if __name__ == "__main__":
    print("CLI工具测试程序 v1.0")
    print(f"Python: {sys.version}")
    print()
    
    success = test_cli_tools()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 所有测试通过!")
        print("CLI工具运行正常，可以处理长时间运行的任务")
    else:
        print("⚠️  测试未完全通过")
        print("可能需要检查CLI工具配置")
    
    sys.exit(0 if success else 1)