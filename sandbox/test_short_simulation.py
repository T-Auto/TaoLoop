#!/usr/bin/env python3
"""
简短的测试版本，运行10秒
"""

import time
import sys
from datetime import datetime

def test_simulation():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始测试仿真")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 将运行10秒，每2秒输出一次")
    
    start_time = time.time()
    last_log = start_time
    
    try:
        for i in range(100):  # 最多100次循环
            current_time = time.time()
            elapsed = current_time - start_time
            
            if elapsed >= 10:  # 10秒后停止
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 测试完成，运行了 {elapsed:.1f} 秒")
                break
            
            if current_time - last_log >= 2:  # 每2秒输出
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 测试进度: {elapsed:.1f}/10 秒, 迭代 {i}")
                last_log = current_time
            
            # 模拟一些计算
            result = sum([x*x for x in range(1000)])
            time.sleep(0.1)  # 短暂休眠
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 测试被中断")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 测试结束")

if __name__ == "__main__":
    test_simulation()