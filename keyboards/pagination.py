from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def page_keyboard(prefix: str, page: int, has_next: bool) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{page - 1}"))
    if has_next:
        buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{page + 1}"))
    rows = [buttons] if buttons else []
    rows.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
