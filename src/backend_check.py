"""启动内置后端、等待健康检查通过后退出，用于镜像构建后的自检。"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from backend_manager import BackendManager
from backend_store import BackendStore


async def _check(bundled_dir: Path, port: int) -> int:
    with tempfile.TemporaryDirectory(prefix="pansou-check-") as tmp:
        store = BackendStore(Path(tmp), bundled_dir)
        build = store.bundled()
        if build is None:
            print(f"FAIL: no backend binary in {bundled_dir}")
            return 1
        manager = BackendManager(store, port=port, start_timeout=60, env_file=None)
        ok = await manager.start()
        await manager.stop()
        print(f"{'OK' if ok else 'FAIL'}: backend {build.short} ({build.committed_at or '?'})")
        return 0 if ok else 1


def main() -> int:
    bundled = Path(os.environ.get("BACKEND_BUNDLED_DIR", "/opt/pansou"))
    port = int(os.environ.get("BACKEND_CHECK_PORT", "18888"))
    return asyncio.run(_check(bundled, port))
