"""
修复版扫雷训练脚本
调整探索率衰减，让智能体能够学习
"""
import torch
import numpy as np
import random
import time
import os
from datetime import datetime
from collections import deque
import matplotlib.pyplot as plt
from tqdm import tqdm

from minesweeper_game import MinesweeperEnv
from minesweeper_nn import DQNAgent


class FixedMinesweeperTrainer:
    """修复版扫雷训练器"""
    
    def __init__(
        self,
        width: int = 9,
        height: int = 9,
        mines: int = 10,
        episodes: int = 3000,  # 减少回合数
        max_steps: int = 200,
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.1,  # 提高最终探索率
        epsilon_decay_steps: int = 2000,  # 明确衰减步数
        memory_size: int = 10000,
        batch_size: int = 64,
        target_update: int = 200,
        save_interval: int = 300,
        log_interval: int = 100,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        初始化训练器
        
        Args:
            width: 游戏宽度
            height: 游戏高度
            mines: 地雷数量
            episodes: 训练回合数
            max_steps: 每回合最大步数
            learning_rate: 学习率
            gamma: 折扣因子
            epsilon_start: 初始探索率
            epsilon_end: 最小探索率
            epsilon_decay_steps: 探索率衰减步数
            memory_size: 经验回放缓冲区大小
            batch_size: 训练批次大小
            target_update: 目标网络更新频率
            save_interval: 保存间隔
            log_interval: 日志间隔
            device: 计算设备
        """
        self.width = width
        self.height = height
        self.mines = mines
        self.episodes = episodes
        self.max_steps = max_steps
        self.save_interval = save_interval
        self.log_interval = log_interval
        self.device = device
        
        # 探索率衰减参数
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = (epsilon_end / epsilon_start) ** (1 / epsilon_decay_steps)
        
        # 创建环境
        self.env = MinesweeperEnv(width, height, mines)
        action_dim = width * height * 2
        
        # 创建智能体（使用线性衰减）
        self.agent = DQNAgent(
            height=height,
            width=width,
            action_dim=action_dim,
            learning_rate=learning_rate,
            gamma=gamma,
            epsilon_start=epsilon_start,
            epsilon_end=epsilon_end,
            epsilon_decay=0.999,  # 设置一个基础衰减
            memory_size=memory_size,
            batch_size=batch_size,
            target_update=target_update,
            device=device
        )
        
        # 覆盖智能体的探索率衰减逻辑
        self.agent.epsilon_decay = self.epsilon_decay
        
        # 训练统计
        self.rewards_history = []
        self.wins_history = []
        self.steps_history = []
        self.losses_history = []
        self.epsilon_history = []
        
        # 创建保存目录
        self.save_dir = f"models_fixed/minesweeper_{width}x{height}_{mines}"
        os.makedirs(self.save_dir, exist_ok=True)
        
        print(f"修复版训练配置:")
        print(f"  游戏: {width}x{height}, 地雷: {mines}")
        print(f"  设备: {device}")
        print(f"  回合数: {episodes}")
        print(f"  探索率: {epsilon_start} -> {epsilon_end} (衰减步数: {epsilon_decay_steps})")
        print(f"  探索率衰减系数: {self.epsilon_decay:.6f}")
        print(f"  模型保存目录: {self.save_dir}")
    
    def get_epsilon(self, step: int) -> float:
        """计算当前探索率（线性衰减）"""
        if step >= self.episodes * 0.8:  # 最后20%保持最小探索率
            return self.epsilon_end
        
        # 线性衰减
        decay_steps = self.episodes * 0.8
        epsilon = self.epsilon_start - (self.epsilon_start - self.epsilon_end) * (step / decay_steps)
        return max(epsilon, self.epsilon_end)
    
    def train_episode(self, episode: int) -> dict:
        """
        训练一个回合
        
        Args:
            episode: 回合编号
        
        Returns:
            回合统计信息
        """
        # 重置环境
        state = self.env.reset()
        total_reward = 0
        steps = 0
        done = False
        
        episode_losses = []
        
        while not done and steps < self.max_steps:
            # 获取有效动作
            valid_actions = self.env.get_valid_actions()
            
            # 设置当前探索率
            self.agent.epsilon = self.get_epsilon(episode)
            
            # 选择动作
            action = self.agent.select_action(state, valid_actions, training=True)
            
            if action is None:
                break
            
            # 执行动作
            next_state, reward, done, info = self.env.step(action)
            
            # 存储经验
            self.agent.store_transition(state, action, reward, next_state, done)
            
            # 训练
            if len(self.agent.memory) >= self.agent.batch_size:
                loss = self.agent.train_step()
                if loss > 0:
                    episode_losses.append(loss)
            
            # 更新状态
            state = next_state
            total_reward += reward
            steps += 1
        
        # 回合统计
        win = info['status'].value == 1  # GameStatus.WIN
        avg_loss = np.mean(episode_losses) if episode_losses else 0.0
        
        stats = {
            'episode': episode,
            'total_reward': total_reward,
            'steps': steps,
            'win': win,
            'avg_loss': avg_loss,
            'epsilon': self.agent.epsilon,
            'revealed': info.get('revealed', 0),
            'flags': info.get('flags', 0)
        }
        
        return stats
    
    def train(self):
        """主训练循环"""
        print(f"\n开始修复版训练...")
        start_time = time.time()
        
        # 进度条
        pbar = tqdm(range(self.episodes), desc="训练进度")
        
        for episode in pbar:
            # 训练一个回合
            stats = self.train_episode(episode)
            
            # 更新历史记录
            self.rewards_history.append(stats['total_reward'])
            self.wins_history.append(1 if stats['win'] else 0)
            self.steps_history.append(stats['steps'])
            self.losses_history.append(stats['avg_loss'])
            self.epsilon_history.append(stats['epsilon'])
            
            # 更新进度条
            if len(self.wins_history) >= 100:
                win_rate = np.mean(self.wins_history[-100:]) * 100
                avg_reward = np.mean(self.rewards_history[-100:])
            else:
                win_rate = 0
                avg_reward = 0
            
            pbar.set_postfix({
                '奖励': f"{stats['total_reward']:.2f}",
                '胜率': f"{win_rate:.1f}%",
                '步数': stats['steps'],
                '探索率': f"{stats['epsilon']:.3f}"
            })
            
            # 日志输出
            if (episode + 1) % self.log_interval == 0:
                print(f"\n回合 {episode + 1}/{self.episodes}:")
                print(f"  累计奖励: {stats['total_reward']:.2f}")
                print(f"  步数: {stats['steps']}")
                print(f"  结果: {'胜利' if stats['win'] else '失败'}")
                print(f"  平均损失: {stats['avg_loss']:.4f}")
                print(f"  探索率: {stats['epsilon']:.3f}")
                print(f"  最近100回合胜率: {win_rate:.1f}%")
                print(f"  最近100回合平均奖励: {avg_reward:.2f}")
            
            # 保存模型
            if (episode + 1) % self.save_interval == 0:
                model_path = os.path.join(self.save_dir, f"model_episode_{episode+1}.pth")
                self.agent.save(model_path)
                print(f"模型已保存到: {model_path}")
        
        # 训练完成
        training_time = time.time() - start_time
        print(f"\n训练完成!")
        print(f"总训练时间: {training_time:.2f}秒")
        print(f"平均每回合时间: {training_time/self.episodes:.2f}秒")
        
        # 保存最终模型
        final_model_path = os.path.join(self.save_dir, "model_final.pth")
        self.agent.save(final_model_path)
        print(f"最终模型已保存到: {final_model_path}")
        
        # 保存训练统计
        self.save_training_stats()
        
        # 绘制训练曲线
        self.plot_training_curves()
    
    def save_training_stats(self):
        """保存训练统计"""
        stats_path = os.path.join(self.save_dir, "training_stats.npz")
        np.savez(
            stats_path,
            rewards=self.rewards_history,
            wins=self.wins_history,
            steps=self.steps_history,
            losses=self.losses_history,
            epsilon=self.epsilon_history
        )
        print(f"训练统计已保存到: {stats_path}")
    
    def plot_training_curves(self):
        """绘制训练曲线"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        episodes = range(len(self.rewards_history))
        
        # 奖励曲线
        axes[0, 0].plot(episodes, self.rewards_history, alpha=0.3, label='原始')
        if len(self.rewards_history) >= 100:
            smoothed = np.convolve(self.rewards_history, np.ones(100)/100, mode='valid')
            axes[0, 0].plot(range(99, len(self.rewards_history)), smoothed, 
                           label='平滑(100)', linewidth=2, color='red')
        axes[0, 0].set_xlabel('回合')
        axes[0, 0].set_ylabel('累计奖励')
        axes[0, 0].set_title('奖励曲线')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 胜率曲线
        if len(self.wins_history) >= 100:
            win_rates = []
            for i in range(100, len(self.wins_history) + 1):
                win_rates.append(np.mean(self.wins_history[i-100:i]) * 100)
            
            axes[0, 1].plot(range(100, len(self.wins_history) + 1), win_rates, linewidth=2)
            axes[0, 1].set_xlabel('回合')
            axes[0, 1].set_ylabel('胜率 (%)')
            axes[0, 1].set_title('胜率曲线 (100回合滑动平均)')
            axes[0, 1].grid(True, alpha=0.3)
        
        # 探索率曲线
        axes[1, 0].plot(episodes, self.epsilon_history, linewidth=2)
        axes[1, 0].set_xlabel('回合')
        axes[1, 0].set_ylabel('探索率')
        axes[1, 0].set_title('探索率衰减曲线')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 损失曲线
        if any(loss > 0 for loss in self.losses_history):
            axes[1, 1].plot(episodes, self.losses_history, alpha=0.3, label='原始')
            if len(self.losses_history) >= 100:
                smoothed = np.convolve(self.losses_history, np.ones(100)/100, mode='valid')
                axes[1, 1].plot(range(99, len(self.losses_history)), smoothed, 
                               label='平滑(100)', linewidth=2, color='red')
            axes[1, 1].set_xlabel('回合')
            axes[1, 1].set_ylabel('损失')
            axes[1, 1].set_title('损失曲线')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plot_path = os.path.join(self.save_dir, "training_curves.png")
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"训练曲线图已保存到: {plot_path}")
    
    def evaluate(self, num_episodes: int = 100):
        """
        评估模型性能
        
        Args:
            num_episodes: 评估回合数
        """
        print(f"\n评估模型性能 ({num_episodes}回合)...")
        
        original_epsilon = self.agent.epsilon
        self.agent.epsilon = 0.1  # 评估时使用较小的探索率
        
        wins = 0
        total_rewards = []
        total_steps = []
        
        for episode in range(num_episodes):
            state = self.env.reset()
            total_reward = 0
            steps = 0
            done = False
            
            while not done and steps < self.max_steps:
                valid_actions = self.env.get_valid_actions()
                action = self.agent.select_action(state, valid_actions, training=False)
                
                if action is None:
                    break
                
                next_state, reward, done, info = self.env.step(action)
                state = next_state
                total_reward += reward
                steps += 1
            
            if info['status'].value == 1:
                wins += 1
            
            total_rewards.append(total_reward)
            total_steps.append(steps)
        
        # 恢复探索率
        self.agent.epsilon = original_epsilon
        
        # 评估结果
        win_rate = wins / num_episodes * 100
        avg_reward = np.mean(total_rewards)
        avg_steps = np.mean(total_steps)
        
        print(f"\n评估结果:")
        print(f"  胜率: {win_rate:.1f}% ({wins}/{num_episodes})")
        print(f"  平均奖励: {avg_reward:.2f}")
        print(f"  平均步数: {avg_steps:.1f}")
        
        return {
            'win_rate': win_rate,
            'avg_reward': avg_reward,
            'avg_steps': avg_steps
        }


def main():
    """主函数"""
    # 检查GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # 创建训练器
    trainer = FixedMinesweeperTrainer(
        width=9,
        height=9,
        mines=10,
        episodes=3000,  # 3000回合
        max_steps=200,
        learning_rate=0.001,
        gamma=0.99,
        epsilon_start=1.0,
        epsilon_end=0.1,  # 最终探索率10%
        epsilon_decay_steps=2000,  # 2000步内衰减
        memory_size=10000,
        batch_size=64,
        target_update=200,
        save_interval=300,
        log_interval=100,
        device=device
    )
    
    # 开始训练
    trainer.train()
    
    # 评估模型
    print("\n" + "="*50)
    print("模型评估")
    print("="*50)
    trainer.evaluate(num_episodes=50)


if __name__ == "__main__":
    main()