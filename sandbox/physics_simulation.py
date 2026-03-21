#!/usr/bin/env python3
"""
物理实验仿真程序
模拟一个简单的粒子碰撞实验，运行300秒，每10秒输出一次状态
"""

import time
import random
import sys
import math
from datetime import datetime

class Particle:
    """模拟粒子"""
    def __init__(self, id, mass, position, velocity):
        self.id = id
        self.mass = mass
        self.position = position  # (x, y, z)
        self.velocity = velocity  # (vx, vy, vz)
        self.energy = 0.5 * mass * (velocity[0]**2 + velocity[1]**2 + velocity[2]**2)
    
    def update(self, dt, force):
        """更新粒子状态"""
        # F = ma => a = F/m
        acceleration = (force[0]/self.mass, force[1]/self.mass, force[2]/self.mass)
        
        # 更新速度: v = v0 + a*dt
        self.velocity = (
            self.velocity[0] + acceleration[0] * dt,
            self.velocity[1] + acceleration[1] * dt,
            self.velocity[2] + acceleration[2] * dt
        )
        
        # 更新位置: x = x0 + v*dt
        self.position = (
            self.position[0] + self.velocity[0] * dt,
            self.position[1] + self.velocity[1] * dt,
            self.position[2] + self.velocity[2] * dt
        )
        
        # 更新能量
        self.energy = 0.5 * self.mass * (
            self.velocity[0]**2 + self.velocity[1]**2 + self.velocity[2]**2
        )
    
    def distance_to(self, other):
        """计算到另一个粒子的距离"""
        dx = self.position[0] - other.position[0]
        dy = self.position[1] - other.position[1]
        dz = self.position[2] - other.position[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

class PhysicsSimulation:
    """物理仿真实验"""
    def __init__(self, duration_sec=300, log_interval=10):
        self.duration_sec = duration_sec
        self.log_interval = log_interval
        self.start_time = None
        self.particles = []
        self.collisions = 0
        self.total_energy = 0.0
        self.system_momentum = (0.0, 0.0, 0.0)
        
        # 初始化粒子
        self._initialize_particles()
    
    def _initialize_particles(self):
        """初始化10个随机粒子"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 初始化粒子系统...")
        
        for i in range(10):
            mass = random.uniform(1.0, 5.0)  # 质量 1-5 kg
            position = (
                random.uniform(-10.0, 10.0),
                random.uniform(-10.0, 10.0),
                random.uniform(-10.0, 10.0)
            )
            velocity = (
                random.uniform(-2.0, 2.0),
                random.uniform(-2.0, 2.0),
                random.uniform(-2.0, 2.0)
            )
            
            particle = Particle(i, mass, position, velocity)
            self.particles.append(particle)
            
            # 累加系统总动量和能量
            self.system_momentum = (
                self.system_momentum[0] + mass * velocity[0],
                self.system_momentum[1] + mass * velocity[1],
                self.system_momentum[2] + mass * velocity[2]
            )
            self.total_energy += particle.energy
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 初始化完成: {len(self.particles)} 个粒子")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 系统总能量: {self.total_energy:.2f} J")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 系统总动量: ({self.system_momentum[0]:.2f}, {self.system_momentum[1]:.2f}, {self.system_momentum[2]:.2f}) kg·m/s")
    
    def _calculate_force(self, particle):
        """计算作用在粒子上的力（简化的引力模型）"""
        force = [0.0, 0.0, 0.0]
        G = 6.67430e-11  # 引力常数
        
        for other in self.particles:
            if other.id == particle.id:
                continue
            
            # 计算距离
            dx = other.position[0] - particle.position[0]
            dy = other.position[1] - particle.position[1]
            dz = other.position[2] - particle.position[2]
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            # 避免除零
            if distance < 0.1:
                distance = 0.1
                self.collisions += 1
            
            # 引力公式: F = G * m1 * m2 / r^2
            force_magnitude = G * particle.mass * other.mass / (distance * distance)
            
            # 力的方向
            force[0] += force_magnitude * dx / distance
            force[1] += force_magnitude * dy / distance
            force[2] += force_magnitude * dz / distance
        
        return tuple(force)
    
    def _check_collisions(self):
        """检查粒子碰撞"""
        for i in range(len(self.particles)):
            for j in range(i+1, len(self.particles)):
                p1 = self.particles[i]
                p2 = self.particles[j]
                
                if p1.distance_to(p2) < 0.5:  # 碰撞阈值
                    self.collisions += 1
                    
                    # 简单的弹性碰撞处理
                    # 交换速度（简化模型）
                    p1.velocity, p2.velocity = p2.velocity, p1.velocity
    
    def _log_status(self, elapsed):
        """记录系统状态"""
        # 计算当前总能量和动量
        current_energy = sum(p.energy for p in self.particles)
        current_momentum = [0.0, 0.0, 0.0]
        
        for p in self.particles:
            current_momentum[0] += p.mass * p.velocity[0]
            current_momentum[1] += p.mass * p.velocity[1]
            current_momentum[2] += p.mass * p.velocity[2]
        
        # 计算能量守恒误差
        energy_error = abs(current_energy - self.total_energy) / self.total_energy * 100 if self.total_energy > 0 else 0
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === 仿真状态报告 ===")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已运行时间: {elapsed:.1f} / {self.duration_sec} 秒")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 粒子数量: {len(self.particles)}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 碰撞次数: {self.collisions}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 当前总能量: {current_energy:.2f} J")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 能量守恒误差: {energy_error:.4f}%")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 当前总动量: ({current_momentum[0]:.2f}, {current_momentum[1]:.2f}, {current_momentum[2]:.2f}) kg·m/s")
        
        # 输出一些粒子状态
        if len(self.particles) >= 3:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 粒子0: 位置({self.particles[0].position[0]:.2f}, {self.particles[0].position[1]:.2f}, {self.particles[0].position[2]:.2f}), "
                  f"速度({self.particles[0].velocity[0]:.2f}, {self.particles[0].velocity[1]:.2f}, {self.particles[0].velocity[2]:.2f}) m/s")
        
        # 模拟一些硬件监控信息
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 系统CPU使用率: {cpu_percent:.1f}%")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 系统内存使用: {memory.used/1e9:.2f} / {memory.total/1e9:.2f} GB ({memory.percent}%)")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 进程内存: {psutil.Process().memory_info().rss/1e6:.2f} MB")
        except ImportError:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 硬件监控: psutil模块未安装，跳过硬件信息")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 硬件监控出错: {e}")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ======================\n")
        
        # 刷新输出缓冲区
        sys.stdout.flush()
    
    def run(self):
        """运行仿真"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始物理仿真实验")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 总时长: {self.duration_sec} 秒")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 日志间隔: {self.log_interval} 秒")
        
        self.start_time = time.time()
        last_log_time = self.start_time
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - self.start_time
                
                # 检查是否达到总时长
                if elapsed >= self.duration_sec:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 仿真完成！总运行时间: {elapsed:.1f} 秒")
                    break
                
                # 每10秒输出一次日志
                if current_time - last_log_time >= self.log_interval:
                    self._log_status(elapsed)
                    last_log_time = current_time
                
                # 仿真步进
                dt = 0.1  # 时间步长 0.1秒
                
                # 更新每个粒子
                for particle in self.particles:
                    force = self._calculate_force(particle)
                    particle.update(dt, force)
                
                # 检查碰撞
                self._check_collisions()
                
                # 短暂休眠以避免CPU占用过高
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 仿真被用户中断")
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 仿真出错: {e}")
        
        # 最终报告
        final_elapsed = time.time() - self.start_time
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === 仿真最终报告 ===")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 总运行时间: {final_elapsed:.1f} 秒")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 总碰撞次数: {self.collisions}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 仿真结束")

if __name__ == "__main__":
    # 创建并运行仿真
    simulation = PhysicsSimulation(duration_sec=300, log_interval=10)
    simulation.run()