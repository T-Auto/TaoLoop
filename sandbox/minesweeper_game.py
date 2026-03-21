"""
扫雷游戏引擎
支持不同难度级别，提供游戏状态和交互接口
"""
import numpy as np
import random
from enum import Enum
from typing import Tuple, List, Optional
import copy


class CellState(Enum):
    """单元格状态"""
    HIDDEN = 0      # 未揭开
    REVEALED = 1    # 已揭开
    FLAGGED = 2     # 已标记为地雷
    QUESTION = 3    # 标记为疑问


class GameStatus(Enum):
    """游戏状态"""
    PLAYING = 0     # 游戏中
    WIN = 1         # 胜利
    LOSE = 2        # 失败


class MinesweeperGame:
    """扫雷游戏类"""
    
    def __init__(self, width: int = 9, height: int = 9, mines: int = 10):
        """
        初始化扫雷游戏
        
        Args:
            width: 游戏宽度
            height: 游戏高度
            mines: 地雷数量
        """
        self.width = width
        self.height = height
        self.mines = mines
        self.reset()
    
    def reset(self):
        """重置游戏"""
        # 初始化游戏板
        self.board = np.zeros((self.height, self.width), dtype=int)  # 0-8: 周围雷数，-1: 地雷
        self.state = np.full((self.height, self.width), CellState.HIDDEN.value, dtype=int)
        self.game_status = GameStatus.PLAYING
        self.first_click = True
        self.revealed_count = 0
        self.flag_count = 0
        self.mine_positions = []
        
        # 初始时没有地雷，等待第一次点击
        return self.get_observation()
    
    def place_mines(self, safe_x: int, safe_y: int):
        """放置地雷，避开安全区域"""
        positions = []
        attempts = 0
        
        while len(positions) < self.mines and attempts < 1000:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            
            # 避开第一次点击的单元格及其周围8格
            if abs(x - safe_x) <= 1 and abs(y - safe_y) <= 1:
                continue
            
            if (x, y) not in positions:
                positions.append((x, y))
                self.board[y, x] = -1  # 标记为地雷
        
        self.mine_positions = positions
        
        # 计算每个单元格周围的雷数
        for y in range(self.height):
            for x in range(self.width):
                if self.board[y, x] != -1:
                    self.board[y, x] = self._count_adjacent_mines(x, y)
    
    def _count_adjacent_mines(self, x: int, y: int) -> int:
        """计算单元格周围的地雷数量"""
        count = 0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.board[ny, nx] == -1:
                        count += 1
        return count
    
    def reveal(self, x: int, y: int) -> Tuple[np.ndarray, float, bool]:
        """
        揭开单元格
        
        Returns:
            observation: 游戏观察状态
            reward: 奖励值
            done: 游戏是否结束
        """
        if self.game_status != GameStatus.PLAYING:
            return self.get_observation(), 0.0, True
        
        # 如果是第一次点击，放置地雷
        if self.first_click:
            self.place_mines(x, y)
            self.first_click = False
        
        # 检查是否越界
        if not (0 <= x < self.width and 0 <= y < self.height):
            return self.get_observation(), -0.1, False
        
        # 检查单元格状态
        if self.state[y, x] == CellState.REVEALED.value:
            return self.get_observation(), -0.05, False
        
        # 揭开单元格
        self.state[y, x] = CellState.REVEALED.value
        self.revealed_count += 1
        
        # 检查是否踩到地雷
        if self.board[y, x] == -1:
            self.game_status = GameStatus.LOSE
            # 揭开所有地雷
            for mx, my in self.mine_positions:
                self.state[my, mx] = CellState.REVEALED.value
            return self.get_observation(), -10.0, True
        
        # 如果是空白单元格，自动揭开周围
        if self.board[y, x] == 0:
            self._reveal_adjacent(x, y)
        
        # 检查是否胜利
        if self._check_win():
            self.game_status = GameStatus.WIN
            # 标记所有剩余的地雷
            for mx, my in self.mine_positions:
                if self.state[my, mx] != CellState.REVEALED.value:
                    self.state[my, mx] = CellState.FLAGGED.value
            return self.get_observation(), 10.0, True
        
        # 正常揭开奖励
        reward = 0.1 if self.board[y, x] > 0 else 0.2
        return self.get_observation(), reward, False
    
    def _reveal_adjacent(self, x: int, y: int):
        """递归揭开空白单元格周围的单元格"""
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.state[ny, nx] == CellState.HIDDEN.value:
                        self.state[ny, nx] = CellState.REVEALED.value
                        self.revealed_count += 1
                        if self.board[ny, nx] == 0:
                            self._reveal_adjacent(nx, ny)
    
    def toggle_flag(self, x: int, y: int) -> Tuple[np.ndarray, float, bool]:
        """
        切换标记状态（标记/取消标记地雷）
        
        Returns:
            observation: 游戏观察状态
            reward: 奖励值
            done: 游戏是否结束
        """
        if self.game_status != GameStatus.PLAYING:
            return self.get_observation(), 0.0, True
        
        # 检查是否越界
        if not (0 <= x < self.width and 0 <= y < self.height):
            return self.get_observation(), -0.1, False
        
        # 已揭开的单元格不能标记
        if self.state[y, x] == CellState.REVEALED.value:
            return self.get_observation(), -0.05, False
        
        # 切换标记状态
        current_state = self.state[y, x]
        
        if current_state == CellState.HIDDEN.value:
            self.state[y, x] = CellState.FLAGGED.value
            self.flag_count += 1
            reward = 0.5 if self.board[y, x] == -1 else -0.5
        elif current_state == CellState.FLAGGED.value:
            self.state[y, x] = CellState.QUESTION.value
            self.flag_count -= 1
            reward = -0.3 if self.board[y, x] == -1 else 0.3
        else:  # QUESTION -> HIDDEN
            self.state[y, x] = CellState.HIDDEN.value
            reward = 0.0
        
        # 检查是否胜利（所有地雷都被正确标记）
        if self._check_win():
            self.game_status = GameStatus.WIN
            return self.get_observation(), 10.0, True
        
        return self.get_observation(), reward, False
    
    def _check_win(self) -> bool:
        """检查是否胜利"""
        # 所有非地雷单元格都已揭开
        for y in range(self.height):
            for x in range(self.width):
                if self.board[y, x] != -1 and self.state[y, x] != CellState.REVEALED.value:
                    return False
        
        # 所有地雷都被正确标记或揭开
        for mx, my in self.mine_positions:
            if self.state[my, mx] not in [CellState.FLAGGED.value, CellState.REVEALED.value]:
                return False
        
        return True
    
    def get_observation(self) -> np.ndarray:
        """
        获取游戏观察状态
        
        Returns:
            3通道的观察状态:
            - 通道0: 单元格内容 (-1: 地雷, 0-8: 周围雷数)
            - 通道1: 单元格状态 (0: 隐藏, 1: 揭开, 2: 标记, 3: 疑问)
            - 通道2: 游戏状态编码
        """
        # 创建3通道观察
        obs = np.zeros((3, self.height, self.width), dtype=np.float32)
        
        # 通道0: 单元格内容（对神经网络隐藏未揭开的地雷）
        for y in range(self.height):
            for x in range(self.width):
                if self.state[y, x] == CellState.REVEALED.value:
                    obs[0, y, x] = self.board[y, x]  # 显示实际内容
                else:
                    obs[0, y, x] = 0  # 隐藏内容
        
        # 通道1: 单元格状态
        obs[1] = self.state.astype(np.float32) / 3.0  # 归一化到[0, 1]
        
        # 通道2: 游戏状态编码
        if self.game_status == GameStatus.PLAYING:
            obs[2, :, :] = 0.0
        elif self.game_status == GameStatus.WIN:
            obs[2, :, :] = 1.0
        else:  # LOSE
            obs[2, :, :] = -1.0
        
        return obs
    
    def get_valid_actions(self) -> List[Tuple[int, int, int]]:
        """
        获取有效动作列表
        
        Returns:
            动作列表，每个动作为 (x, y, action_type)
            action_type: 0=揭开, 1=标记
        """
        actions = []
        
        if self.game_status != GameStatus.PLAYING:
            return actions
        
        for y in range(self.height):
            for x in range(self.width):
                # 只能对未揭开的单元格进行操作
                if self.state[y, x] != CellState.REVEALED.value:
                    actions.append((x, y, 0))  # 揭开动作
                    actions.append((x, y, 1))  # 标记动作
        
        return actions
    
    def render(self, show_mines: bool = False):
        """渲染游戏板（文本模式）"""
        symbols = {
            -1: '💣', 0: ' ', 1: '1', 2: '2', 3: '3', 
            4: '4', 5: '5', 6: '6', 7: '7', 8: '8'
        }
        
        state_symbols = {
            CellState.HIDDEN.value: '■',
            CellState.REVEALED.value: ' ',
            CellState.FLAGGED.value: '⚑',
            CellState.QUESTION.value: '?'
        }
        
        print("+" + "-" * (self.width * 2 - 1) + "+")
        for y in range(self.height):
            row = "|"
            for x in range(self.width):
                if show_mines and self.board[y, x] == -1:
                    row += "💣 "
                elif self.state[y, x] == CellState.REVEALED.value:
                    row += symbols[self.board[y, x]] + " "
                else:
                    row += state_symbols[self.state[y, x]] + " "
            row = row.rstrip() + "|"
            print(row)
        print("+" + "-" * (self.width * 2 - 1) + "+")
        
        status_text = {
            GameStatus.PLAYING: f"游戏中 - 已揭开: {self.revealed_count}, 标记: {self.flag_count}",
            GameStatus.WIN: "胜利！🎉",
            GameStatus.LOSE: "失败！💥"
        }
        print(status_text[self.game_status])


