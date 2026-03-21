#!/usr/bin/env python3
"""
物理仿真实验模拟程序
运行300秒，每10秒输出一次日志
用于测试异步消息机制和硬件监控
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
        # 在Windows上使用当前目录的磁盘信息
        import os
        current_drive = os.path.splitdrive(os.getcwd())[0] + '\\'
        disk = psutil.disk_usage(current_drive)
        
        # 尝试获取GPU信息（如果可用）
        gpu_info = None
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_info = {
                    'name': gpu.name,
                    'load': gpu.load * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'temperature': gpu.temperature
                }
        except ImportError:
            pass
            
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_gb': memory.used / (1024**3),
            'memory_total_gb': memory.total / (1024**3),
            'disk_free_gb': disk.free / (1024**3),
            'gpu': gpu_info
        }
    except Exception as e:
        return {'error': str(e)}

def simulate_physics_experiment(iteration, total_iterations):
    """模拟物理实验计算"""
    # 模拟一些物理计算
    temperature = 300 + random.uniform(-5, 5)  # 温度波动
    pressure = 1.0 + random.uniform(-0.1, 0.1)  # 压力波动
    magnetic_field = 0.5 + random.uniform(-0.05, 0.05)  # 磁场强度
    
    # 模拟一些计算密集型操作
    result = 0
    for i in range(10000):
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
    print("物理仿真实验开始")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    total_duration = 300  # 总运行时间：300秒
    log_interval = 10     # 日志间隔：10秒
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
        'iterations': [],
        'system_info_history': []
    }
    
    try:
        for iteration in range(1, total_iterations + 1):
            # 获取系统信息
            system_info = get_system_info()
            experiment_data['system_info_history'].append(system_info)
            
            # 执行物理仿真
            experiment_result = simulate_physics_experiment(iteration, total_iterations)
            experiment_data['iterations'].append(experiment_result)
            
            # 输出日志
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代 {iteration}/{total_iterations}")
            print(f"  实验数据: 温度={experiment_result['temperature_k']}K, "
                  f"压力={experiment_result['pressure_atm']}atm, "
                  f"磁场={experiment_result['magnetic_field_t']}T")
            print(f"  系统状态: CPU={system_info.get('cpu_percent', 'N/A')}%, "
                  f"内存={system_info.get('memory_percent', 'N/A')}%")
            
            if system_info.get('gpu'):
                gpu = system_info['gpu']
                print(f"  GPU状态: {gpu['name']} - 负载={gpu['load']:.1f}%, "
                      f"显存={gpu['memory_used']}/{gpu['memory_total']}MB, "
                      f"温度={gpu['temperature']}°C")
            
            print(f"  进度: {experiment_result['progress_percent']}%")
            print("-" * 40)
            
            # 保存中间结果（每5次迭代保存一次）
            if iteration % 5 == 0:
                with open('experiment_progress.json', 'w') as f:
                    json.dump(experiment_data, f, indent=2)
                print(f"  进度已保存到 experiment_progress.json")
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
        
        with open('experiment_final.json', 'w') as f:
            json.dump(experiment_data, f, indent=2)
        
        print("=" * 60)
        print("物理仿真实验结束")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"实际运行时间: {experiment_data['actual_duration']:.1f} 秒")
        print(f"数据已保存到: experiment_final.json")
        print("=" * 60)

if __name__ == "__main__":
    main()