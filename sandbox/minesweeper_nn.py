"""
扫雷神经网络模型
使用PyTorch实现深度Q网络（DQN）来学习玩扫雷
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from collections import deque
import random
from typing import Tuple, List, Optional
import math


class MinesweeperCNN(nn.Module):
    """扫雷卷积神经网络"""
    
    def __init__(self, height: int = 9, width: int = 9, action_dim: int = 162):
        """
        初始化CNN
        
        Args:
            height: 游戏高度
            width: 游戏宽度
            action_dim: 动作空间维度
        """
        super(MinesweeperCNN, self).__init__()
        
        # 输入形状: (batch_size, 3, height, width)
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        
        # 计算全连接层输入大小
        conv_output_height = height
        conv_output_width = width
        fc_input_size = 128 * conv_output_height * conv_output_width
        
        self.fc1 = nn.Linear(fc_input_size, 512)
        self.fc2 = nn.Linear(512, 256)
        self.fc3 = nn.Linear(256, action_dim)
        
        # 初始化权重
        self._initialize_weights()
    
    def _initialize_weights(self):
        """初始化网络权重"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: 输入张量，形状为 (batch_size, 3, height, width)
        
        Returns:
            动作价值张量，形状为 (batch_size, action_dim)
        """
        # 卷积层
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        
        # 展平
        x = x.view(x.size(0), -1)
        
        # 全连接层
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        
        return x


class DQNAgent:
    """深度Q学习智能体"""
    
    def __init__(
        self,
        height: int = 9,
        width: int = 9,
        action_dim: int = 162,
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        memory_size: int = 10000,
        batch_size: int = 64,
        target_update: int = 100,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        初始化DQN智能体
        
        Args:
            height: 游戏高度
            width: 游戏宽度
            action_dim: 动作空间维度
            learning_rate: 学习率
            gamma: 折扣因子
            epsilon_start: 初始探索率
            epsilon_end: 最小探索率
            epsilon_decay: 探索率衰减
            memory_size: 经验回放缓冲区大小
            batch_size: 训练批次大小
            target_update: 目标网络更新频率
            device: 计算设备
        """
        self.height = height
        self.width = width
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update = target_update
        self.device = device
        
        # 创建策略网络和目标网络
        self.policy_net = MinesweeperCNN(height, width, action_dim).to(device)
        self.target_net = MinesweeperCNN(height, width, action_dim).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        # 优化器
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        
        # 经验回放缓冲区
        self.memory = deque(maxlen=memory_size)
        
        # 训练步数计数器
        self.steps_done = 0
        
        # 损失函数
        self.criterion = nn.MSELoss()
    
    def select_action(
        self, 
        state: np.ndarray, 
        valid_actions: List[Tuple[int, int, int]],
        training: bool = True
    ) -> Tuple[int, int, int]:
        """
        选择动作
        
        Args:
            state: 当前状态
            valid_actions: 有效动作列表
            training: 是否在训练模式
        
        Returns:
            选择的动作 (x, y, action_type)
        """
        if not valid_actions:
            return None
        
        # 探索：随机选择动作
        if training and random.random() < self.epsilon:
            return random.choice(valid_actions)
        
        # 利用：选择Q值最大的动作
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            
            # 将动作映射到Q值索引
            action_indices = []
            for action in valid_actions:
                x, y, action_type = action
                action_idx = (y * self.width + x) * 2 + action_type
                action_indices.append(action_idx)
            
            # 选择有效动作中Q值最大的
            valid_q_values = q_values[0, action_indices]
            best_idx = torch.argmax(valid_q_values).item()
            return valid_actions[best_idx]
    
    def store_transition(
        self,
        state: np.ndarray,
        action: Tuple[int, int, int],
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """
        存储经验到回放缓冲区
        
        Args:
            state: 当前状态
            action: 执行的动作
            reward: 获得的奖励
            next_state: 下一个状态
            done: 是否结束
        """
        if action is None:
            return
        
        # 将动作转换为索引
        x, y, action_type = action
        action_idx = (y * self.width + x) * 2 + action_type
        
        self.memory.append((
            state.copy(),
            action_idx,
            reward,
            next_state.copy(),
            done
        ))
    
    def train_step(self) -> float:
        """
        执行一次训练步骤
        
        Returns:
            损失值
        """
        if len(self.memory) < self.batch_size:
            return 0.0
        
        # 从回放缓冲区采样
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        # 转换为张量
        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones = torch.FloatTensor(dones).unsqueeze(1).to(self.device)
        
        # 计算当前Q值
        current_q_values = self.policy_net(states).gather(1, actions)
        
        # 计算目标Q值
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0].unsqueeze(1)
            target_q_values = rewards + (1 - dones) * self.gamma * next_q_values
        
        # 计算损失
        loss = self.criterion(current_q_values, target_q_values)
        
        # 反向传播
        self.optimizer.zero_grad()
        loss.backward()
        
        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        
        self.optimizer.step()
        
        # 更新探索率
        if self.epsilon > self.epsilon_end:
            self.epsilon *= self.epsilon_decay
        
        # 更新目标网络
        self.steps_done += 1
        if self.steps_done % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())
        
        return loss.item()
    
    def save(self, path: str):
        """保存模型"""
        torch.save({
            'policy_net_state_dict': self.policy_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'steps_done': self.steps_done,
            'memory': list(self.memory)
        }, path)
    
    def load(self, path: str):
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
        self.target_net.load_state_dict(checkpoint['target_net_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.epsilon = checkpoint['epsilon']
        self.steps_done = checkpoint['steps_done']
        self.memory = deque(checkpoint['memory'], maxlen=len(self.memory))
    
    def get_action_distribution(self, state: np.ndarray) -> np.ndarray:
        """
        获取动作分布
        
        Args:
            state: 当前状态
        
        Returns:
            动作概率分布
        """
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            probabilities = F.softmax(q_values, dim=1)
            return probabilities.cpu().numpy()[0]


class PrioritizedReplayBuffer:
    """优先经验回放缓冲区"""
    
    def __init__(self, capacity: int, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.size = 0
    
    def push(self, state, action, reward, next_state, done, priority: float = None):
        """添加经验"""
        if priority is None:
            priority = 1.0 if len(self.buffer) == 0 else np.max(self.priorities[:self.size])
        
        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)
        
        self.priorities[self.position] = priority ** self.alpha
        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
    
    def sample(self, batch_size: int, beta: float = 0.4):
        """采样批次"""
        if self.size == 0:
            return None
        
        # 计算采样概率
        probs = self.priorities[:self.size] / np.sum(self.priorities[:self.size])
        
        # 采样索引
        indices = np.random.choice(self.size, batch_size, p=probs)
        
        # 计算重要性采样权重
        weights = (self.size * probs[indices]) ** (-beta)
        weights = weights / np.max(weights)
        
        # 获取批次数据
        batch = [self.buffer[idx] for idx in indices]
        states, actions, rewards, next_states, dones = zip(*batch)
        
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones),
            indices,
            weights
        )
    
    def update_priorities(self, indices, priorities):
        """更新优先级"""
        for idx, priority in zip(indices, priorities):
            self.priorities[idx] = priority ** self.alpha


def test_game_visualization():
    """测试游戏可视化"""
    from minesweeper_game import MinesweeperGame
    
    print("测试扫雷游戏...")
    game = MinesweeperGame(9, 9, 10)
    
    # 初始状态
    print("\n初始状态:")
    game.render()
    
    # 揭开一些单元格
    print("\n揭开(4, 4):")
    obs, reward, done = game.reveal(4, 4)
    game.render()
    print(f"奖励: {reward}, 结束: {done}")
    
    # 标记一个单元格
    print("\n标记(0, 0):")
    obs, reward, done = game.toggle_flag(0, 0)
    game.render()
    print(f"奖励: {reward}, 结束: {done}")
    
    # 显示所有地雷
    print("\n显示所有地雷:")
    game.render(show_mines=True)


if __name__ == "__main__":
    test_game_visualization()