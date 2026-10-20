from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from database.repositories import admin_stats
from keyboards.admin import admin_menu

router = Router(name="admin-dashboard")


async def _dashboard_text(db_path: str) -> str:
    stats = await admin_stats(db_path)
    popular = "\n".join(
        f"  {row['name']} — {row['downloads']} yuklab olish"
        for row in stats["popular"]
    ) or "  Hozircha ma’lumot yo‘q"
    recent = "\n".join(f"  {row['name']}" for row in stats["recent"]) or "  Hozircha ma’lumot yo‘q"
    return (
        "📊 Administrator paneli\n\n"
        f"Jami dasturlar: {stats['programs']} (faol {stats['active']}, yashirin {stats['hidden']})\n"
        f"Kategoriyalar: {stats['categories']}\n"
        f"Foydalanuvchilar: {stats['users']} (bugun yangi {stats['new_users']})\n"
        f"Yuklab olishlar: {stats['downloads']} (bugun {stats['today_downloads']})\n"
        f"Kutilayotgan so‘rovlar: {stats['pending_requests']}\n\n"
        f"Eng ommabop:\n{popular}\n\nOxirgi qo‘shilgan:\n{recent}"
    )


@router.message(Command("admin"))
async def admin_command(message: Message, db_path: str) -> None:
    await message.answer(await _dashboard_text(db_path), reply_markup=admin_menu())


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(await _dashboard_text(db_path), reply_markup=admin_menu())


@router.callback_query(F.data == "admin:stats")
async def admin_statistics(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(await _dashboard_text(db_path), reply_markup=admin_menu())
