import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.db import DatabaseErrors, DatabaseIntegrityErrors
from database.repositories import add_category, categories, delete_category, rename_category
from keyboards.admin import category_admin_keyboard
from states.admin import CategoryForm
from utils.validators import required_text

logger = logging.getLogger(__name__)
router = Router(name="admin-categories")


@router.callback_query(F.data == "admin:categories")
async def show_categories(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    rows = await categories(db_path)
    if callback.message:
        listing = "\n".join(f"{row['id']}: {row['name']}" for row in rows)
        await callback.message.answer(f"Kategoriyalar:\n{listing}", reply_markup=category_admin_keyboard(rows))


@router.callback_query(F.data == "category_add")
async def add_category_begin(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(CategoryForm.name)
    await state.update_data(category_action="add")
    if callback.message:
        await callback.message.answer("Yangi kategoriya nomini yuboring:")


@router.callback_query(F.data.startswith("category_edit:"))
async def rename_category_begin(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.clear()
    await state.set_state(CategoryForm.name)
    await state.update_data(category_action="rename", category_id=category_id)
    if callback.message:
        await callback.message.answer("Kategoriya uchun yangi nomni yuboring:")


@router.message(CategoryForm.name)
async def save_category_name(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        name = required_text(message.text or "", "Kategoriya nomi", 80)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    try:
        if data["category_action"] == "add":
            await add_category(db_path, name)
            result = "Kategoriya qo‘shildi."
        else:
            changed = await rename_category(db_path, data["category_id"], name)
            result = "Kategoriya nomi yangilandi." if changed else "Kategoriya topilmadi."
    except DatabaseIntegrityErrors:
        await message.answer("Bunday nomdagi kategoriya mavjud.")
        return
    except DatabaseErrors:
        logger.exception("Kategoriya saqlashda xato: admin_id=%s", message.from_user.id)
        await message.answer("Kategoriyani saqlab bo‘lmadi. Qayta urinib ko‘ring.")
        return
    await state.clear()
    await message.answer(result, reply_markup=category_admin_keyboard(await categories(db_path)))


@router.callback_query(F.data.startswith("category_delete_confirm:"))
async def category_delete_confirmation(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha, o‘chirish", callback_data=f"category_delete:{category_id}"),
        InlineKeyboardButton(text="Bekor qilish", callback_data="admin:categories"),
    ]])
    if callback.message:
        await callback.message.answer(
            "Kategoriya o‘chiriladi, unga tegishli dasturlar kategoriyasiz qoladi. Tasdiqlaysizmi?",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("category_delete:"))
async def category_delete_confirmed(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    deleted = await delete_category(db_path, category_id)
    if callback.message:
        rows = await categories(db_path)
        await callback.message.answer(
            "Kategoriya o‘chirildi." if deleted else "Kategoriya topilmadi.",
            reply_markup=category_admin_keyboard(rows),
        )
