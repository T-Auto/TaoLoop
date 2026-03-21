#!/usr/bin/env python3
"""
简化的物理实验测试程序
运行90秒，每隔10秒输出一次清晰的日志
"""

import time
import sys
from datetime import datetime

def run_experiment():
    """运行90秒的实验，每10秒输出日志"""
    print("=" * 50)
    print("CLI工具测试：物理实验模拟")
    print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    total_time = 90  # 总运行时间：90秒
    interval = 10    # 日志间隔：10秒
    start = time.time()
    
    print(f"[INFO] 实验将运行 {total_time} 秒")
    print(f"[INFO] 每 {interval} 秒输出一次日志")
    print()
    
    checkpoints = list(range(0, total_time + 1, interval))
    current_checkpoint = 0
    
    try:
        while True:
            elapsed = time.time() - start
            
            # 检查是否到达下一个检查点
            if current_checkpoint < len(checkpoints) and elapsed >= checkpoints[current_checkpoint]:
                progress = (elapsed / total_time) * 100
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 进度: {progress:.1f}% ({elapsed:.1f}s/{total_time}s)")
                print(f"  检查点: {checkpoints[current_checkpoint]}秒")
                print(f"  系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                print()
                current_checkpoint += 1
            
            # 检查是否完成
            if elapsed >= total_time:
                print("=" * 50)
                print("实验完成！")
                print(f"实际运行时间: {elapsed:.2f} 秒")
                print(f"结束时间: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 50)
                return 0
            
            # 短暂休眠
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n[WARN] 实验被中断，已运行 {elapsed:.1f} 秒")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        return 2

if __name__ == "__main__":
    print(f"Python版本: {sys.version}")
    print("开始测试CLI工具...")
    result = run_experiment()
    sys.exit(result)