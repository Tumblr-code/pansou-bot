from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import io
import json
import os
import socket
import sys
import tarfile
from pathlib import Path

import httpx
import pytest

import backend_manager
from backend_manager import BackendManager, build_backend_env
from backend_store import BUNDLED, BackendStore, load_build
from backend_updater import (
    BackendUpdater,
    UpgradeError,
    extract_release,
    parse_sums,
    pick_release,
)

FAKE_BACKEND = f"""#!{sys.executable}
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

if os.environ.get("FAKE_FAIL") or {{fail}}:
    sys.exit(3)
with open(os.path.join(os.getcwd(), "env.json"), "w") as fh:
    json.dump(dict(os.environ), fh)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({{"status": "ok", "rev": "{{rev}}"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def write_build(directory: Path, revision: str, *, fail: bool = False, defaults: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "pansou"
    binary.write_text(FAKE_BACKEND.replace("{fail}", str(fail)).replace("{rev}", revision))
    binary.chmod(0o755)
    (directory / "VERSION.json").write_text(
        json.dumps({"revision": revision, "committed_at": "2026-10-12T14:00:52+08:00"})
    )
    (directory / "defaults.env").write_text(defaults)
    return directory


def make_manager(tmp_path: Path, **kwargs) -> BackendManager:
    store = BackendStore(tmp_path / "data", tmp_path / "bundled")
    return BackendManager(
        store, port=free_port(), start_timeout=10, base_env={"PATH": os.environ["PATH"]},
        env_file=None, **kwargs,
    )


REV_A = "a" * 40
REV_B = "b" * 40


# ---------- 环境变量 ----------

def test_backend_env_drops_bot_secrets_and_fills_defaults(tmp_path: Path) -> None:
    build = load_build(BUNDLED, write_build(tmp_path / "b", REV_A, defaults="CHANNELS=x,y\nTZ=UTC\n"))
    assert build is not None
    env = build_backend_env(
        build,
        port=9999,
        cache_dir=tmp_path / "cache",
        base_env={"TG_BOT_TOKEN": "secret", "TMDB_API_KEY": "k", "CHANNELS": "", "TZ": "Asia/Shanghai"},
        env_file=None,
    )
    assert "TG_BOT_TOKEN" not in env and "TMDB_API_KEY" not in env
    assert env["CHANNELS"] == "x,y"  # 空值视为未设置
    assert env["TZ"] == "Asia/Shanghai"  # 用户设置优先
    assert env["PORT"] == "9999"
    assert env["CACHE_PATH"] == str(tmp_path / "cache")


# ---------- 进程管理 ----------

@pytest.mark.asyncio
async def test_manager_starts_bundled_and_stops(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    assert await manager.start()
    assert manager.build.key == BUNDLED and await manager.healthy()
    env = json.loads((manager.store.work_dir / "env.json").read_text())
    assert env["CACHE_PATH"] == str(manager.store.cache_dir)
    await manager.stop()
    assert not manager.running and not await manager.healthy()


@pytest.mark.asyncio
async def test_broken_active_release_falls_back_to_bundled(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    store = manager.store
    write_build(store.releases_dir / REV_B[:12], REV_B, fail=True)
    state = store.load_state()
    state.active = REV_B[:12]
    store.save_state(state)
    try:
        assert await manager.start()
        assert manager.build.key == BUNDLED
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_failed_switch_restores_running_version(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    broken = load_build("x", write_build(tmp_path / "broken", REV_B, fail=True))
    try:
        assert await manager.start()
        assert not await manager.switch(broken)
        assert manager.build.key == BUNDLED and await manager.healthy()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_crashed_backend_is_restarted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_manager, "RESTART_BACKOFF", (0.1,))
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    try:
        assert await manager.start()
        first = manager.pid
        os.kill(first, 9)
        for _ in range(100):
            await asyncio.sleep(0.1)
            if manager.pid not in (None, first) and await manager.healthy():
                break
        assert manager.pid not in (None, first)
    finally:
        await manager.stop()


# ---------- 发布解析与解压 ----------

def _release_json(tag: str, arch: str = "amd64", **extra) -> dict:
    base = f"https://example.invalid/{tag}"
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "html_url": base,
        "assets": [
            {"name": f"pansou-linux-{arch}.tar.gz", "browser_download_url": f"{base}/pansou-linux-{arch}.tar.gz"},
            {"name": "SHA256SUMS", "browser_download_url": f"{base}/SHA256SUMS"},
        ],
        **extra,
    }


def test_pick_release_skips_unrelated_and_incomplete_releases() -> None:
    releases = [
        {"tag_name": "v2.0.0", "assets": []},
        _release_json("backend-20261013-" + "c" * 12, prerelease=True),
        _release_json("backend-20261012-" + "b" * 12, arch="arm64"),
        _release_json("backend-20261011-" + "a" * 12),
    ]
    picked = pick_release(releases, "amd64")
    assert picked.revision == "a" * 12 and picked.date == "2026-10-11"
    assert pick_release(releases, "arm64").revision == "b" * 12


def test_pick_release_prefers_newest_upstream_date_over_publish_order() -> None:
    releases = [
        _release_json("backend-20261001-" + "d" * 12, published_at="2026-10-14T00:00:00Z"),
        _release_json("backend-20261011-" + "a" * 12, published_at="2026-10-12T00:00:00Z"),
    ]
    assert pick_release(releases, "amd64").revision == "a" * 12


def test_parse_sums() -> None:
    digest = "0" * 64
    assert parse_sums(f"{digest}  pansou-linux-amd64.tar.gz\nbad line\n") == {
        "pansou-linux-amd64.tar.gz": digest
    }


def _tar(files: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo(symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "files,symlink",
    [
        ({"../pansou": b"x", "VERSION.json": b"{}"}, None),
        ({"pansou": b"x", "VERSION.json": b"{}", "extra.sh": b"x"}, None),
        ({"pansou": b"x", "VERSION.json": b"{}"}, "LICENSE"),
        ({"pansou": b"x"}, None),
    ],
)
def test_extract_rejects_unexpected_entries(tmp_path: Path, files, symlink) -> None:
    archive = tmp_path / "a.tar.gz"
    archive.write_bytes(_tar(files, symlink=symlink))
    with pytest.raises(UpgradeError):
        extract_release(archive, tmp_path / "out")


# ---------- 在线升级 ----------

def _release_archive(tmp_path: Path, revision: str, *, fail: bool = False) -> bytes:
    src = write_build(tmp_path / f"src-{revision[:4]}", revision, fail=fail)
    return _tar({name: (src / name).read_bytes() for name in ("pansou", "VERSION.json", "defaults.env")})


def _github(tmp_path: Path, revision: str, archive: bytes, *, digest: str | None = None):
    tag = f"backend-20261012-{revision[:12]}"
    release = _release_json(tag, arch=backend_updater_arch())
    name = release["assets"][0]["name"]
    sums = f"{digest or hashlib.sha256(archive).hexdigest()}  {name}\n".encode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[release])
        if request.url.path.endswith("/SHA256SUMS"):
            return httpx.Response(200, content=sums)
        if request.url.path.endswith(".tar.gz"):
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def backend_updater_arch() -> str:
    from backend_updater import current_arch

    return current_arch()


@pytest.mark.asyncio
async def test_upgrade_installs_switches_and_rolls_back(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    transport = _github(tmp_path, REV_B, _release_archive(tmp_path, REV_B))
    updater = BackendUpdater(manager.store, manager, repo="o/r", transport=transport)
    steps: list[str] = []

    async def progress(text: str) -> None:
        steps.append(text)

    try:
        assert await manager.start()
        release = await updater.check()
        assert release.revision == REV_B[:12] and updater.is_newer(release)
        older = dataclasses.replace(release, date="2026-10-01")
        assert not updater.is_newer(older)  # 比当前版本（2026-10-12）旧

        build = await updater.install(release, progress)
        assert build.key == REV_B[:12] and manager.build.key == REV_B[:12]
        assert len(steps) == 3
        state = manager.store.load_state()
        assert (state.active, state.previous) == (REV_B[:12], BUNDLED)
        assert not updater.is_newer(release)

        # 重启后仍运行升级后的版本
        await manager.stop()
        assert await manager.start() and manager.build.key == REV_B[:12]

        back = await updater.rollback()
        assert back.key == BUNDLED and manager.build.key == BUNDLED
        assert manager.store.load_state().active == BUNDLED
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_upgrade_with_bad_checksum_keeps_running_version(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    transport = _github(tmp_path, REV_B, _release_archive(tmp_path, REV_B), digest="0" * 64)
    updater = BackendUpdater(manager.store, manager, repo="o/r", transport=transport)
    try:
        assert await manager.start()
        release = await updater.check()
        with pytest.raises(UpgradeError, match="SHA256"):
            await updater.install(release)
        assert manager.build.key == BUNDLED and await manager.healthy()
        assert not (manager.store.releases_dir / REV_B[:12]).exists()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_upgrade_to_broken_build_restores_and_remembers(tmp_path: Path) -> None:
    write_build(tmp_path / "bundled", REV_A)
    manager = make_manager(tmp_path)
    transport = _github(tmp_path, REV_B, _release_archive(tmp_path, REV_B, fail=True))
    updater = BackendUpdater(manager.store, manager, repo="o/r", transport=transport)
    try:
        assert await manager.start()
        release = await updater.check()
        with pytest.raises(UpgradeError, match="健康检查"):
            await updater.install(release)
        assert manager.build.key == BUNDLED and await manager.healthy()
        assert REV_B[:12] in manager.store.load_state().bad
        with pytest.raises(UpgradeError, match="跳过"):
            await updater.install(release)
    finally:
        await manager.stop()
