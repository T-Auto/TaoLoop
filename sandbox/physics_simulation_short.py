#!/usr/bin/env python3
"""
简化的物理仿真实验模拟程序
运行30秒，每5秒输出一次日志
用于测试后台任务功能
"""

import time
import sys
import random
import json
from datetime import datetime

def simulate_physics_experiment(iteration, total_iterations):
    """模拟物理实验计算"""
    # 模拟一些物理计算
    temperature = 300 + random.uniform(-5, 5)  # 温度波动
    pressure = 1.0 + random.uniform(-0.1, 0.1)  # 压力波动
    magnetic_field = 0.5 + random.uniform(-0.05, 0.05)  # 磁场强度
    
    # 模拟一些计算密集型操作
    result = 0
    for i in range(5000):
        result += random.random() * 0.0001
    
    # 模拟实验数据
    data_point = {
        'iteration': iteration,
        'temperature_k': round(temperature, 2),
        'pressure_atm': round(pressure, 3),
        'magnetic_field_t': round(magnetic_field, 4),
        'computation_result': round(result, 6),
        'progress_percent': round((iteration / total_iterations) * 100, 1)
    }
    
    return data_point

def main():
    """主函数"""
    print("=" * 60)
    print("简化的物理仿真实验开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    total_duration = 30  # 总运行时间：30秒
    log_interval = 5     # 日志间隔：5秒
    total_iterations = total_duration // log_interval
    
    print(f"实验配置:")
    print(f"  - 总运行时间: {total_duration} 秒")
    print(f"  - 日志间隔: {log_interval} 秒")
    print(f"  - 总迭代次数: {total_iterations}")
    print(f"  - 预计结束时间: {datetime.fromtimestamp(time.time() + total_duration).strftime('%H:%M:%S')}")
    print()
    
    # 初始化实验数据
    experiment_data = {
        'start_time': datetime.now().isoformat(),
        'total_duration_seconds': total_duration,
        'log_interval_seconds': log_interval,
        'iterations': []
    }
    
    try:
        for iteration in range(1, total_iterations + 1):
            # 执行物理仿真
            experiment_result = simulate_physics_experiment(iteration, total_iterations)
            experiment_data['iterations'].append(experiment_result)
            
            # 输出日志
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代 {iteration}/{total_iterations}")
            print(f"  实验数据: 温度={experiment_result['temperature_k']}K, "
                  f"压力={experiment_result['pressure_atm']}atm, "
                  f"磁场={experiment_result['magnetic_field_t']}T")
            print(f"  进度: {experiment_result['progress_percent']}%")
            print("-" * 40)
            
            # 保存中间结果
            if iteration % 2 == 0:
                with open('experiment_short_progress.json', 'w') as f:
                    json.dump(experiment_data, f, indent=2)
                print(f"  进度已保存到 experiment_short_progress.json")
                print()
            
            # 等待下一个日志间隔（最后迭代不等待）
            if iteration < total_iterations:
                time.sleep(log_interval)
                
    except KeyboardInterrupt:
        print("\n实验被用户中断")
    except Exception as e:
        print(f"\n实验发生错误: {e}")
    finally:
        # 保存最终结果
        experiment_data['end_time'] = datetime.now().isoformat()
        experiment_data['actual_duration'] = time.time() - time.mktime(
            datetime.fromisoformat(experiment_data['start_time']).timetuple()
        )
        
        with open('experiment_short_final.json', 'w') as f:
            json.dump(experiment_data, f, indent=2)
        
        print("=" * 60)
        print("简化的物理仿真实验结束")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"实际运行时间: {experiment_data['actual_duration']:.1f} 秒")
        print(f"数据已保存到: experiment_short_final.json")
        print("=" * 60)

if __name__ == "__main__":
    main()