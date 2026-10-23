import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from database.repositories import (
    broadcast_targets,
    cancel_broadcast_job,
    complete_broadcast_job,
    create_broadcast_job,
    get_broadcast_job,
    get_running_broadcast_job,
    log_broadcast,
    start_broadcast_job,
    update_broadcast_job_progress,
)

logger = logging.getLogger(__name__)

SEND_INTERVAL = 0.035
PROGRESS_WRITE_INTERVAL = 50


async def notify_admins(bot: Bot, admin_ids: frozenset[int], text: str, reply_markup=None) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except TelegramAPIError:
            logger.exception("Administratorga bildirishnoma yuborilmadi: admin_id=%s", admin_id)


async def _check_cancelled(db_path: str, job_id: int) -> bool:
    job = await get_broadcast_job(db_path, job_id)
    return job is not None and job["status"] == "cancelled"


async def _send_single_message(
    bot: Bot, user_id: int, source_chat_id: int, source_message_id: int
) -> bool:
    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
        )
        return True
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 0.5)
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
            )
            return True
        except TelegramAPIError:
            logger.exception("Qayta urinishdan so'ng ham yuborilmadi: user_id=%s", user_id)
            return False
    except TelegramAPIError:
        logger.exception("Xabarni yuborib bo'lmadi: user_id=%s", user_id)
        return False


async def _send_media_group(
    bot: Bot, user_id: int, source_chat_id: int, message_ids: list[int]
) -> bool:
    try:
        first_ok = await _send_single_message(bot, user_id, source_chat_id, message_ids[0])
        if not first_ok:
            return False
        for message_id in message_ids[1:]:
            ok = await _send_single_message(bot, user_id, source_chat_id, message_id)
            if not ok:
                return False
            await asyncio.sleep(SEND_INTERVAL)
        return True
    except TelegramAPIError:
        logger.exception("Media albumni yuborib bo'lmadi: user_id=%s", user_id)
        return False


async def broadcast(
    bot: Bot,
    db_path: str,
    admin_id: int,
    source_chat_id: int,
    source_message_id: int,
    media_group_id: str | None = None,
    message_ids: list[int] | None = None,
) -> tuple[int, int, int]:
    job_id = await create_broadcast_job(
        db_path, admin_id, source_chat_id, source_message_id, media_group_id
    )

    running = await get_running_broadcast_job(db_path, admin_id)
    if running is not None:
        logger.warning(
            "Admin %d already has a running broadcast job %d; refusing duplicate.",
            admin_id, running["id"],
        )
        return 0, 0, 0

    targets = await broadcast_targets(db_path)
    total = len(targets)
    await start_broadcast_job(db_path, job_id, total)

    sent = 0
    failed = 0
    messages_since_progress = 0

    for index, user_id in enumerate(targets):
        if await _check_cancelled(db_path, job_id):
            logger.info(
                "Broadcast %d cancelled by admin %d at user %d", job_id, admin_id, user_id
            )
            break

        try:
            if media_group_id and message_ids:
                ok = await _send_media_group(bot, user_id, source_chat_id, message_ids)
            else:
                ok = await _send_single_message(bot, user_id, source_chat_id, source_message_id)

            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Unexpected error sending to user_id=%s", user_id)
            failed += 1

        messages_since_progress += 1

        if messages_since_progress >= PROGRESS_WRITE_INTERVAL:
            await update_broadcast_job_progress(db_path, job_id, sent, failed)
            messages_since_progress = 0

        if index < len(targets) - 1:
            await asyncio.sleep(SEND_INTERVAL)

    if messages_since_progress > 0:
        await update_broadcast_job_progress(db_path, job_id, sent, failed)

    if not await _check_cancelled(db_path, job_id):
        await complete_broadcast_job(db_path, job_id, sent, failed)

    source_ref = f"message_id={source_message_id}"
    if media_group_id:
        source_ref += f" media_group_id={media_group_id}"
    await log_broadcast(db_path, admin_id, source_ref, total, sent, failed)

    return total, sent, failed


async def stop_broadcast(db_path: str, admin_id: int) -> bool:
    running = await get_running_broadcast_job(db_path, admin_id)
    if running is None:
        return False
    return await cancel_broadcast_job(db_path, running["id"])
