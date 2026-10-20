import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from database.repositories import broadcast_targets, log_broadcast

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, admin_ids: frozenset[int], text: str, reply_markup=None) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except TelegramAPIError:
            logger.exception("Administratorga bildirishnoma yuborilmadi: admin_id=%s", admin_id)


async def broadcast(bot: Bot, db_path: str, admin_id: int, text: str) -> tuple[int, int, int]:
    targets = await broadcast_targets(db_path)
    sent = 0
    failed = 0
    for user_id in targets:
        try:
            try:
                await bot.send_message(user_id, text)
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 0.5)
                await bot.send_message(user_id, text)
            sent += 1
        except TelegramAPIError:
            failed += 1
            logger.warning("Ommaviy xabar yuborilmadi: user_id=%s", user_id)
        await asyncio.sleep(0.05)
    await log_broadcast(db_path, admin_id, text, len(targets), sent, failed)
    return len(targets), sent, failed
