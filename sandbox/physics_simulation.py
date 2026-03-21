#!/usr/bin/env python3
"""
模拟物理实验的Python程序
运行90秒，每隔10秒输出一次日志
用于测试CLI工具功能
"""

import time
import sys
import random
from datetime import datetime

def simulate_physics_experiment():
    """
    模拟物理实验：粒子碰撞仿真
    """
    print("=" * 60)
    print("开始物理实验：粒子碰撞仿真")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 实验参数
    total_duration = 90  # 总运行时间：90秒
    log_interval = 10    # 日志间隔：10秒
    num_particles = 1000  # 模拟粒子数量
    
    # 初始化粒子状态
    particles = [
        {
            'id': i,
            'position': [random.uniform(-10, 10) for _ in range(3)],
            'velocity': [random.uniform(-1, 1) for _ in range(3)],
            'energy': random.uniform(0.1, 10.0)
        }
        for i in range(num_particles)
    ]
    
    start_time = time.time()
    elapsed_time = 0
    iteration = 0
    
    print(f"初始化完成: {num_particles} 个粒子")
    print(f"实验总时长: {total_duration} 秒")
    print(f"日志间隔: {log_interval} 秒")
    print("-" * 60)
    
    try:
        while elapsed_time < total_duration:
            iteration += 1
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # 模拟粒子运动
            collisions = 0
            total_energy = 0.0
            
            for particle in particles:
                # 更新位置
                for j in range(3):
                    particle['position'][j] += particle['velocity'][j] * 0.1
                
                # 随机碰撞检测
                if random.random() < 0.01:  # 1%的碰撞概率
                    collisions += 1
                    # 能量转移
                    particle['energy'] *= random.uniform(0.8, 1.2)
                
                total_energy += particle['energy']
            
            # 每10秒输出一次日志
            if elapsed_time >= iteration * log_interval:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代 {iteration}")
                print(f"  运行时间: {elapsed_time:.1f} 秒 / {total_duration} 秒")
                print(f"  粒子碰撞次数: {collisions}")
                print(f"  系统总能量: {total_energy:.2f} J")
                print(f"  剩余时间: {total_duration - elapsed_time:.1f} 秒")
                print("-" * 40)
            
            # 短暂休眠以避免CPU占用过高
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n实验被用户中断")
    
    # 实验结束
    print("=" * 60)
    print("物理实验完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总运行时间: {elapsed_time:.1f} 秒")
    print(f"总迭代次数: {iteration}")
    
    # 计算最终统计
    final_energy = sum(p['energy'] for p in particles)
    avg_velocity = sum(
        sum(v*v for v in p['velocity'])**0.5 
        for p in particles
    ) / num_particles
    
    print(f"最终系统能量: {final_energy:.2f} J")
    print(f"平均粒子速度: {avg_velocity:.3f} m/s")
    print("=" * 60)
    
    return {
        'total_time': elapsed_time,
        'iterations': iteration,
        'final_energy': final_energy,
        'avg_velocity': avg_velocity
    }

if __name__ == "__main__":
    print("Python版本:", sys.version)
    print("程序开始执行...")
    
    try:
        results = simulate_physics_experiment()
        print("\n实验总结:")
        for key, value in results.items():
            print(f"  {key}: {value}")
        
        # 验证运行时间
        if results['total_time'] >= 85:  # 允许5秒误差
            print("\n✅ 测试通过: 程序成功运行约90秒")
        else:
            print(f"\n⚠️  警告: 运行时间较短 ({results['total_time']:.1f}秒)")
            
    except Exception as e:
        print(f"\n❌ 错误发生: {e}")
        sys.exit(1)