import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent,
)
from aiogram.fsm.storage.memory import MemoryStorage

from admin import broadcasts, categories, dashboard, programs, requests, settings, users
from config import load_config
from database.db import close_postgres_pools, init_db
from handlers import catalog, downloads, fallback, requests as user_requests, search, start
from middlewares.throttling import ThrottlingMiddleware
from middlewares.user_tracking import UserTrackingMiddleware
from utils.permissions import AdminOnly
from utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    logger.error(
        "Yangilanmani qayta ishlashda kutilmagan xato",
        exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
    )
    update = event.update
    message = update.message
    if message is not None:
        await message.answer("Kutilmagan xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko‘ring.")
    elif update.callback_query is not None:
        try:
            await update.callback_query.answer("Xatolik yuz berdi. Qayta urinib ko‘ring.", show_alert=True)
        except TelegramAPIError:
            logger.info("Eskirgan callback uchun javob yuborilmadi.")
    return True


async def main() -> None:
    config = load_config()
    configure_logging(config.log_level)
    await init_db(config.database_url)

    bot = Bot(token=config.bot_token)
    common_commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="about", description="Bot haqida"),
        BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
    ]
    await bot.set_my_commands(common_commands, scope=BotCommandScopeDefault())
    for admin_id in config.admin_ids:
        await bot.set_my_commands(
            [*common_commands, BotCommand(command="admin", description="Admin panel")],
            scope=BotCommandScopeChat(chat_id=admin_id),
        )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["db_path"] = config.database_url
    dispatcher["admin_ids"] = config.admin_ids
    dispatcher["allowed_file_extensions"] = config.allowed_file_extensions

    tracking = UserTrackingMiddleware(config.database_url)
    throttling = ThrottlingMiddleware()
    dispatcher.message.outer_middleware(tracking)
    dispatcher.callback_query.outer_middleware(tracking)
    dispatcher.message.middleware(throttling)
    dispatcher.callback_query.middleware(throttling)
    dispatcher.errors.register(on_error)

    for router in (start.router, user_requests.router, search.router, catalog.router, downloads.router):
        dispatcher.include_router(router)

    for router in (
        dashboard.router, programs.router, categories.router, requests.router,
        users.router, broadcasts.router, settings.router,
    ):
        router.message.filter(AdminOnly(config.admin_ids))
        router.callback_query.filter(AdminOnly(config.admin_ids))
        dispatcher.include_router(router)
    dispatcher.include_router(fallback.router)

    logger.info(
        "Bot ishga tushmoqda. Adminlar soni: %d, Fly machine: %s",
        len(config.admin_ids),
        os.getenv("FLY_MACHINE_ID", "local"),
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await close_postgres_pools()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
