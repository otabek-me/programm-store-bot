from collections import OrderedDict
import logging
from time import monotonic, perf_counter

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.repositories import upsert_user

logger = logging.getLogger(__name__)


class UserTrackingMiddleware(BaseMiddleware):
    tracking_interval = 60.0

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._last_persisted: OrderedDict[int, float] = OrderedDict()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        started_at = perf_counter()
        user = getattr(event, "from_user", None)
        if user is not None:
            now = monotonic()
            last_persisted = self._last_persisted.get(user.id, 0.0)
            if now - last_persisted >= self.tracking_interval:
                await upsert_user(self.db_path, user.id, user.username, user.first_name or "")
                self._last_persisted[user.id] = now
                self._last_persisted.move_to_end(user.id)
                if len(self._last_persisted) > 10000:
                    self._last_persisted.popitem(last=False)
        try:
            return await handler(event, data)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            if duration_ms >= 1000:
                logger.warning(
                    "Slow Telegram update",
                    extra={
                        "duration_ms": duration_ms,
                        "update_type": type(event).__name__,
                    },
                )
