"""启动并看护内置的 PanSou 后端进程。"""
from __future__ import annotations

import asyncio
import os
import signal
import socket
import time
from pathlib import Path
from typing import Mapping, Optional

import httpx
from dotenv import dotenv_values
from structlog import get_logger

from backend_store import BackendBuild, BackendStore

logger = get_logger()

# 只属于机器人的密钥，不传给后端进程
BOT_ONLY_ENV = frozenset(
    {"TG_BOT_TOKEN", "TMDB_READ_ACCESS_TOKEN", "TMDB_API_KEY"}
)
RESTART_BACKOFF = (1, 2, 5, 10, 30)
# 进程运行超过这个时间再退出，视为偶发故障，重启间隔从头算
STABLE_SECONDS = 300
# 升级后的版本在这段时间内连续崩溃，自动退回上一个版本
CRASH_LOOP_WINDOW = 120
CRASH_LOOP_LIMIT = 3


def build_backend_env(
    build: BackendBuild,
    *,
    port: int,
    cache_dir: Path,
    base_env: Optional[Mapping[str, str]] = None,
    env_file: Optional[Path] = Path(".env"),
) -> dict[str, str]:
    """组合后端环境变量：版本默认值 < .env < 进程环境；端口和缓存目录固定。"""
    env: dict[str, str] = {}
    if env_file is not None and env_file.is_file():
        env.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    env.update(os.environ if base_env is None else base_env)
    for key in BOT_ONLY_ENV:
        env.pop(key, None)
    for key, value in build.defaults().items():
        if not env.get(key):
            env[key] = value
    env["PORT"] = str(port)
    env["CACHE_PATH"] = str(cache_dir)
    return env


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


class BackendManager:
    def __init__(
        self,
        store: BackendStore,
        *,
        port: int,
        start_timeout: float = 60,
        base_env: Optional[Mapping[str, str]] = None,
        env_file: Optional[Path] = Path(".env"),
    ):
        self.store = store
        self.port = port
        self.start_timeout = start_timeout
        self.base_env = base_env
        self.env_file = env_file
        self.url = f"http://127.0.0.1:{port}"
        self.build: Optional[BackendBuild] = None
        self.started_at: Optional[float] = None
        self._process: Optional[asyncio.subprocess.Process] = None
        self._monitor: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._stopping = False
        self._crash_times: list[float] = []

    # ---- 查询 ----

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self.running else None

    async def healthy(self, timeout: float = 3.0) -> bool:
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
                response = await client.get(f"{self.url}/api/health")
            return response.status_code == 200 and response.json().get("status") == "ok"
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    # ---- 生命周期 ----

    async def start(self) -> bool:
        """启动首选版本；失败时退回上一个版本或镜像自带版本。"""
        async with self._lock:
            self._stopping = False
            self.store.ensure_dirs()
            build = self.store.preferred()
            if build is None:
                logger.error("backend_missing", bundled_dir=str(self.store.bundled_dir))
                return False
            if await self._launch(build):
                return True
            fallback = self.store.fallback_for(build)
            if fallback is None:
                return False
            logger.warning("backend_fallback", failed=build.key, fallback=fallback.key)
            return await self._launch(fallback)

    async def stop(self) -> None:
        # 先置位再拿锁：重启等待中的看护任务看到它就会放弃并释放锁
        self._stopping = True
        async with self._lock:
            await self._terminate()

    async def switch(self, build: BackendBuild) -> bool:
        """切换到另一个版本；新版本起不来时恢复原来的版本。"""
        async with self._lock:
            previous = self.build
            await self._terminate()
            if await self._launch(build):
                return True
            logger.warning("backend_switch_failed", target=build.key)
            if previous is not None:
                await self._launch(previous)
            return False

    # ---- 内部 ----

    async def _launch(self, build: BackendBuild) -> bool:
        if port_in_use(self.port):
            logger.error("backend_port_in_use", port=self.port)
            return False
        env = build_backend_env(
            build,
            port=self.port,
            cache_dir=self.store.cache_dir,
            base_env=self.base_env,
            env_file=self.env_file,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                str(build.binary),
                cwd=str(self.store.work_dir),
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            logger.error("backend_exec_failed", build=build.key, error_type=type(exc).__name__)
            return False

        self._process, self.build, self.started_at = process, build, time.monotonic()
        logger.info("backend_starting", build=build.key, revision=build.short, pid=process.pid)

        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            if process.returncode is not None:
                break
            if await self.healthy():
                logger.info("backend_ready", build=build.key, revision=build.short)
                self._monitor = asyncio.create_task(self._watch(process))
                return True
            await asyncio.sleep(0.5)

        logger.error("backend_start_failed", build=build.key, returncode=process.returncode)
        await self._terminate()
        return False

    async def _terminate(self) -> None:
        process, self._process = self._process, None
        monitor, self._monitor = self._monitor, None
        if monitor is not None and monitor is not asyncio.current_task():
            monitor.cancel()
        if process is None or process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def _watch(self, process: asyncio.subprocess.Process) -> None:
        returncode = await process.wait()
        async with self._lock:
            if self._stopping or self._process is not process:
                return
            logger.error("backend_exited", returncode=returncode, build=self.build and self.build.key)
            now = time.monotonic()
            uptime = now - (self.started_at or now)
            self._crash_times = [t for t in self._crash_times if now - t < CRASH_LOOP_WINDOW]
            self._crash_times.append(now)
            if uptime > STABLE_SECONDS:
                self._crash_times = [now]

            build = self.build
            if (
                build is not None
                and len(self._crash_times) >= CRASH_LOOP_LIMIT
                and (fallback := self.store.fallback_for(build)) is not None
            ):
                logger.warning("backend_crash_loop_fallback", failed=build.key, fallback=fallback.key)
                build = fallback
                self._crash_times = []

            attempt = 0
            while not self._stopping and build is not None:
                delay = RESTART_BACKOFF[min(attempt, len(RESTART_BACKOFF) - 1)]
                await asyncio.sleep(delay)
                if self._stopping:
                    return
                if await self._launch(build):
                    return
                attempt += 1
