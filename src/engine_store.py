"""PanSou 搜索引擎的磁盘布局、版本信息和切换状态。

    <bundled_dir>/            镜像自带的版本（只读）
    <data_dir>/engine/
        releases/<rev12>/     在线升级下载的版本：pansou、defaults.env、VERSION.json、LICENSE
        state.json            当前版本、上一个版本、失败过的版本
        cache/                PanSou 的 CACHE_PATH
        work/                 PanSou 进程的工作目录（个别插件会写相对路径）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BUNDLED = "bundled"
BINARY_NAME = "pansou"
RELEASE_FILES = frozenset({BINARY_NAME, "defaults.env", "VERSION.json", "LICENSE"})
REVISION_RE = re.compile(r"^[0-9a-f]{12,40}$")
ENV_LINE_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")


@dataclass(frozen=True)
class EngineBuild:
    """一个可运行的搜索引擎版本。"""

    key: str  # "bundled" 或 12 位提交号
    directory: Path
    revision: str = ""
    committed_at: str = ""
    source: str = ""

    @property
    def binary(self) -> Path:
        return self.directory / BINARY_NAME

    @property
    def short(self) -> str:
        return self.revision[:12] if self.revision else "unknown"

    def label(self) -> str:
        date = self.committed_at[:10] if self.committed_at else "?"
        origin = "镜像自带" if self.key == BUNDLED else "在线升级"
        return f"{self.short}（{date}，{origin}）"

    def defaults(self) -> dict[str, str]:
        return parse_env_file(self.directory / "defaults.env")


@dataclass
class EngineState:
    active: Optional[str] = None
    previous: Optional[str] = None
    bad: list[str] = field(default_factory=list)
    notified: Optional[str] = None


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, NotADirectoryError):
        return values
    for line in lines:
        match = ENV_LINE_RE.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def load_build(key: str, directory: Path) -> Optional[EngineBuild]:
    """读取目录里的版本；可执行文件缺失时返回 None。"""
    binary = directory / BINARY_NAME
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return None
    try:
        meta = json.loads((directory / "VERSION.json").read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except (OSError, ValueError):
        meta = {}
    revision = str(meta.get("revision", ""))
    return EngineBuild(
        key=key,
        directory=directory,
        revision=revision if REVISION_RE.match(revision) else "",
        committed_at=str(meta.get("committed_at", "")),
        source=str(meta.get("source", "")),
    )


class EngineStore:
    def __init__(self, data_dir: Path, bundled_dir: Path):
        self.root = Path(data_dir) / "engine"
        self.bundled_dir = Path(bundled_dir)
        self.releases_dir = self.root / "releases"
        self.cache_dir = self.root / "cache"
        self.work_dir = self.root / "work"
        self.state_path = self.root / "state.json"

    def ensure_dirs(self) -> None:
        for directory in (self.root, self.releases_dir, self.cache_dir, self.work_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # ---- state ----

    def load_state(self) -> EngineState:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return EngineState()
        if not isinstance(raw, dict):
            return EngineState()
        bad = raw.get("bad") if isinstance(raw.get("bad"), list) else []
        return EngineState(
            active=raw.get("active") if isinstance(raw.get("active"), str) else None,
            previous=raw.get("previous") if isinstance(raw.get("previous"), str) else None,
            bad=[item for item in bad if isinstance(item, str)][-20:],
            notified=raw.get("notified") if isinstance(raw.get("notified"), str) else None,
        )

    def save_state(self, state: EngineState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.__dict__, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".state.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.state_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ---- builds ----

    def bundled(self) -> Optional[EngineBuild]:
        return load_build(BUNDLED, self.bundled_dir)

    def release(self, key: str) -> Optional[EngineBuild]:
        if not REVISION_RE.match(key):
            return None
        return load_build(key, self.releases_dir / key)

    def get(self, key: Optional[str]) -> Optional[EngineBuild]:
        if not key:
            return None
        return self.bundled() if key == BUNDLED else self.release(key)

    def preferred(self) -> Optional[EngineBuild]:
        """当前应运行的版本：state 里的 active，不可用时退回镜像自带版本。"""
        state = self.load_state()
        return self.get(state.active) or self.bundled()

    def fallback_for(self, failed: EngineBuild) -> Optional[EngineBuild]:
        state = self.load_state()
        for key in (state.previous, BUNDLED):
            build = self.get(key)
            if build and build.key != failed.key:
                return build
        return None

    def prune(self, keep: set[str]) -> None:
        """只保留 keep 中的已下载版本。"""
        if not self.releases_dir.is_dir():
            return
        for entry in self.releases_dir.iterdir():
            if entry.name not in keep:
                shutil.rmtree(entry, ignore_errors=True)
