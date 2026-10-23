import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repositories import add_request_message, get_request, requests, update_request_status
from keyboards.admin import request_admin_keyboard
from states.admin import RequestReply
from utils.validators import required_text

logger = logging.getLogger(__name__)
router = Router(name="admin-requests")

STATUS_LABELS = {
    "pending": "Kutilmoqda",
    "in_progress": "Jarayonda",
    "completed": "Bajarildi",
    "rejected": "Rad etildi",
}


@router.callback_query(F.data == "admin:requests")
async def requests_list(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    await _show_requests(callback, db_path, 0, answered=True)


@router.callback_query(F.data.startswith("admin:requests:"))
async def requests_page(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        page = max(int(callback.data.rsplit(":", 1)[1]), 0)
    except ValueError:
        return
    await _show_requests(callback, db_path, page, answered=True)


ACTIVE_STATUSES = ("pending", "in_progress")


async def _show_requests(callback: CallbackQuery, db_path: str, page: int, answered: bool = False) -> None:
    if not answered:
        await callback.answer()
    rows = await requests(db_path, status=list(ACTIVE_STATUSES), limit=9, offset=page * 8)
    if not callback.message:
        return
    visible_rows = rows[:8]
    if not visible_rows:
        await callback.message.answer("✅ Hozircha yangi so‘rovlar yo‘q")
        return
    for row in visible_rows:
        await callback.message.answer(
            f"#{row['id']} · {row['program_name']} · {STATUS_LABELS[row['status']]}\n"
            f"Foydalanuvchi: {row['first_name']} (ID {row['user_id']})\n"
            f"Izoh: {row['details'] or 'Yo‘q'}",
            reply_markup=request_admin_keyboard(row["id"], row["status"]),
        )
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:requests:{page - 1}"))
    if len(rows) > 8:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:requests:{page + 1}"))
    if navigation:
        await callback.message.answer("Sahifalash:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[navigation]))


@router.callback_query(F.data.startswith("request_status:"))
async def set_request_status(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        _, request_id_raw, status = callback.data.split(":", 2)
        request_id = int(request_id_raw)
    except ValueError:
        return
    if status not in STATUS_LABELS:
        return
    updated = await update_request_status(db_path, request_id, status, callback.from_user.id)
    request = await get_request(db_path, request_id)
    if callback.message:
        if not updated or request is None:
            await callback.message.answer("So‘rov topilmadi.")
            return
        await callback.message.answer(f"So‘rov #{request_id}: {STATUS_LABELS[status]}.")
        try:
            await callback.bot.send_message(
                request["user_id"],
                f"#{request_id} raqamli “{request['program_name']}” so‘rovingiz holati: {STATUS_LABELS[status]}.",
            )
        except TelegramAPIError:
            logger.exception("So‘rov holatini foydalanuvchiga yuborib bo‘lmadi: request_id=%s", request_id)


@router.callback_query(F.data.startswith("request_reply:"))
async def begin_request_reply(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        request_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.clear()
    await state.set_state(RequestReply.message)
    await state.update_data(request_id=request_id)
    if callback.message:
        await callback.message.answer(f"So‘rov #{request_id} uchun javob matnini yuboring:")


@router.message(RequestReply.message)
async def send_request_reply(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        reply = required_text(message.text or "", "Javob", 2000)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    request = await get_request(db_path, data["request_id"])
    if request is None:
        await state.clear()
        await message.answer("So‘rov topilmadi.")
        return
    try:
        await message.bot.send_message(
            request["user_id"],
            f"Administrator javobi — so‘rov #{request['id']} ({request['program_name']}):\n{reply}",
        )
    except TelegramAPIError:
        logger.exception("Administrator javobi yuborilmadi: request_id=%s", request["id"])
        await message.answer("Javobni foydalanuvchiga yetkazib bo‘lmadi.")
        return
    await add_request_message(db_path, request["id"], message.from_user.id, reply)
    await state.clear()
    await message.answer("Javob foydalanuvchiga yuborildi.")
