"""
训练监控脚本
定期检查训练进度和模型性能
"""
import time
import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime


def monitor_training_progress(model_dir: str = "models/minesweeper_9x9_10"):
    """监控训练进度"""
    if not os.path.exists(model_dir):
        print(f"模型目录不存在: {model_dir}")
        return
    
    # 检查训练统计
    stats_path = os.path.join(model_dir, "training_stats.npz")
    if os.path.exists(stats_path):
        stats = np.load(stats_path)
        
        print(f"\n训练进度监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 基本信息
        total_episodes = len(stats['rewards'])
        print(f"已完成回合数: {total_episodes}")
        
        if total_episodes >= 100:
            # 最近100回合统计
            recent_wins = stats['wins'][-100:]
            recent_rewards = stats['rewards'][-100:]
            recent_steps = stats['steps'][-100:]
            
            win_rate = np.mean(recent_wins) * 100
            avg_reward = np.mean(recent_rewards)
            avg_steps = np.mean(recent_steps)
            
            print(f"最近100回合胜率: {win_rate:.1f}%")
            print(f"最近100回合平均奖励: {avg_reward:.2f}")
            print(f"最近100回合平均步数: {avg_steps:.1f}")
        
        # 探索率
        current_epsilon = stats['epsilon'][-1] if len(stats['epsilon']) > 0 else 1.0
        print(f"当前探索率: {current_epsilon:.3f}")
        
        # 损失
        if 'losses' in stats and len(stats['losses']) > 0:
            recent_losses = stats['losses'][-100:]
            avg_loss = np.mean([l for l in recent_losses if l > 0])
            print(f"最近平均损失: {avg_loss:.4f}")
        
        # 模型文件
        model_files = [f for f in os.listdir(model_dir) if f.endswith('.pth')]
        print(f"模型文件数量: {len(model_files)}")
        
        if model_files:
            # 按修改时间排序
            model_files.sort(key=lambda x: os.path.getmtime(os.path.join(model_dir, x)), reverse=True)
            latest_model = model_files[0]
            mtime = os.path.getmtime(os.path.join(model_dir, latest_model))
            print(f"最新模型: {latest_model}")
            print(f"最后更新时间: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 绘制简单进度图
        if total_episodes >= 200:
            plot_progress(stats, model_dir)
    
    else:
        print(f"训练统计文件不存在: {stats_path}")


def plot_progress(stats: dict, save_dir: str):
    """绘制训练进度图"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    
    episodes = range(len(stats['rewards']))
    
    # 奖励曲线
    axes[0, 0].plot(episodes, stats['rewards'], alpha=0.3, label='原始')
    if len(stats['rewards']) >= 100:
        # 滑动平均
        window = min(100, len(stats['rewards']) // 10)
        smoothed = np.convolve(stats['rewards'], np.ones(window)/window, mode='valid')
        axes[0, 0].plot(range(window-1, len(stats['rewards'])), smoothed, 
                       label=f'平滑({window})', linewidth=2, color='red')
    axes[0, 0].set_xlabel('回合')
    axes[0, 0].set_ylabel('累计奖励')
    axes[0, 0].set_title('奖励曲线')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # 胜率曲线
    if len(stats['wins']) >= 100:
        win_rates = []
        for i in range(100, len(stats['wins']) + 1):
            win_rates.append(np.mean(stats['wins'][i-100:i]) * 100)
        
        axes[0, 1].plot(range(100, len(stats['wins']) + 1), win_rates, linewidth=2)
        axes[0, 1].set_xlabel('回合')
        axes[0, 1].set_ylabel('胜率 (%)')
        axes[0, 1].set_title('胜率曲线 (100回合滑动平均)')
        axes[0, 1].grid(True, alpha=0.3)
    
    # 步数曲线
    axes[1, 0].plot(episodes, stats['steps'], alpha=0.3, label='原始')
    if len(stats['steps']) >= 100:
        window = min(100, len(stats['steps']) // 10)
        smoothed = np.convolve(stats['steps'], np.ones(window)/window, mode='valid')
        axes[1, 0].plot(range(window-1, len(stats['steps'])), smoothed, 
                       label=f'平滑({window})', linewidth=2, color='red')
    axes[1, 0].set_xlabel('回合')
    axes[1, 0].set_ylabel('步数')
    axes[1, 0].set_title('步数曲线')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # 探索率曲线
    axes[1, 1].plot(episodes, stats['epsilon'], linewidth=2)
    axes[1, 1].set_xlabel('回合')
    axes[1, 1].set_ylabel('探索率')
    axes[1, 1].set_title('探索率衰减曲线')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图像
    plot_path = os.path.join(save_dir, "progress_monitor.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"进度图已保存到: {plot_path}")


def check_system_resources():
    """检查系统资源"""
    import psutil
    
    print("\n系统资源监控:")
    print("-"*40)
    
    # CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU使用率: {cpu_percent:.1f}%")
    
    # 内存使用
    memory = psutil.virtual_memory()
    print(f"内存使用: {memory.used/1024**3:.1f}GB/{memory.total/1024**3:.1f}GB ({memory.percent}%)")
    
    # GPU信息（如果可用）
    try:
        import torch
        if torch.cuda.is_available():
            print(f"GPU设备: {torch.cuda.get_device_name(0)}")
            print(f"GPU内存: {torch.cuda.memory_allocated()/1024**3:.2f}GB / {torch.cuda.memory_reserved()/1024**3:.2f}GB")
    except:
        pass
    
    # 磁盘空间
    disk = psutil.disk_usage('.')
    print(f"磁盘空间: {disk.free/1024**3:.1f}GB/{disk.total/1024**3:.1f}GB ({disk.percent}%)")


def main():
    """主函数"""
    print("扫雷训练监控系统")
    print("="*60)
    
    # 检查系统资源
    check_system_resources()
    
    # 监控训练进度
    monitor_training_progress()
    
    print("\n监控完成。训练仍在后台进行中...")
    print("使用以下命令查看训练状态:")
    print("  uv run python monitor_training.py")
    print("\n训练完成后，运行演示:")
    print("  uv run python demo_minesweeper.py")


if __name__ == "__main__":
    main()