"""从 GitHub Releases 在线升级内置后端。

发布约定（由 .github/workflows/backend-release.yml 生成）：
  标签       backend-<YYYYMMDD>-<12 位上游提交号>
  资产       pansou-linux-<amd64|arm64>.tar.gz、SHA256SUMS
压缩包里只允许 pansou、defaults.env、VERSION.json、LICENSE 四个普通文件。
"""
from __future__ import annotations

import asyncio
import hashlib
import platform
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx
from structlog import get_logger

from backend_manager import BackendManager
from backend_store import BUNDLED, RELEASE_FILES, BackendBuild, BackendStore, load_build

logger = get_logger()

TAG_RE = re.compile(r"^backend-(\d{8})-([0-9a-f]{12})$")
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_SUMS_BYTES = 64 * 1024
ARCHES = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}

Progress = Callable[[str], Awaitable[None]]


class UpgradeError(Exception):
    """可直接展示给管理员的升级失败原因。"""


@dataclass(frozen=True)
class RemoteRelease:
    tag: str
    revision: str  # 12 位
    date: str  # YYYY-MM-DD
    archive_url: str
    archive_name: str
    sums_url: str
    html_url: str


def current_arch() -> str:
    arch = ARCHES.get(platform.machine().lower())
    if arch is None:
        raise UpgradeError(f"不支持的 CPU 架构：{platform.machine()}")
    return arch


def pick_release(releases: list, arch: str) -> Optional[RemoteRelease]:
    """找上游提交日期最新的完整后端版本（不按发布先后：补发的旧版本不能顶替新版本）。"""
    archive_name = f"pansou-linux-{arch}.tar.gz"
    candidates = []
    for item in releases:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            continue
        match = TAG_RE.match(str(item.get("tag_name", "")))
        if not match:
            continue
        assets = {
            asset.get("name"): asset.get("browser_download_url")
            for asset in item.get("assets") or []
            if isinstance(asset, dict)
        }
        if archive_name in assets and "SHA256SUMS" in assets:
            day = match.group(1)
            release = RemoteRelease(
                tag=item["tag_name"],
                revision=match.group(2),
                date=f"{day[:4]}-{day[4:6]}-{day[6:]}",
                archive_url=assets[archive_name],
                archive_name=archive_name,
                sums_url=assets["SHA256SUMS"],
                html_url=str(item.get("html_url", "")),
            )
            candidates.append((day, str(item.get("published_at") or ""), release))
    if not candidates:
        return None
    return max(candidates, key=lambda c: (c[0], c[1]))[2]


def parse_sums(text: str) -> dict[str, str]:
    sums = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            sums[parts[1].lstrip("*")] = parts[0]
    return sums


def extract_release(archive: Path, target: Path) -> None:
    """只解出白名单里的普通文件，拒绝路径穿越、链接和设备文件。"""
    target.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = set()
        for member in members:
            name = member.name.removeprefix("./")
            if name in ("", "."):
                continue
            if name not in RELEASE_FILES or not member.isfile():
                raise UpgradeError(f"压缩包里有不允许的条目：{member.name}")
            names.add(name)
            source = tar.extractfile(member)
            if source is None:
                raise UpgradeError(f"无法读取 {member.name}")
            with source, open(target / name, "wb") as out:
                shutil.copyfileobj(source, out)
    if not {"pansou", "VERSION.json"} <= names:
        raise UpgradeError("压缩包缺少 pansou 或 VERSION.json")
    (target / "pansou").chmod(0o755)


