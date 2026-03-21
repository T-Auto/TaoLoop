"""
简单演示：观看AI玩扫雷
"""
import torch
import numpy as np
import time
from minesweeper_game import MinesweeperEnv
from minesweeper_nn import DQNAgent


def watch_ai_play(model_path: str = None, num_games: int = 3):
    """观看AI玩扫雷"""
    print("观看AI玩扫雷")
    print("="*60)
    
    # 创建环境
    env = MinesweeperEnv(9, 9, 10)
    
    # 创建智能体
    action_dim = 9 * 9 * 2
    agent = DQNAgent(
        height=9,
        width=9,
        action_dim=action_dim,
        epsilon_start=0.0,  # 无探索
        epsilon_end=0.0,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    
    # 加载模型（如果有）
    if model_path:
        try:
            agent.load(model_path)
            print(f"已加载模型: {model_path}")
        except:
            print("模型加载失败，使用随机策略")
            agent.epsilon = 1.0  # 完全随机
    else:
        print("使用随机策略")
        agent.epsilon = 1.0
    
    for game_idx in range(num_games):
        print(f"\n游戏 {game_idx + 1}/{num_games}:")
        print("-"*40)
        
        state = env.reset()
        total_reward = 0
        steps = 0
        done = False
        
        # 显示初始状态
        env.render()
        time.sleep(1)
        
        while not done and steps < 50:
            # 获取有效动作
            valid_actions = env.get_valid_actions()
            
            if not valid_actions:
                print("没有有效动作")
                break
            
            # 选择动作
            action = agent.select_action(state, valid_actions, training=False)
            
            if action is None:
                print("无法选择动作")
                break
            
            # 执行动作
            x, y, action_type = action
            action_str = "揭开" if action_type == 0 else "标记"
            
            next_state, reward, done, info = env.step(action)
            
            # 显示
            print(f"\n步骤 {steps + 1}: 在({x}, {y}) {action_str}")
            print(f"奖励: {reward:.2f}, 累计奖励: {total_reward + reward:.2f}")
            env.render()
            
            # 更新状态
            state = next_state
            total_reward += reward
            steps += 1
            
            time.sleep(0.5)
            
            if done:
                break
        
        # 游戏结果
        print("\n" + "="*40)
        if info['status'].value == 1:
            print("🎉 AI胜利！")
        else:
            print("💥 AI失败")
        print(f"总步数: {steps}")
        print(f"总奖励: {total_reward:.2f}")
        print(f"揭开单元格: {info.get('revealed', 0)}")
        print(f"标记: {info.get('flags', 0)}")
        print("="*40)
        
        if game_idx < num_games - 1:
            time.sleep(2)


def test_random_baseline(num_games: int = 100):
    """测试随机策略基准"""
    print("\n测试随机策略基准...")
    
    env = MinesweeperEnv(9, 9, 10)
    wins = 0
    
    for game in range(num_games):
        env.reset()
        done = False
        
        while not done:
            valid_actions = env.get_valid_actions()
            if not valid_actions:
                break
            
            # 随机选择动作
            import random
            action = random.choice(valid_actions)
            _, _, done, info = env.step(action)
        
        if info['status'].value == 1:
            wins += 1
        
        if (game + 1) % 20 == 0:
            print(f"  已完成 {game + 1}/{num_games} 局")
    
    win_rate = wins / num_games * 100
    print(f"\n随机策略基准 ({num_games}局):")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  平均每局胜利需要尝试: {100/win_rate:.1f} 局" if win_rate > 0 else "  从未胜利")
    
    return win_rate


def main():
    """主函数"""
    print("扫雷AI演示系统")
    print("="*60)
    
    # 测试随机基准
    random_win_rate = test_random_baseline(50)
    
    print("\n" + "="*60)
    print("AI演示选项:")
    print("1. 观看随机AI玩扫雷")
    print("2. 观看训练模型玩扫雷")
    print("3. 退出")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == '1':
        watch_ai_play(num_games=3)
    
    elif choice == '2':
        # 尝试加载模型
        model_paths = [
            "models/minesweeper_9x9_10/model_final.pth",
            "models/minesweeper_9x9_10/model_episode_5000.pth"
        ]
        
        import os
        model_to_use = None
        for path in model_paths:
            if os.path.exists(path):
                model_to_use = path
                break
        
        if model_to_use:
            watch_ai_play(model_path=model_to_use, num_games=3)
        else:
            print("未找到训练模型，使用随机策略")
            watch_ai_play(num_games=3)
    
    elif choice == '3':
        print("退出")
    
    else:
        print("无效选择")
    
    print("\n" + "="*60)
    print("训练状态:")
    print("1. 第一次训练已完成（探索率问题，胜率0%）")
    print("2. 修复版训练正在进行中...")
    print("3. 新模型将保存到: models_fixed/minesweeper_9x9_10/")
    print("="*60)


if __name__ == "__main__":
    main()