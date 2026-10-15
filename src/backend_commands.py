"""内置后端的管理命令：/backend 查看状态，/upgrade 在线升级与回滚。"""
from __future__ import annotations

import asyncio
import html
import time
from typing import Optional

from structlog import get_logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from backend_manager import BackendManager
from backend_store import BackendStore
from backend_updater import BackendUpdater, RemoteRelease, UpgradeError
from config import settings

logger = get_logger()

CALLBACK_PREFIX = "bk:"
CALLBACK_PATTERN = r"^bk:"

_manager: Optional[BackendManager] = None
_updater: Optional[BackendUpdater] = None
_check_task: Optional[asyncio.Task] = None


def _proxy() -> Optional[str]:
    proxies = settings.get_proxies() or {}
    return proxies.get("https://") or proxies.get("http://")


def get_manager() -> Optional[BackendManager]:
    return _manager


def get_updater() -> Optional[BackendUpdater]:
    return _updater


# ============ 生命周期 ============

async def start_backend(application: Application) -> None:
    """启动后端，并按配置开启定时检查更新。"""
    global _manager, _updater, _check_task
    store = BackendStore(settings.data_dir, settings.backend_bundled_dir)
    _manager = BackendManager(
        store, port=settings.backend_port, start_timeout=settings.backend_start_timeout
    )
    _updater = BackendUpdater(store, _manager, repo=settings.backend_update_repo, proxy=_proxy())
    if not await _manager.start():
        logger.error("backend_unavailable_at_startup")
    if settings.backend_update_check_hours > 0:
        _check_task = asyncio.create_task(_periodic_check(application))


async def stop_backend() -> None:
    global _check_task
    if _check_task is not None:
        _check_task.cancel()
        _check_task = None
    if _manager is not None:
        await _manager.stop()


async def _periodic_check(application: Application) -> None:
    await asyncio.sleep(300)  # 启动后先等一会儿，避免和重启风暴叠在一起
    while True:
        try:
            await _check_and_notify(application)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # 定时任务不能因为一次失败停掉
            logger.warning("backend_update_check_failed", error_type=type(exc).__name__)
        await asyncio.sleep(settings.backend_update_check_hours * 3600)


async def _check_and_notify(application: Application) -> None:
    updater = _updater
    if updater is None or updater.busy:
        return
    try:
        release = await updater.check()
    except UpgradeError as exc:
        logger.warning("backend_update_check_failed", reason=str(exc))
        return
    if release is None or not updater.is_newer(release):
        return
    state = updater.store.load_state()
    if release.revision in state.bad:
        return

    if settings.backend_auto_upgrade:
        try:
            build = await updater.install(release)
            text = f"✅ 后端已自动升级到 <code>{build.short}</code>（{release.date}）"
        except UpgradeError as exc:
            text = f"⚠️ 后端自动升级失败：{html.escape(str(exc))}"
        await _notify_admins(application, text, None)
        return

    if state.notified == release.revision:
        return
    text = _release_text(release) + "\n\n要现在升级吗？"
    await _notify_admins(application, text, _upgrade_keyboard(release))
    state = updater.store.load_state()
    state.notified = release.revision
    updater.store.save_state(state)


async def _notify_admins(application: Application, text: str, markup) -> None:
    for admin_id in settings.get_admin_ids():
        try:
            await application.bot.send_message(
                admin_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
        except TelegramError as exc:
            logger.warning("backend_notify_failed", error_type=type(exc).__name__)


# ============ 文案 ============

def _release_text(release: RemoteRelease) -> str:
    current = _manager.build.label() if _manager and _manager.build else "未运行"
    link = (
        f'\n📝 <a href="{html.escape(release.html_url)}">发布说明</a>' if release.html_url else ""
    )
    return (
        "🆕 <b>发现新的后端版本</b>\n\n"
        f"当前：<code>{html.escape(current)}</code>\n"
        f"最新：<code>{release.revision}</code>（{release.date}）{link}"
    )


def _upgrade_keyboard(release: RemoteRelease) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("⬆️ 立即升级", callback_data=f"{CALLBACK_PREFIX}u:{release.revision}"),
            InlineKeyboardButton("取消", callback_data=f"{CALLBACK_PREFIX}x"),
        ]]
    )


