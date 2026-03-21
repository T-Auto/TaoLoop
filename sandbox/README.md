# 扫雷神经网络训练项目

使用深度强化学习（DQN）训练神经网络玩扫雷游戏。

## 项目结构

```
sandbox/
├── minesweeper_game.py      # 扫雷游戏引擎
├── minesweeper_nn.py        # 神经网络模型
├── train_minesweeper.py     # 训练脚本
├── demo_minesweeper.py      # 演示脚本
├── test_environment.py      # 环境测试
├── requirements.txt         # 依赖列表
└── README.md               # 说明文档
```

## 功能特性

1. **完整的扫雷游戏引擎**：
   - 支持初级（9x9, 10雷）、中级（16x16, 40雷）、高级（30x16, 99雷）难度
   - 游戏状态管理（隐藏、揭开、标记、疑问）
   - 自动揭开空白区域
   - 胜利/失败判断

2. **深度Q网络（DQN）**：
   - 卷积神经网络处理游戏状态
   - 经验回放缓冲区
   - 目标网络稳定训练
   - 探索率衰减（ε-greedy策略）

3. **训练系统**：
   - GPU加速训练
   - 训练进度可视化
   - 模型自动保存
   - 训练统计记录

4. **演示功能**：
   - 交互式游戏演示
   - 决策分析
   - 性能评估

## 安装依赖

使用uv管理Python环境：

```bash
# 安装PyTorch（CUDA 12.4）
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 安装其他依赖
uv pip install numpy matplotlib tqdm scipy scikit-learn
```

## 快速开始

### 1. 测试环境

```bash
uv run python test_environment.py
```

### 2. 开始训练

```bash
# 训练初级难度（9x9, 10雷）
uv run python train_minesweeper.py
```

训练参数可在 `train_minesweeper.py` 中调整：
- `episodes`: 训练回合数（默认5000）
- `batch_size`: 批次大小（默认128）
- `learning_rate`: 学习率（默认0.001）
- `gamma`: 折扣因子（默认0.99）

### 3. 演示训练结果

```bash
# 交互式演示
uv run python demo_minesweeper.py
```

## 文件说明

### minesweeper_game.py
扫雷游戏核心逻辑：
- `MinesweeperGame`: 游戏类，管理游戏状态和规则
- `MinesweeperEnv`: 环境包装器，用于强化学习
- 支持三种难度级别

### minesweeper_nn.py
神经网络模型：
- `MinesweeperCNN`: 卷积神经网络，处理游戏状态
- `DQNAgent`: DQN智能体，包含策略网络和目标网络
- `PrioritizedReplayBuffer`: 优先经验回放缓冲区

### train_minesweeper.py
训练脚本：
- `MinesweeperTrainer`: 训练器类，管理训练循环
- 支持GPU训练
- 自动保存模型和训练统计
- 训练曲线可视化

### demo_minesweeper.py
演示脚本：
- `MinesweeperDemo`: 演示类，展示模型性能
- 交互式游戏界面
- 决策分析功能
- 性能评估统计

## 训练配置

默认训练配置（初级难度）：
- 游戏板: 9x9
- 地雷数: 10
- 训练回合: 5000
- 批次大小: 128
- 学习率: 0.001
- 折扣因子: 0.99
- 探索率: 1.0 → 0.01
- 目标网络更新: 每200步

## 模型保存

训练过程中模型会自动保存到 `models/` 目录：
- `model_episode_500.pth`: 每500回合保存一次
- `model_final.pth`: 最终模型
- `training_stats.npz`: 训练统计
- `training_curves.png`: 训练曲线图

## 性能指标

训练完成后可以评估模型：
- 胜率（Win Rate）
- 平均奖励（Average Reward）
- 平均步数（Average Steps）
- 揭开单元格数（Revealed Cells）

## 扩展功能

1. **调整难度**：修改 `train_minesweeper.py` 中的 `width`, `height`, `mines` 参数
2. **自定义网络**：修改 `MinesweeperCNN` 类的网络结构
3. **高级策略**：实现Double DQN、Dueling DQN等改进算法
4. **多GPU训练**：使用 `torch.nn.DataParallel` 加速训练

## 注意事项

1. **GPU内存**：训练过程中监控GPU内存使用，适当调整批次大小
2. **训练时间**：5000回合训练约需1-2小时（取决于GPU性能）
3. **探索策略**：初始探索率较高，随着训练逐渐降低
4. **模型选择**：选择胜率最高的模型进行部署

## 故障排除

1. **CUDA错误**：确保安装正确版本的PyTorch（CUDA 12.4）
2. **内存不足**：减小批次大小或游戏板尺寸
3. **训练不稳定**：调整学习率或增加目标网络更新频率
4. **胜率低**：增加训练回合数或调整网络结构

## 许可证

本项目仅供学习和研究使用。