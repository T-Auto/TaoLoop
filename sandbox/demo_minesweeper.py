"""
扫雷演示脚本
展示训练好的神经网络如何玩扫雷
"""
import torch
import numpy as np
import time
import os
import sys

from minesweeper_game import MinesweeperEnv
from minesweeper_nn import DQNAgent


class MinesweeperDemo:
    """扫雷演示类"""
    
    def __init__(self, model_path: str = None, difficulty: str = 'beginner'):
        """
        初始化演示
        
        Args:
            model_path: 模型路径
            difficulty: 难度级别 ('beginner', 'intermediate', 'expert')
        """
        # 难度设置
        difficulty_settings = {
            'beginner': (9, 9, 10),
            'intermediate': (16, 16, 40),
            'expert': (30, 16, 99)
        }
        
        if difficulty not in difficulty_settings:
            print(f"未知难度: {difficulty}，使用 beginner")
            difficulty = 'beginner'
        
        width, height, mines = difficulty_settings[difficulty]
        
        # 创建环境
        self.env = MinesweeperEnv(width, height, mines)
        self.width = width
        self.height = height
        self.mines = mines
        
        # 创建智能体
        action_dim = width * height * 2
        self.agent = DQNAgent(
            height=height,
            width=width,
            action_dim=action_dim,
            epsilon_start=0.0,  # 关闭探索
            epsilon_end=0.0,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )
        
        # 加载模型
        if model_path and os.path.exists(model_path):
            self.agent.load(model_path)
            print(f"已加载模型: {model_path}")
        else:
            print("警告: 未找到模型，使用随机策略")
        
        # 关闭探索
        self.agent.epsilon = 0.0
        
        # 统计
        self.stats = {
            'wins': 0,
            'losses': 0,
            'total_games': 0,
            'total_reward': 0,
            'total_steps': 0
        }
    
    def play_game(self, render: bool = True, delay: float = 0.5) -> dict:
        """
        玩一局游戏
        
        Args:
            render: 是否渲染游戏
            delay: 渲染延迟（秒）
        
        Returns:
            游戏结果统计
        """
        # 重置环境
        state = self.env.reset()
        total_reward = 0
        steps = 0
        done = False
        
        if render:
            print("\n" + "="*50)
            print(f"开始新游戏: {self.width}x{self.height}, 地雷: {self.mines}")
            print("="*50)
            self.env.render()
            time.sleep(delay)
        
        while not done and steps < 200:
            # 获取有效动作
            valid_actions = self.env.get_valid_actions()
            
            if not valid_actions:
                break
            
            # 选择动作
            action = self.agent.select_action(state, valid_actions, training=False)
            
            if action is None:
                break
            
            # 执行动作
            next_state, reward, done, info = self.env.step(action)
            
            # 更新统计
            state = next_state
            total_reward += reward
            steps += 1
            
            # 渲染
            if render:
                action_type = "揭开" if action[2] == 0 else "标记"
                print(f"\n步骤 {steps}: 在({action[0]}, {action[1]}) {action_type}")
                print(f"奖励: {reward:.2f}, 累计奖励: {total_reward:.2f}")
                self.env.render()
                time.sleep(delay)
        
        # 游戏结果
        win = info['status'].value == 1  # GameStatus.WIN
        
        if render:
            print("\n" + "="*50)
            if win:
                print("🎉 胜利！")
            else:
                print("💥 失败！")
            print(f"总步数: {steps}")
            print(f"总奖励: {total_reward:.2f}")
            print(f"揭开单元格: {info.get('revealed', 0)}")
            print(f"标记: {info.get('flags', 0)}")
            print("="*50)
        
        # 更新全局统计
        self.stats['total_games'] += 1
        self.stats['total_reward'] += total_reward
        self.stats['total_steps'] += steps
        
        if win:
            self.stats['wins'] += 1
        else:
            self.stats['losses'] += 1
        
        # 返回游戏结果
        result = {
            'win': win,
            'total_reward': total_reward,
            'steps': steps,
            'revealed': info.get('revealed', 0),
            'flags': info.get('flags', 0)
        }
        
        return result
    
    def play_multiple_games(self, num_games: int = 10, render_first: bool = True):
        """
        玩多局游戏
        
        Args:
            num_games: 游戏局数
            render_first: 是否渲染第一局游戏
        """
        print(f"\n开始玩 {num_games} 局扫雷...")
        print(f"难度: {self.width}x{self.height}, 地雷: {self.mines}")
        
        results = []
        
        for game_idx in range(num_games):
            render = render_first and (game_idx == 0)
            
            print(f"\n游戏 {game_idx + 1}/{num_games}:")
            result = self.play_game(render=render, delay=0.3)
            results.append(result)
            
            if not render:
                status = "胜利" if result['win'] else "失败"
                print(f"  结果: {status}, 步数: {result['steps']}, 奖励: {result['total_reward']:.2f}")
        
        # 统计结果
        self._print_statistics(results)
    
    def _print_statistics(self, results: list):
        """打印统计信息"""
        wins = sum(1 for r in results if r['win'])
        win_rate = wins / len(results) * 100
        
        avg_reward = np.mean([r['total_reward'] for r in results])
        avg_steps = np.mean([r['steps'] for r in results])
        avg_revealed = np.mean([r['revealed'] for r in results])
        
        print("\n" + "="*50)
        print("游戏统计:")
        print("="*50)
        print(f"总游戏数: {len(results)}")
        print(f"胜利: {wins}")
        print(f"失败: {len(results) - wins}")
        print(f"胜率: {win_rate:.1f}%")
        print(f"平均奖励: {avg_reward:.2f}")
        print(f"平均步数: {avg_steps:.1f}")
        print(f"平均揭开单元格: {avg_revealed:.1f}")
        
        # 全局统计
        if self.stats['total_games'] > len(results):
            global_win_rate = self.stats['wins'] / self.stats['total_games'] * 100
            print(f"\n全局统计 (所有游戏):")
            print(f"  总游戏数: {self.stats['total_games']}")
            print(f"  胜率: {global_win_rate:.1f}%")
            print(f"  平均奖励: {self.stats['total_reward'] / self.stats['total_games']:.2f}")
    
    def analyze_decision(self, state: np.ndarray):
        """
        分析决策过程
        
        Args:
            state: 游戏状态
        """
        print("\n决策分析:")
        
        # 获取所有有效动作
        valid_actions = self.env.get_valid_actions()
        
        if not valid_actions:
            print("没有有效动作")
            return
        
        # 获取Q值
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.agent.device)
            q_values = self.agent.policy_net(state_tensor)[0]
        
        # 分析每个有效动作
        print(f"有效动作数量: {len(valid_actions)}")
        print("\n前10个最佳动作:")
        
        action_scores = []
        for action in valid_actions:
            x, y, action_type = action
            action_idx = (y * self.width + x) * 2 + action_type
            q_value = q_values[action_idx].item()
            action_scores.append((action, q_value))
        
        # 按Q值排序
        action_scores.sort(key=lambda x: x[1], reverse=True)
        
        for i, (action, q_value) in enumerate(action_scores[:10]):
            x, y, action_type = action
            action_str = "揭开" if action_type == 0 else "标记"
            print(f"  {i+1}. ({x}, {y}) {action_str}: Q值 = {q_value:.4f}")
        
        # 选择最佳动作
        best_action, best_q = action_scores[0]
        x, y, action_type = best_action
        action_str = "揭开" if action_type == 0 else "标记"
        
        print(f"\n推荐动作: 在({x}, {y}) {action_str}")
        print(f"置信度: {best_q:.4f}")
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n" + "="*50)
        print("交互式扫雷演示")
        print("="*50)
        
        while True:
            print("\n选项:")
            print("  1. 玩一局游戏")
            print("  2. 玩多局游戏")
            print("  3. 分析当前决策")
            print("  4. 显示当前游戏板")
            print("  5. 重置游戏")
            print("  6. 退出")
            
            choice = input("\n请选择 (1-6): ").strip()
            
            if choice == '1':
                self.play_game(render=True, delay=0.5)
            
            elif choice == '2':
                try:
                    num_games = int(input("游戏局数 (默认10): ") or "10")
                    self.play_multiple_games(num_games=num_games, render_first=True)
                except ValueError:
                    print("请输入有效数字")
            
            elif choice == '3':
                # 获取当前状态
                state = self.env.game.get_observation()
                self.analyze_decision(state)
            
            elif choice == '4':
                print("\n当前游戏板:")
                self.env.render()
            
            elif choice == '5':
                self.env.reset()
                print("游戏已重置")
            
            elif choice == '6':
                print("退出演示")
                break
            
            else:
                print("无效选择")


