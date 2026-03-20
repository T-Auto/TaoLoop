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
    print("物理实验模拟开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("实验类型: 粒子碰撞模拟")
    print("运行时长: 90秒")
    print("日志间隔: 10秒")
    print("=" * 60)
    
    total_duration = 90  # 总运行时间：90秒
    log_interval = 10    # 日志间隔：10秒
    start_time = time.time()
    
    # 模拟实验参数
    particle_count = 1000
    collision_rate = 0.1
    energy_level = 100.0
    
    iteration = 0
    
    try:
        while time.time() - start_time < total_duration:
            iteration += 1
            elapsed = time.time() - start_time
            
            # 模拟物理过程
            collisions = int(particle_count * collision_rate * random.uniform(0.8, 1.2))
            energy_change = random.uniform(-5.0, 5.0)
            energy_level += energy_change
            
            # 生成实验数据
            temperature = 300 + random.uniform(-10, 10)  # 模拟温度波动
            pressure = 1.0 + random.uniform(-0.1, 0.1)   # 模拟压力波动
            
            # 每10秒输出一次详细日志
            if elapsed >= iteration * log_interval:
                print(f"\n[实验日志] 时间: {elapsed:.1f}秒")
                print(f"  迭代次数: {iteration}")
                print(f"  粒子碰撞数: {collisions}")
                print(f"  能量水平: {energy_level:.2f} MeV")
                print(f"  系统温度: {temperature:.1f} K")
                print(f"  系统压力: {pressure:.2f} atm")
                print(f"  碰撞率: {collision_rate:.3f}")
                print(f"  剩余时间: {total_duration - elapsed:.1f}秒")
                
                # 模拟一些实验事件
                if random.random() < 0.3:
                    event_type = random.choice(["粒子衰变", "能量共振", "散射事件", "吸收事件"])
                    print(f"  [实验事件] 检测到: {event_type}")
            
            # 每秒输出一个进度点
            if int(elapsed) > int(elapsed - 1):
                sys.stdout.write('.')
                sys.stdout.flush()
            
            time.sleep(1)  # 每秒循环一次
        
        # 实验结束
        print(f"\n\n{'=' * 60}")
        print("物理实验模拟完成")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总运行时间: {total_duration}秒")
        print(f"总迭代次数: {iteration}")
        print("实验总结:")
        print(f"  - 平均碰撞率: {collision_rate:.3f}")
        print(f"  - 最终能量水平: {energy_level:.2f} MeV")
        print(f"  - 模拟粒子数: {particle_count}")
        print("=" * 60)
        
        # 生成实验结果摘要
        return {
            "total_duration": total_duration,
            "iterations": iteration,
            "final_energy": energy_level,
            "particle_count": particle_count,
            "collision_rate": collision_rate,
            "success": True
        }
        
    except KeyboardInterrupt:
        print("\n\n实验被用户中断")
        return {"success": False, "reason": "user_interrupt"}
    except Exception as e:
        print(f"\n\n实验发生错误: {e}")
        return {"success": False, "reason": str(e)}

if __name__ == "__main__":
    print("启动物理实验模拟程序...")
    result = simulate_physics_experiment()
    
    if result.get("success"):
        print("\n✅ 实验成功完成！")
        print(f"结果已保存，可在后续分析中使用。")
    else:
        print(f"\n❌ 实验失败: {result.get('reason', '未知原因')}")