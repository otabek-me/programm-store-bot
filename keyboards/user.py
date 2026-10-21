from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Dastur qidirish"), KeyboardButton(text="📂 Kategoriyalar")],
            [KeyboardButton(text="🆕 Yangi dasturlar"), KeyboardButton(text="🔥 Mashhur dasturlar")],
            [KeyboardButton(text="📋 Dasturlar katalogi"), KeyboardButton(text="💬 Dastur so‘rash")],
            [KeyboardButton(text="ℹ️ Bot haqida")],
        ],
        resize_keyboard=True,
    )


def _chunk(rows: list, size: int) -> list[list]:
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def categories_keyboard(rows) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=row["name"], callback_data=f"category:{row['id']}")
        for row in rows
    ]
    keyboard = _chunk(buttons, 2)
    keyboard.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def programs_keyboard(rows, *, page: int = 0, mode: str = "catalog", sort: str = "relevance") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{'⭐ ' if row['is_recommended'] else ''}{row['name']}", callback_data=f"program:{row['id']}")]
        for row in rows[:8]
    ]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{mode}:{sort}:{page - 1}"))
    if len(rows) > 8:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{mode}:{sort}:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    if mode in {"catalog", "search"}:
        sort_prefix = "sort_search" if mode == "search" else "sort"
        buttons.append([
            InlineKeyboardButton(text="⭐ Relevant", callback_data=f"{sort_prefix}:relevance"),
            InlineKeyboardButton(text="🔥 Ommabop", callback_data=f"{sort_prefix}:popular"),
            InlineKeyboardButton(text="🆕 Yangi", callback_data=f"{sort_prefix}:newest"),
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def program_detail(program_id: int, *, admin: bool = False, active: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="⬇️ Yuklab olish", callback_data=f"download:{program_id}")]]
    if admin:
        buttons.append([
            InlineKeyboardButton(
                text="🙈 Yashirish" if active else "👁 Ko‘rsatish",
                callback_data=f"program_toggle:{program_id}",
            ),
            InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"program_delete:{program_id}"),
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def request_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborish", callback_data="request:confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="request:cancel")],
    ])
