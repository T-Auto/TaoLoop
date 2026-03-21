#!/usr/bin/env python3
"""
物理实验仿真测试程序
模拟一个运行40秒的物理实验，每隔10秒输出一次日志
用于测试CLI工具的功能
"""

import time
import sys
import random
from datetime import datetime

def simulate_physics_experiment():
    """
    模拟物理实验过程
    """
    print("=" * 60)
    print("物理实验仿真测试 - 开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 实验总时长：40秒
    total_duration = 40
    # 日志输出间隔：10秒
    log_interval = 10
    
    # 模拟实验参数
    temperature = 25.0  # 初始温度 (°C)
    pressure = 101.3    # 初始压力 (kPa)
    voltage = 12.0      # 初始电压 (V)
    current = 0.5       # 初始电流 (A)
    
    # 实验步骤描述
    experiment_steps = [
        "1. 初始化实验设备",
        "2. 校准传感器",
        "3. 开始数据采集",
        "4. 应用实验条件",
        "5. 记录实验结果",
        "6. 清理实验环境"
    ]
    
    start_time = time.time()
    elapsed_time = 0
    step_index = 0
    
    while elapsed_time < total_duration:
        # 计算已运行时间
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # 每10秒输出一次日志
        if elapsed_time >= step_index * log_interval:
            # 模拟物理参数变化
            temperature += random.uniform(-0.5, 1.0)
            pressure += random.uniform(-0.2, 0.2)
            voltage += random.uniform(-0.1, 0.1)
            current += random.uniform(-0.05, 0.05)
            
            # 输出实验状态
            print("\n" + "-" * 50)
            print(f"时间戳: {datetime.now().strftime('%H:%M:%S')}")
            print(f"运行时间: {elapsed_time:.1f} 秒 / {total_duration} 秒")
            
            if step_index < len(experiment_steps):
                print(f"当前步骤: {experiment_steps[step_index]}")
            
            # 输出模拟的物理参数
            print("\n实验参数:")
            print(f"  温度: {temperature:.2f} °C")
            print(f"  压力: {pressure:.2f} kPa")
            print(f"  电压: {voltage:.2f} V")
            print(f"  电流: {current:.2f} A")
            
            # 模拟一些实验事件
            if step_index == 0:
                print("状态: 设备初始化完成")
            elif step_index == 1:
                print("状态: 传感器校准中...")
            elif step_index == 2:
                print("状态: 数据采集正常")
            elif step_index == 3:
                print("状态: 实验条件稳定")
            elif step_index == 4:
                print("状态: 记录数据点")
            else:
                print("状态: 实验进行中")
            
            step_index += 1
        
        # 短暂休眠以避免CPU占用过高
        time.sleep(0.1)
    
    # 实验结束
    print("\n" + "=" * 60)
    print("物理实验仿真测试 - 完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总运行时间: {total_duration} 秒")
    print("=" * 60)
    
    # 生成实验结果摘要
    print("\n实验结果摘要:")
    print(f"- 完成步骤数: {len(experiment_steps)}")
    print(f"- 最终温度: {temperature:.2f} °C")
    print(f"- 最终压力: {pressure:.2f} kPa")
    print(f"- 最终电压: {voltage:.2f} V")
    print(f"- 最终电流: {current:.2f} A")
    print("- 实验状态: 成功完成")
    
    return True

def main():
    """主函数"""
    try:
        print("CLI工具测试 - 物理实验仿真程序")
        print("程序将运行40秒，每隔10秒输出一次日志")
        print("按 Ctrl+C 可提前终止程序\n")
        
        # 运行仿真实验
        success = simulate_physics_experiment()
        
        if success:
            print("\n✅ 测试完成: CLI工具运行正常")
            return 0
        else:
            print("\n❌ 测试失败: 实验仿真异常")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断")
        return 130
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())