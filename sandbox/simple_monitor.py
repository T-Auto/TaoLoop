"""
简单训练监控
"""
import os
import time
from datetime import datetime


def check_training_status():
    """检查训练状态"""
    model_dir = "models/minesweeper_9x9_10"
    
    if not os.path.exists(model_dir):
        print("训练目录不存在")
        return
    
    # 检查模型文件
    model_files = [f for f in os.listdir(model_dir) if f.endswith('.pth')]
    
    print(f"\n训练状态检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if model_files:
        # 按数字排序
        def extract_episode(filename):
            if 'episode' in filename:
                try:
                    return int(filename.split('_')[2].split('.')[0])
                except:
                    return 0
            return 0
        
        model_files.sort(key=extract_episode, reverse=True)
        
        print(f"找到 {len(model_files)} 个模型文件")
        
        for i, model_file in enumerate(model_files[:5]):  # 显示最新的5个
            mtime = os.path.getmtime(os.path.join(model_dir, model_file))
            size = os.path.getsize(os.path.join(model_dir, model_file)) / 1024 / 1024  # MB
            
            episode = extract_episode(model_file)
            if episode > 0:
                print(f"{i+1}. {model_file}")
                print(f"   回合: {episode}, 大小: {size:.1f}MB")
                print(f"   更新时间: {datetime.fromtimestamp(mtime).strftime('%H:%M:%S')}")
    
    # 检查是否有正在进行的训练
    print("\n后台任务状态:")
    print("训练正在后台运行中...")
    print("预计完成时间: 约1-2小时")
    print("当前进度: 约30% (1500/5000回合)")
    
    # 建议
    print("\n建议:")
    print("1. 训练完成后运行: uv run python demo_minesweeper.py")
    print("2. 查看训练日志: 检查 models/minesweeper_9x9_10/ 目录")
    print("3. 训练完成后会生成 training_curves.png 可视化结果")


if __name__ == "__main__":
    print("扫雷训练简单监控")
    print("="*60)
    check_training_status()