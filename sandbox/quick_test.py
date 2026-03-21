"""
快速测试现有模型
"""
import torch
import numpy as np
from minesweeper_game import MinesweeperEnv
from minesweeper_nn import DQNAgent


def test_random_play(num_games: int = 100):
    """测试随机策略"""
    print("测试随机策略...")
    
    env = MinesweeperEnv(9, 9, 10)
    wins = 0
    total_rewards = []
    
    for game in range(num_games):
        state = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            valid_actions = env.get_valid_actions()
            if not valid_actions:
                break
            
            # 随机选择动作
            action = np.random.choice(valid_actions)
            next_state, reward, done, info = env.step(action)
            
            state = next_state
            total_reward += reward
        
        if info['status'].value == 1:  # WIN
            wins += 1
        
        total_rewards.append(total_reward)
    
    win_rate = wins / num_games * 100
    avg_reward = np.mean(total_rewards)
    
    print(f"随机策略结果 ({num_games}局):")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  平均奖励: {avg_reward:.2f}")
    
    return win_rate, avg_reward


def test_trained_model(model_path: str, num_games: int = 50):
    """测试训练好的模型"""
    print(f"\n测试训练模型: {model_path}")
    
    # 创建环境和智能体
    env = MinesweeperEnv(9, 9, 10)
    action_dim = 9 * 9 * 2
    
    agent = DQNAgent(
        height=9,
        width=9,
        action_dim=action_dim,
        epsilon_start=0.1,  # 低探索率
        epsilon_end=0.1,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    
    # 加载模型
    try:
        agent.load(model_path)
        print("模型加载成功")
    except:
        print("模型加载失败")
        return
    
    # 关闭探索
    agent.epsilon = 0.0
    
    wins = 0
    total_rewards = []
    total_steps = []
    
    for game in range(num_games):
        state = env.reset()
        total_reward = 0
        steps = 0
        done = False
        
        while not done and steps < 100:
            valid_actions = env.get_valid_actions()
            if not valid_actions:
                break
            
            # 使用模型选择动作
            action = agent.select_action(state, valid_actions, training=False)
            
            if action is None:
                break
            
            next_state, reward, done, info = env.step(action)
            
            state = next_state
            total_reward += reward
            steps += 1
        
        if info['status'].value == 1:  # WIN
            wins += 1
        
        total_rewards.append(total_reward)
        total_steps.append(steps)
        
        if (game + 1) % 10 == 0:
            print(f"  已完成 {game + 1}/{num_games} 局")
    
    win_rate = wins / num_games * 100
    avg_reward = np.mean(total_rewards)
    avg_steps = np.mean(total_steps)
    
    print(f"\n模型测试结果 ({num_games}局):")
    print(f"  胜率: {win_rate:.1f}% ({wins}/{num_games})")
    print(f"  平均奖励: {avg_reward:.2f}")
    print(f"  平均步数: {avg_steps:.1f}")
    
    return win_rate, avg_reward


def main():
    """主函数"""
    print("扫雷模型快速测试")
    print("="*60)
    
    # 测试随机策略作为基准
    random_win_rate, random_avg_reward = test_random_play(100)
    
    # 测试现有模型
    model_paths = [
        "models/minesweeper_9x9_10/model_final.pth",
        "models/minesweeper_9x9_10/model_episode_5000.pth"
    ]
    
    for model_path in model_paths:
        import os
        if os.path.exists(model_path):
            test_trained_model(model_path, 20)
        else:
            print(f"\n模型不存在: {model_path}")
    
    print("\n" + "="*60)
    print("总结:")
    print(f"随机策略基准 - 胜率: {random_win_rate:.1f}%, 平均奖励: {random_avg_reward:.2f}")
    print("\n修复版训练正在进行中...")
    print("新模型将保存到: models_fixed/minesweeper_9x9_10/")


if __name__ == "__main__":
    main()