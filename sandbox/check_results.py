"""
检查训练结果
"""
import numpy as np
import os

# 加载训练统计
stats_path = "models/minesweeper_9x9_10/training_stats.npz"
if os.path.exists(stats_path):
    data = np.load(stats_path)
    
    print("="*60)
    print("扫雷神经网络训练结果")
    print("="*60)
    
    print(f"总训练回合数: {len(data['rewards'])}")
    print(f"最终探索率: {data['epsilon'][-1]:.4f}")
    
    # 计算统计
    total_wins = np.sum(data['wins'])
    win_rate = total_wins / len(data['wins']) * 100
    avg_reward = np.mean(data['rewards'])
    avg_steps = np.mean(data['steps'])
    
    print(f"总胜利次数: {total_wins}")
    print(f"总体胜率: {win_rate:.1f}%")
    print(f"平均奖励: {avg_reward:.2f}")
    print(f"平均步数: {avg_steps:.1f}")
    
    # 最近100回合统计
    if len(data['wins']) >= 100:
        recent_wins = np.sum(data['wins'][-100:])
        recent_win_rate = recent_wins / 100 * 100
        recent_avg_reward = np.mean(data['rewards'][-100:])
        
        print(f"\n最近100回合统计:")
        print(f"  胜利次数: {recent_wins}")
        print(f"  胜率: {recent_win_rate:.1f}%")
        print(f"  平均奖励: {recent_avg_reward:.2f}")
    
    # 检查模型文件
    model_dir = "models/minesweeper_9x9_10"
    model_files = [f for f in os.listdir(model_dir) if f.endswith('.pth')]
    print(f"\n模型文件数量: {len(model_files)}")
    
    if 'model_final.pth' in model_files:
        print("✅ 最终模型已保存: model_final.pth")
    
    if os.path.exists(os.path.join(model_dir, "training_curves.png")):
        print("✅ 训练曲线图已生成: training_curves.png")
    
    print("\n" + "="*60)
    print("训练完成！现在可以运行演示：")
    print("  uv run python demo_minesweeper.py")
    print("="*60)
    
else:
    print(f"训练统计文件不存在: {stats_path}")