#!/usr/bin/env python3
"""遥感数据集生成器主入口脚本

这是项目的主要入口点，提供命令行接口和程序化接口。

使用方法:
    python main.py input.shp --output-dir output/
    python main.py --interactive
    python main.py --help
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# 导入CLI模块
from src.cli import main

if __name__ == '__main__':
    main()