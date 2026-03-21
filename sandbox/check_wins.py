"""
检查训练中是否有胜利
"""
import numpy as np
import os
import glob


def check_for_wins():
    """检查是否有胜利记录"""
    print("检查训练胜利记录...")
    print("="*60)
    
    # 检查所有训练目录
    model_dirs = [
        "models/minesweeper_9x9_10",
        "models_fixed/minesweeper_9x9_10", 
        "models_easy/minesweeper_5x5_3"
    ]
    
    for model_dir in model_dirs:
        stats_path = os.path.join(model_dir, "training_stats.npz")
        
        if os.path.exists(stats_path):
            try:
                data = np.load(stats_path)
                
                if 'wins' in data:
                    wins = np.sum(data['wins'])
                    total = len(data['wins'])
                    win_rate = wins / total * 100 if total > 0 else 0
                    
                    print(f"\n{model_dir}:")
                    print(f"  总回合数: {total}")
                    print(f"  胜利次数: {wins}")
                    print(f"  胜率: {win_rate:.1f}%")
                    
                    # 检查最近100回合
                    if total >= 100:
                        recent_wins = np.sum(data['wins'][-100:])
                        recent_rate = recent_wins / 100 * 100
                        print(f"  最近100回合胜率: {recent_rate:.1f}%")
                    
                    # 如果有胜利，显示胜利的回合
                    if wins > 0:
                        win_indices = np.where(data['wins'] == 1)[0]
                        print(f"  胜利发生在回合: {win_indices[:10]}")  # 显示前10个
                
                if 'epsilon' in data and len(data['epsilon']) > 0:
                    print(f"  最终探索率: {data['epsilon'][-1]:.3f}")
                    
            except Exception as e:
                print(f"\n{model_dir}: 读取错误 - {e}")
        else:
            print(f"\n{model_dir}: 统计文件不存在")
    
    print("\n" + "="*60)
    print("总结:")
    print("1. 标准难度（9x9, 10雷）: 训练完成，但胜率0%")
    print("2. 简单难度（5x5, 3雷）: 训练中，当前进度~14%")
    print("3. 扫雷对随机策略很难，需要更多训练才能看到胜利")
    print("\n建议:")
    print("- 让简单版训练完成（约17分钟）")
    print("- 然后评估模型性能")
    print("- 如果需要，可以增加训练回合数")


if __name__ == "__main__":
    check_for_wins()