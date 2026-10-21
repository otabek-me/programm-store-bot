import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from database.repositories import admin_user_stats, list_users
from keyboards.admin import user_pagination_keyboard

router = Router(name="admin-users")

USERS_PER_PAGE = 10


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


def _escape(text: str) -> str:
    """Foydalanuvchi kiritgan matnni HTML xavfsiz qilib qaytaradi."""
    return html.escape(text or "", quote=False)


def _status_emoji(is_blocked: int) -> str:
    return "🔴" if is_blocked else "🟢"


def _status_label(is_blocked: int) -> str:
    return "Bloklangan" if is_blocked else "Faol"


def _format_user_row(index: int, row: dict) -> str:
    first_name = _escape(row["first_name"])
    username = row["username"] or "mavjud emas"
    if username != "mavjud emas":
        username = f"@{_escape(username)}"
    return (
        f"<b>{index}. {first_name}</b>\n"
        f"▫️ Username: {username}\n"
        f"▫️ Telegram ID: <code>{row['user_id']}</code>\n"
        f"▫️ Yuklab olishlar: <b>{row['download_count']} ta</b>\n"
        f"▫️ Holati: {_status_emoji(row['is_blocked'])} {_status_label(row['is_blocked'])}"
    )


def _format_users_message(page: int, stats: dict, rows: list[dict], has_next: bool) -> str:
    lines = [
        "<b>👥 FOYDALANUVCHILAR</b>",
        "",
        "<b>📊 Umumiy statistika</b>",
        f"├ Jami: <b>{stats['total']}</b>",
        f"├ Faol: <b>{stats['active']}</b>",
        f"└ Yuklab olishlar: <b>{stats['total_downloads']} ta</b>",
        "",
        "━━━━━━━━━━━━━━━━",
        "",
    ]

    start_index = page * USERS_PER_PAGE
    for i, row in enumerate(rows, start=start_index + 1):
        lines.append(_format_user_row(i, row))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append("")

    total_pages = (stats["total"] + USERS_PER_PAGE - 1) // USERS_PER_PAGE if stats["total"] else 1
    lines.append(f"📄 Sahifa: {page + 1}/{total_pages}")

    return "\n".join(lines)


async def _show_users(callback: CallbackQuery, db_path: str, page: int, answered: bool = False) -> None:
    if not answered:
        await callback.answer()

    stats = await admin_user_stats(db_path)
    rows = await list_users(db_path, limit=USERS_PER_PAGE + 1, offset=page * USERS_PER_PAGE)
    has_next = len(rows) > USERS_PER_PAGE
    visible_rows = rows[:USERS_PER_PAGE]

    if not callback.message:
        return

    text = _format_users_message(page, stats, visible_rows, has_next)
    keyboard = user_pagination_keyboard("admin:users", page, has_next)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
