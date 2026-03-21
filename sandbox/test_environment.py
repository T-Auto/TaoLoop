"""
测试扫雷环境和神经网络
"""
import torch
import numpy as np
from minesweeper_game import MinesweeperGame, MinesweeperEnv
from minesweeper_nn import MinesweeperCNN, DQNAgent


def test_game_environment():
    """测试游戏环境"""
    print("测试扫雷游戏环境...")
    
    # 创建游戏
    game = MinesweeperGame(9, 9, 10)
    
    # 测试重置
    obs = game.reset()
    print(f"观察形状: {obs.shape}")
    print(f"观察范围: [{obs.min():.2f}, {obs.max():.2f}]")
    
    # 测试揭开
    print("\n测试揭开单元格 (4, 4):")
    obs, reward, done = game.reveal(4, 4)
    print(f"奖励: {reward:.2f}, 结束: {done}")
    game.render()
    
    # 测试标记
    print("\n测试标记单元格 (0, 0):")
    obs, reward, done = game.toggle_flag(0, 0)
    print(f"奖励: {reward:.2f}, 结束: {done}")
    game.render()
    
    # 测试有效动作
    valid_actions = game.get_valid_actions()
    print(f"\n有效动作数量: {len(valid_actions)}")
    if valid_actions:
        print(f"前5个有效动作: {valid_actions[:5]}")
    
    return True


def test_neural_network():
    """测试神经网络"""
    print("\n测试神经网络...")
    
    # 创建模型
    model = MinesweeperCNN(9, 9, 162)
    
    # 测试前向传播
    batch_size = 4
    dummy_input = torch.randn(batch_size, 3, 9, 9)
    output = model(dummy_input)
    
    print(f"输入形状: {dummy_input.shape}")
    print(f"输出形状: {output.shape}")
    print(f"输出范围: [{output.min():.4f}, {output.max():.4f}]")
    
    # 测试GPU
    if torch.cuda.is_available():
        print("\n测试GPU支持...")
        model = model.cuda()
        dummy_input = dummy_input.cuda()
        output = model(dummy_input)
        print(f"GPU输出形状: {output.shape}")
        print("GPU测试通过!")
    
    return True


def test_dqn_agent():
    """测试DQN智能体"""
    print("\n测试DQN智能体...")
    
    # 创建智能体
    agent = DQNAgent(
        height=9,
        width=9,
        action_dim=162,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    
    # 创建测试状态
    env = MinesweeperEnv(9, 9, 10)
    state = env.reset()
    valid_actions = env.get_valid_actions()
    
    print(f"状态形状: {state.shape}")
    print(f"有效动作数量: {len(valid_actions)}")
    
    # 测试动作选择
    action = agent.select_action(state, valid_actions, training=True)
    print(f"选择的动作: {action}")
    
    # 测试经验存储
    next_state, reward, done, _ = env.step(action)
    agent.store_transition(state, action, reward, next_state, done)
    
    print(f"存储经验后记忆大小: {len(agent.memory)}")
    print(f"探索率: {agent.epsilon:.3f}")
    
    # 测试训练
    if len(agent.memory) >= agent.batch_size:
        loss = agent.train_step()
        print(f"训练损失: {loss:.4f}")
    
    return True


def test_training_loop():
    """测试训练循环"""
    print("\n测试训练循环...")
    
    from train_minesweeper import MinesweeperTrainer
    
    # 创建小型训练器
    trainer = MinesweeperTrainer(
        width=5,
        height=5,
        mines=3,
        episodes=10,
        max_steps=50,
        memory_size=1000,
        batch_size=32,
        save_interval=5,
        log_interval=2,
        device="cpu"  # 使用CPU进行快速测试
    )
    
    # 测试一个回合
    print("测试一个训练回合...")
    stats = trainer.train_episode(0)
    
    print(f"回合统计:")
    print(f"  累计奖励: {stats['total_reward']:.2f}")
    print(f"  步数: {stats['steps']}")
    print(f"  结果: {'胜利' if stats['win'] else '失败'}")
    print(f"  平均损失: {stats['avg_loss']:.4f}")
    
    return True


def main():
    """主测试函数"""
    print("="*50)
    print("扫雷神经网络测试套件")
    print("="*50)
    
    tests_passed = 0
    total_tests = 4
    
    try:
        # 测试1: 游戏环境
        if test_game_environment():
            tests_passed += 1
            print("✓ 游戏环境测试通过")
    except Exception as e:
        print(f"✗ 游戏环境测试失败: {e}")
    
    try:
        # 测试2: 神经网络
        if test_neural_network():
            tests_passed += 1
            print("✓ 神经网络测试通过")
    except Exception as e:
        print(f"✗ 神经网络测试失败: {e}")
    
    try:
        # 测试3: DQN智能体
        if test_dqn_agent():
            tests_passed += 1
            print("✓ DQN智能体测试通过")
    except Exception as e:
        print(f"✗ DQN智能体测试失败: {e}")
    
    try:
        # 测试4: 训练循环
        if test_training_loop():
            tests_passed += 1
            print("✓ 训练循环测试通过")
    except Exception as e:
        print(f"✗ 训练循环测试失败: {e}")
    
    # 总结
    print("\n" + "="*50)
    print(f"测试结果: {tests_passed}/{total_tests} 通过")
    
    if tests_passed == total_tests:
        print("所有测试通过! 可以开始训练。")
        print("\n运行以下命令开始训练:")
        print("  uv run python train_minesweeper.py")
        print("\n运行以下命令进行演示:")
        print("  uv run python demo_minesweeper.py")
    else:
        print("部分测试失败，请检查错误。")
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)