def _format_uptime(seconds: float) -> str:
    minutes, _ = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"


async def backend_status_text() -> str:
    manager = _manager
    if manager is None:
        return "⚠️ 后端还没有初始化"
    build = manager.build
    healthy = await manager.healthy() if manager.running else False
    lines = ["🧩 <b>搜索后端</b>", ""]
    lines.append(f"状态：{'✅ 正常' if healthy else '❌ 不可用'}")
    if build is not None:
        lines.append(f"版本：<code>{html.escape(build.label())}</code>")
    if manager.running and manager.started_at:
        lines.append(f"已运行：{_format_uptime(time.monotonic() - manager.started_at)}")
    state = manager.store.load_state()
    previous = manager.store.get(state.previous)
    if previous is not None and (build is None or previous.key != build.key):
        lines.append(f"上一个版本：<code>{html.escape(previous.label())}</code>")
    return "\n".join(lines)


# ============ 命令 ============

async def backend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔️ 该命令仅限管理员使用")
        return
    await update.message.reply_text(await backend_status_text(), parse_mode=ParseMode.HTML)


async def upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔️ 该命令仅限管理员使用")
        return
    if _updater is None:
        await update.message.reply_text("后端还没有初始化，请稍后再试。")
        return

    if context.args and context.args[0].lower() == "rollback":
        message = await update.message.reply_text("⏪ 正在回滚…")
        await _run_rollback(message.edit_text)
        return

    message = await update.message.reply_text("🔍 正在检查新版本…")
    try:
        release = await _updater.check()
    except UpgradeError as exc:
        await message.edit_text(f"⚠️ 检查失败：{exc}")
        return
    if release is None:
        await message.edit_text("还没有可用的后端发布版本。")
        return
    if not _updater.is_newer(release):
        build = _manager.build if _manager else None
        text = f"✅ 已是最新版本：<code>{html.escape(build.label() if build else release.revision)}</code>"
        state = _updater.store.load_state()
        if _updater.store.get(state.previous) is not None:
            text += "\n\n需要退回上一个版本时，用 /upgrade rollback"
        await message.edit_text(text, parse_mode=ParseMode.HTML)
        return
    await message.edit_text(
        _release_text(release) + "\n\n要现在升级吗？",
        parse_mode=ParseMode.HTML,
        reply_markup=_upgrade_keyboard(release),
        disable_web_page_preview=True,
    )


async def backend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not settings.is_admin(query.from_user.id):
        await query.answer("仅限管理员", show_alert=True)
        return
    await query.answer()
    action = (query.data or "")[len(CALLBACK_PREFIX):]

    if action == "x":
        await query.edit_message_text("已取消。")
        return
    if not action.startswith("u:") or _updater is None:
        return

    revision = action[2:]
    release = _updater.latest
    if release is None or release.revision != revision:
        try:
            release = await _updater.check()
        except UpgradeError as exc:
            await query.edit_message_text(f"⚠️ 检查失败：{exc}")
            return
    if release is None or release.revision != revision:
        await query.edit_message_text("这个版本已经不是最新的了，请重新发送 /upgrade")
        return

    async def progress(text: str) -> None:
        try:
            await query.edit_message_text(text)
        except TelegramError:
            pass

    try:
        build = await _updater.install(release, progress)
    except UpgradeError as exc:
        await progress(f"❌ 升级失败：{exc}")
        return
    await query.edit_message_text(
        f"✅ 升级完成，后端现在是 <code>{html.escape(build.label())}</code>\n\n"
        "如有问题可以用 /upgrade rollback 退回上一个版本。",
        parse_mode=ParseMode.HTML,
    )


async def _run_rollback(edit) -> None:
    assert _updater is not None
    try:
        build = await _updater.rollback()
    except UpgradeError as exc:
        await edit(f"❌ 回滚失败：{exc}")
        return
    await edit(
        f"✅ 已回滚到 <code>{html.escape(build.label())}</code>", parse_mode=ParseMode.HTML
    )
