from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _chunk(rows: list, size: int) -> list[list]:
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def admin_menu() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="➕ Dastur qo‘shish", callback_data="admin:add"),
        InlineKeyboardButton(text="📝 Draftni davom ettirish", callback_data="admin:drafts"),
        InlineKeyboardButton(text="📚 Dasturlarni boshqarish", callback_data="admin:programs"),
        InlineKeyboardButton(text="🔍 Dastur qidirish", callback_data="admin:search"),
        InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="admin:categories"),
        InlineKeyboardButton(text="💬 Foydalanuvchi so‘rovlari", callback_data="admin:requests"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="⚙️ Bot sozlamalari", callback_data="admin:settings"),
        InlineKeyboardButton(text="❌ Paneldan chiqish", callback_data="home"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=_chunk(buttons, 2))


def category_admin_keyboard(rows) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"✏️ {row['name']}", callback_data=f"category_edit:{row['id']}"),
         InlineKeyboardButton(text="🗑", callback_data=f"category_delete_confirm:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="➕ Kategoriya qo‘shish", callback_data="category_add")])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def request_admin_keyboard(request_id: int, status: str) -> InlineKeyboardMarkup:
    options = [
        ("⏳ Jarayonda", "in_progress"),
        ("✅ Bajarildi", "completed"),
        ("❌ Rad etildi", "rejected"),
    ]
    buttons = [
        [InlineKeyboardButton(
            text=("✓ " if status == value else "") + label,
            callback_data=f"request_status:{request_id}:{value}",
        )]
        for label, value in options
    ]
    buttons.append([InlineKeyboardButton(text="💬 Javob yozish", callback_data=f"request_reply:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_program_keyboard(program_id: int) -> InlineKeyboardMarkup:
    fields = [
        ("Nomi", "name"),
        ("Tavsif", "description"),
        ("Kategoriyalar", "category_ids"),
        ("Kalit so‘zlar", "keywords"),
        ("Versiya", "version"),
        ("Operatsion tizim", "operating_system"),
        ("Telegram faylini almashtirish", "file"),
    ]
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"admin:edit:{program_id}:{field}")
        for label, field in fields
    ]
    keyboard = _chunk(buttons, 2)
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"admin:program:{program_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
