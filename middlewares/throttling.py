import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, interval: float = 0.7) -> None:
        self.interval = interval
        self._last_call: dict[int, float] = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is not None:
            now = time.monotonic()
            previous = self._last_call.get(user.id, 0.0)
            if now - previous < self.interval:
                if isinstance(event, CallbackQuery):
                    await event.answer("Biroz kutib, qayta urinib ko‘ring.", show_alert=False)
                elif isinstance(event, Message):
                    await event.answer("Iltimos, biroz kutib qayta urinib ko‘ring.")
                return None
            self._last_call[user.id] = now
        return await handler(event, data)