class BackendUpdater:
    def __init__(
        self,
        store: BackendStore,
        manager: BackendManager,
        *,
        repo: str,
        proxy: Optional[str] = None,
        api_base: str = "https://api.github.com",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.store = store
        self.manager = manager
        self.repo = repo
        self.proxy = proxy
        self.api_base = api_base.rstrip("/")
        self.transport = transport
        self.latest: Optional[RemoteRelease] = None
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            proxy=None if self.transport else self.proxy,
            transport=self.transport,
            timeout=httpx.Timeout(timeout, connect=15.0),
            follow_redirects=True,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "pansou-bot"},
        )

    async def check(self) -> Optional[RemoteRelease]:
        try:
            async with self._client(20) as client:
                response = await client.get(
                    f"{self.api_base}/repos/{self.repo}/releases", params={"per_page": 30}
                )
                response.raise_for_status()
                releases = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpgradeError(f"无法访问 GitHub：{type(exc).__name__}") from exc
        if not isinstance(releases, list):
            raise UpgradeError("GitHub 返回的数据格式不对")
        self.latest = pick_release(releases, current_arch())
        return self.latest

    def is_newer(self, release: RemoteRelease) -> bool:
        """发布的提交日期不早于当前版本、且不是同一个提交时，视为新版本。"""
        current = self.manager.build
        if current is None:
            return True
        if current.revision.startswith(release.revision):
            return False
        return not current.committed_at or release.date >= current.committed_at[:10]

    async def _download(self, client: httpx.AsyncClient, url: str, dest: Path, limit: int) -> str:
        digest = hashlib.sha256()
        size = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(dest, "wb") as out:
                async for chunk in response.aiter_bytes(1 << 16):
                    size += len(chunk)
                    if size > limit:
                        raise UpgradeError("下载的文件超过大小上限")
                    digest.update(chunk)
                    out.write(chunk)
        return digest.hexdigest()

    async def install(self, release: RemoteRelease, progress: Optional[Progress] = None) -> BackendBuild:
        """下载、校验、切换；切换失败时原版本继续运行。"""

        async def report(text: str) -> None:
            if progress is not None:
                await progress(text)

        if self._lock.locked():
            raise UpgradeError("已有升级正在进行")
        async with self._lock:
            state = self.store.load_state()
            if release.revision in state.bad:
                raise UpgradeError("这个版本之前启动失败过，已跳过")
            self.store.ensure_dirs()
            old = self.manager.build
            if old is not None and old.key == release.revision:
                raise UpgradeError("已经在运行这个版本")
            target = self.store.releases_dir / release.revision
            with tempfile.TemporaryDirectory(dir=self.store.root, prefix=".download-") as tmp:
                tmp_dir = Path(tmp)
                await report("⬇️ 正在下载…")
                try:
                    async with self._client(300) as client:
                        sums_path = tmp_dir / "SHA256SUMS"
                        await self._download(client, release.sums_url, sums_path, MAX_SUMS_BYTES)
                        archive = tmp_dir / release.archive_name
                        actual = await self._download(
                            client, release.archive_url, archive, MAX_ARCHIVE_BYTES
                        )
                except httpx.HTTPError as exc:
                    raise UpgradeError(f"下载失败：{type(exc).__name__}") from exc

                await report("🔐 正在校验…")
                expected = parse_sums(sums_path.read_text(encoding="utf-8", errors="replace"))
                if expected.get(release.archive_name) != actual:
                    raise UpgradeError("SHA256 校验不通过，已放弃")
                staging = tmp_dir / "release"
                try:
                    extract_release(archive, staging)
                except (tarfile.TarError, OSError) as exc:
                    raise UpgradeError(f"解压失败：{type(exc).__name__}") from exc
                build = load_build(release.revision, staging)
                if build is None or not build.revision.startswith(release.revision):
                    raise UpgradeError("版本信息和发布标签不一致")
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(staging), target)

            build = load_build(release.revision, target)
            assert build is not None
            await report("🔄 正在切换后端…")
            if not await self.manager.switch(build):
                state = self.store.load_state()
                state.bad = [*state.bad, release.revision][-20:]
                self.store.save_state(state)
                shutil.rmtree(target, ignore_errors=True)
                raise UpgradeError("新版本没能通过健康检查，已恢复原版本")

            state = self.store.load_state()
            state.previous = old.key if old else BUNDLED
            state.active = build.key
            self.store.save_state(state)
            self.store.prune({k for k in (state.active, state.previous) if k and k != BUNDLED})
            logger.info("backend_upgraded", revision=build.short, previous=state.previous)
            return build

    async def rollback(self) -> BackendBuild:
        if self._lock.locked():
            raise UpgradeError("已有升级正在进行")
        async with self._lock:
            state = self.store.load_state()
            current = self.manager.build
            target = self.store.get(state.previous) or self.store.bundled()
            if target is None or (current is not None and target.key == current.key):
                raise UpgradeError("没有可以回滚的版本")
            if not await self.manager.switch(target):
                raise UpgradeError("回滚目标没能通过健康检查，原版本继续运行")
            state.previous = current.key if current else None
            state.active = target.key
            self.store.save_state(state)
            logger.info("backend_rolled_back", revision=target.short)
            return target
