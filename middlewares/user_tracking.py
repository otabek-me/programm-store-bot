from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.repositories import upsert_user


class UserTrackingMiddleware(BaseMiddleware):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if user is not None:
            await upsert_user(self.db_path, user.id, user.username, user.first_name or "")
        return await handler(event, data)
