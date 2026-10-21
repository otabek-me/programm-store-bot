from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.user import main_menu
from database.repositories import remove_draft
from utils.permissions import is_admin

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Dasturlar kutubxonasiga xush kelibsiz.\n"
        "Kerakli dasturni qidiring yoki katalogni ko‘rib chiqing.",
        reply_markup=main_menu(),
    )


@router.message(Command("about"))
@router.message(F.text == "ℹ️ Bot haqida")
async def about(message: Message) -> None:
    await message.answer(
        "Bu bot dasturlar katalogini topish va Telegram orqali olish uchun xizmat qiladi.\n"
        "Faqat tarqatishga ruxsatingiz bo‘lgan dasturlarni yuklang va tarqating."
    )


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer("Bosh menyu:", reply_markup=main_menu())


@router.message(F.text == "❌ Bekor qilish")
@router.message(Command("cancel"))
async def cancel(
    message: Message, state: FSMContext, db_path: str, admin_ids: frozenset[int]
) -> None:
    data = await state.get_data()
    if is_admin(message.from_user.id, admin_ids) and data.get("draft_id"):
        await remove_draft(db_path, message.from_user.id, data["draft_id"])
    await state.clear()
    await message.answer("Jarayon bekor qilindi.", reply_markup=main_menu())
