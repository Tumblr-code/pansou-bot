#!/usr/bin/env python3
"""PanSou Bot - 网盘搜索 Telegram 机器人，内置 PanSou 后端。

    python main.py                 运行机器人
    python main.py check-backend   只启动内置后端做一次健康检查（镜像自检用）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    if sys.argv[1:] == ["check-backend"]:
        from backend_check import main as check_backend

        sys.exit(check_backend())

    from bot import run

    run()
