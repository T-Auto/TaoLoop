#!/usr/bin/env python3
"""
模拟物理实验的Python程序
运行90秒，每隔10秒输出一次日志
用于测试CLI工具功能
"""

import time
import random
import sys
from datetime import datetime

def simulate_physics_experiment():
    """
    模拟物理实验：粒子碰撞模拟
    """
    print("=" * 60)
    print("物理实验模拟开始：粒子碰撞仿真")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 实验参数
    total_duration = 90  # 总运行时间：90秒
    log_interval = 10    # 日志间隔：10秒
    num_particles = 1000  # 模拟粒子数量
    
    # 初始化实验状态
    start_time = time.time()
    elapsed_time = 0
    iteration = 0
    
    # 模拟物理量
    temperature = 300.0  # 开尔文
    pressure = 1.0       # 大气压
    energy = 0.0         # 总能量
    collisions = 0       # 碰撞次数
    
    print(f"[初始化] 粒子数量: {num_particles}")
    print(f"[初始化] 初始温度: {temperature:.2f} K")
    print(f"[初始化] 初始压力: {pressure:.2f} atm")
    print()
    
    try:
        while elapsed_time < total_duration:
            iteration += 1
            
            # 模拟物理过程
            time_since_start = time.time() - start_time
            
            # 更新物理量（模拟物理过程）
            temperature += random.uniform(-0.5, 0.5)
            pressure += random.uniform(-0.01, 0.01)
            energy += random.uniform(0, 10)
            collisions += random.randint(50, 150)
            
            # 每10秒输出一次详细日志
            if time_since_start >= iteration * log_interval:
                # 计算实验进度
                progress = (time_since_start / total_duration) * 100
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 实验进度: {progress:.1f}%")
                print(f"  运行时间: {time_since_start:.1f}s / {total_duration}s")
                print(f"  当前温度: {temperature:.2f} K")
                print(f"  当前压力: {pressure:.3f} atm")
                print(f"  总能量: {energy:.1f} J")
                print(f"  碰撞次数: {collisions}")
                print(f"  迭代次数: {iteration}")
                
                # 模拟一些实验事件
                if random.random() < 0.3:
                    event_type = random.choice(["粒子注入", "能量波动", "压力调节", "温度稳定"])
                    print(f"  ⚡ 实验事件: {event_type}")
                
                print()
            
            # 短暂休眠以避免CPU占用过高
            time.sleep(0.1)
            
            # 更新已用时间
            elapsed_time = time.time() - start_time
        
        # 实验结束
        print("=" * 60)
        print("物理实验模拟完成")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总运行时间: {elapsed_time:.2f} 秒")
        print(f"最终温度: {temperature:.2f} K")
        print(f"最终压力: {pressure:.3f} atm")
        print(f"总能量积累: {energy:.1f} J")
        print(f"总碰撞次数: {collisions}")
        print(f"总迭代次数: {iteration}")
        print("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n[警告] 实验被用户中断")
        print(f"实验运行了 {elapsed_time:.2f} 秒")
        return 1
    except Exception as e:
        print(f"\n[错误] 实验发生异常: {e}")
        return 2

if __name__ == "__main__":
    print("Python版本:", sys.version)
    print("程序开始执行...")
    exit_code = simulate_physics_experiment()
    sys.exit(exit_code)