class MinesweeperEnv:
    """扫雷环境包装器，用于强化学习"""
    
    def __init__(self, width: int = 9, height: int = 9, mines: int = 10):
        self.game = MinesweeperGame(width, height, mines)
        self.action_space = width * height * 2  # 每个单元格有2种操作
        self.observation_space = (3, height, width)
        
    def reset(self):
        """重置环境"""
        return self.game.reset()
    
    def step(self, action: Tuple[int, int, int]):
        """
        执行动作
        
        Args:
            action: (x, y, action_type)
        
        Returns:
            observation, reward, done, info
        """
        x, y, action_type = action
        
        if action_type == 0:  # 揭开
            obs, reward, done = self.game.reveal(x, y)
        else:  # 标记
            obs, reward, done = self.game.toggle_flag(x, y)
        
        info = {
            'status': self.game.game_status,
            'revealed': self.game.revealed_count,
            'flags': self.game.flag_count
        }
        
        return obs, reward, done, info
    
    def get_valid_actions(self):
        """获取有效动作"""
        return self.game.get_valid_actions()
    
    def render(self):
        """渲染游戏"""
        self.game.render()


# 预定义难度级别
DIFFICULTY_LEVELS = {
    'beginner': (9, 9, 10),
    'intermediate': (16, 16, 40),
    'expert': (30, 16, 99)
}