from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repositories import broadcast_targets
from keyboards.admin import admin_menu
from services.notification_service import broadcast
from states.admin import Broadcast
from utils.validators import required_text

router = Router(name="admin-broadcasts")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_begin(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(Broadcast.message)
    if callback.message:
        await callback.message.answer("Foydalanuvchilarga yuboriladigan xabar matnini kiriting:")


@router.message(Broadcast.message)
async def broadcast_preview(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        text = required_text(message.text or "", "Xabar", 4000)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    recipients = await broadcast_targets(db_path)
    await state.update_data(broadcast_text=text, recipient_count=len(recipients))
    await state.set_state(Broadcast.confirm)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash va yuborish", callback_data="broadcast:send"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast:cancel"),
    ]])
    await message.answer(
        f"Xabar ko‘rinishi:\n\n{text}\n\nQabul qiluvchilar: {len(recipients)}\n"
        "Yuborish boshlansinmi?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Ommaviy yuborish bekor qilindi.")
    await state.clear()
    if callback.message:
        await callback.message.answer("Hech kimga xabar yuborilmadi.", reply_markup=admin_menu())


@router.callback_query(F.data == "broadcast:send", Broadcast.confirm)
async def broadcast_confirmed(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer("Yuborish boshlandi.")
    data = await state.get_data()
    await state.clear()
    if callback.message:
        await callback.message.answer("Xabarlar yuborilmoqda. Bu jarayon foydalanuvchilar soniga bog‘liq.")
    total, sent, failed = await broadcast(callback.bot, db_path, callback.from_user.id, data["broadcast_text"])
    if callback.message:
        await callback.message.answer(
            f"Yuborish tugadi.\nQabul qiluvchilar: {total}\nYuborildi: {sent}\nXato: {failed}",
            reply_markup=admin_menu(),
        )
