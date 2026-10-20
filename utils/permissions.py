from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message


def is_admin(user_id: int | None, admin_ids: frozenset[int]) -> bool:
    return user_id is not None and user_id in admin_ids


class AdminOnly(BaseFilter):
    def __init__(self, admin_ids: frozenset[int]) -> None:
        self.admin_ids = admin_ids

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return is_admin(user.id if user else None, self.admin_ids)
