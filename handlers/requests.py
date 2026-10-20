from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.admin import request_admin_keyboard
from keyboards.user import main_menu, request_confirm
from services.notification_service import notify_admins
from services.request_service import submit_request
from database.repositories import get_request
from states.user import SoftwareRequest
from utils.validators import required_text

router = Router(name="requests")


@router.message(F.text == "💬 Dastur so‘rash")
async def request_begin(message: Message, state: FSMContext) -> None:
    await state.set_state(SoftwareRequest.name)
    await message.answer("Qaysi dastur kerak? Nomini yuboring.")


@router.message(SoftwareRequest.name)
async def request_name(message: Message, state: FSMContext) -> None:
    try:
        name = required_text(message.text or "", "Dastur nomi", 120)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(request_name=name)
    await state.set_state(SoftwareRequest.details)
    await message.answer("Versiya, operatsion tizim yoki izohni yuboring. Kerak bo‘lmasa “Yo‘q” deb yozing.")


@router.message(SoftwareRequest.details)
async def request_details(message: Message, state: FSMContext) -> None:
    details = (message.text or "").strip()
    if len(details) > 1000:
        await message.answer("Izoh 1000 belgidan oshmasligi kerak.")
        return
    await state.update_data(request_details="" if details.casefold() in {"yo‘q", "yo'q", "-"} else details)
    data = await state.get_data()
    await state.set_state(SoftwareRequest.confirm)
    preview = f"So‘rovni tekshiring:\n📦 {data['request_name']}\n"
    preview += f"📝 {data['request_details'] or 'Qo‘shimcha izoh yo‘q'}"
    await message.answer(preview, reply_markup=request_confirm())


@router.callback_query(F.data == "request:cancel", SoftwareRequest.confirm)
async def request_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("So‘rov bekor qilindi.")
    await state.clear()
    if callback.message:
        await callback.message.answer("So‘rov yuborilmadi.", reply_markup=main_menu())


@router.callback_query(F.data == "request:confirm", SoftwareRequest.confirm)
async def request_confirmed(
    callback: CallbackQuery, state: FSMContext, db_path: str, admin_ids: frozenset[int]
) -> None:
    await callback.answer()
    data = await state.get_data()
    request_id = await submit_request(
        db_path, callback.from_user.id, data["request_name"], data.get("request_details", "")
    )
    request = await get_request(db_path, request_id)
    username = f"@{callback.from_user.username}" if callback.from_user.username else "Mavjud emas"
    notification = (
        f"Yangi dastur so‘rovi #{request_id}\n"
        f"Dastur: {data['request_name']}\n"
        f"Izoh: {data.get('request_details') or 'Yo‘q'}\n"
        f"Foydalanuvchi ID: {callback.from_user.id}\n"
        f"Username: {username}\nHolat: Kutilmoqda"
    )
    if request is not None:
        notification += f"\nVaqt: {request['created_at']}"
    await notify_admins(
        callback.bot, admin_ids, notification,
        request_admin_keyboard(request_id, "pending"),
    )
    await state.clear()
    if callback.message:
        await callback.message.answer(f"So‘rovingiz #{request_id} administratorga yuborildi.", reply_markup=main_menu())
