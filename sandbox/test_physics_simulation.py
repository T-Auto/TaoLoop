#!/usr/bin/env python3
"""
简化的物理仿真测试程序
运行30秒，每5秒输出一次日志
用于快速测试
"""

import time
import sys
import random
import psutil
import json
from datetime import datetime

def get_system_info():
    """获取系统硬件信息"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_gb': memory.used / (1024**3),
            'memory_total_gb': memory.total / (1024**3),
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    """主函数"""
    print("=" * 60)
    print("物理仿真测试开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    total_duration = 30  # 总运行时间：30秒
    log_interval = 5     # 日志间隔：5秒
    total_iterations = total_duration // log_interval
    
    print(f"测试配置:")
    print(f"  - 总运行时间: {total_duration} 秒")
    print(f"  - 日志间隔: {log_interval} 秒")
    print(f"  - 总迭代次数: {total_iterations}")
    print()
    
    try:
        for iteration in range(1, total_iterations + 1):
            # 获取系统信息
            system_info = get_system_info()
            
            # 输出日志
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代 {iteration}/{total_iterations}")
            print(f"  系统状态: CPU={system_info.get('cpu_percent', 'N/A')}%, "
                  f"内存={system_info.get('memory_percent', 'N/A')}%")
            print(f"  进度: {round((iteration / total_iterations) * 100, 1)}%")
            print("-" * 40)
            
            # 等待下一个日志间隔（最后迭代不等待）
            if iteration < total_iterations:
                time.sleep(log_interval)
                
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试发生错误: {e}")
    finally:
        print("=" * 60)
        print("物理仿真测试结束")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

if __name__ == "__main__":
    main()