#!/usr/bin/env python3
"""PanSou Bot - 网盘资源搜索 Telegram 机器人。

    python main.py                 运行机器人
    python main.py check-engine   只启动搜索引擎做一次健康检查（镜像自检用）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    if sys.argv[1:] == ["check-engine"]:
        from engine_check import main as check_engine

        sys.exit(check_engine())

    from bot import run

    run()
