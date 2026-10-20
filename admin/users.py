from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.repositories import list_users
from keyboards.pagination import page_keyboard

router = Router(name="admin-users")


@router.callback_query(F.data == "admin:users")
async def users_page_first(callback: CallbackQuery, db_path: str) -> None:
    await _show_users(callback, db_path, 0)


@router.callback_query(F.data.startswith("admin:users:"))
async def users_page(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        page = max(int(callback.data.rsplit(":", 1)[1]), 0)
    except ValueError:
        return
    await _show_users(callback, db_path, page, answered=True)


async def _show_users(callback: CallbackQuery, db_path: str, page: int, answered: bool = False) -> None:
    if not answered:
        await callback.answer()
    rows = await list_users(db_path, limit=10, offset=page * 10)
    if not callback.message:
        return
    lines = [
        f"{row['first_name']} (@{row['username'] or '—'}) · ID {row['user_id']} · "
        f"⬇ {row['download_count']} · {'bloklangan' if row['is_blocked'] else 'faol'}"
        for row in rows
    ]
    await callback.message.answer(
        "\n".join(lines) if lines else "Foydalanuvchilar topilmadi.",
        reply_markup=page_keyboard("admin:users", page, len(rows) == 10),
    )
