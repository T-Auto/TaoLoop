#!/usr/bin/env python3
"""测试psutil模块"""

try:
    import psutil
    print("psutil导入成功!")
    print(f"psutil版本: {psutil.__version__}")
    
    # 测试一些功能
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    print(f"CPU使用率: {cpu}%")
    print(f"内存使用: {memory.used/1e9:.2f} / {memory.total/1e9:.2f} GB")
    
except ImportError as e:
    print(f"psutil导入失败: {e}")
    print("尝试重新导入...")
    import sys
    print(f"Python路径: {sys.path}")
except Exception as e:
    print(f"其他错误: {e}")