def find_latest_model(model_dir: str = "models") -> str:
    """查找最新的模型文件"""
    if not os.path.exists(model_dir):
        return None
    
    # 查找所有模型文件
    model_files = []
    for root, dirs, files in os.walk(model_dir):
        for file in files:
            if file.endswith('.pth'):
                model_files.append(os.path.join(root, file))
    
    if not model_files:
        return None
    
    # 按修改时间排序
    model_files.sort(key=os.path.getmtime, reverse=True)
    return model_files[0]


def main():
    """主函数"""
    print("扫雷神经网络演示")
    print("="*50)
    
    # 检查GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # 查找模型
    model_path = find_latest_model("models")
    
    if model_path:
        print(f"找到模型: {model_path}")
    else:
        print("警告: 未找到训练好的模型")
        print("请先运行 train_minesweeper.py 训练模型")
        model_path = None
    
    # 选择难度
    print("\n选择难度:")
    print("  1. 初级 (9x9, 10个地雷)")
    print("  2. 中级 (16x16, 40个地雷)")
    print("  3. 高级 (30x16, 99个地雷)")
    
    difficulty_map = {'1': 'beginner', '2': 'intermediate', '3': 'expert'}
    choice = input("请选择 (1-3, 默认1): ").strip() or '1'
    
    difficulty = difficulty_map.get(choice, 'beginner')
    
    # 创建演示
    demo = MinesweeperDemo(model_path=model_path, difficulty=difficulty)
    
    # 运行演示
    demo.interactive_demo()


if __name__ == "__main__":
    main()