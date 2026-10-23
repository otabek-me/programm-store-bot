import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repositories import broadcast_targets
from keyboards.admin import admin_menu
from services.notification_service import broadcast, stop_broadcast
from states.admin import Broadcast

logger = logging.getLogger(__name__)
router = Router(name="admin-broadcasts")

ALBUM_WAIT_SECONDS = 2.0


def _broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tarqatish", callback_data="broadcast:send"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast:cancel"),
        ]]
    )


def _broadcast_sending_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="⏹ Tarqatishni to‘xtatish", callback_data="broadcast:stop"),
        ]]
    )


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_begin(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(Broadcast.message)
    await state.update_data(album_messages={})
    if callback.message:
        await callback.message.answer(
            "Tarqatmoqchi bo‘lgan xabaringizni yuboring. Matn, rasm, video, hujjat yoki boshqa xabar turini yuborishingiz mumkin.\n"
            "Bir necha rasm yoki videoni bitta albom sifatida yuborishingiz ham mumkin."
        )


@router.message(Broadcast.message)
async def broadcast_collect_message(message: Message, state: FSMContext, db_path: str) -> None:
    media_group_id = message.media_group_id
    album_messages = (await state.get_data()).get("album_messages", {})

    if media_group_id:
        if media_group_id not in album_messages:
            album_messages[media_group_id] = []
        album_messages[media_group_id].append({
            "chat_id": message.chat.id,
            "message_id": message.message_id,
        })
        await state.update_data(album_messages=album_messages)
        await state.set_state(Broadcast.collecting_album)
        # Start/reset album wait timer
        task = asyncio.create_task(_album_wait_and_show_preview(state, message, db_path))
        await state.update_data(_album_timer_task=task)
        return

    await state.update_data(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        media_group_id=None,
        message_ids=None,
    )
    recipients = await broadcast_targets(db_path)
    await state.update_data(recipient_count=len(recipients))
    await state.set_state(Broadcast.confirm)

    await message.copy_to(message.chat.id)
    await message.answer(
        f"Xabar ko‘rinishi yuqoridagi xabarga mos bo‘ladi.\n\n"
        f"Qabul qiluvchilar: {len(recipients)}\n"
        "Yuborish boshlansinmi?",
        reply_markup=_broadcast_confirm_keyboard(),
    )


@router.message(Broadcast.collecting_album)
async def broadcast_collect_album(message: Message, state: FSMContext, db_path: str) -> None:
    media_group_id = message.media_group_id
    album_messages = (await state.get_data()).get("album_messages", {})

    if media_group_id:
        if media_group_id not in album_messages:
            album_messages[media_group_id] = []
        album_messages[media_group_id].append({
            "chat_id": message.chat.id,
            "message_id": message.message_id,
        })
        await state.update_data(album_messages=album_messages)
        # Reset the timer
        existing_task = (await state.get_data()).get("_album_timer_task")
        if existing_task:
            existing_task.cancel()
        task = asyncio.create_task(_album_wait_and_show_preview(state, message, db_path))
        await state.update_data(_album_timer_task=task)


async def _album_wait_and_show_preview(
    state: FSMContext, trigger_message: Message, db_path: str | None
) -> None:
    try:
        await asyncio.sleep(ALBUM_WAIT_SECONDS)
    except asyncio.CancelledError:
        return

    data = await state.get_data()
    album_messages = data.get("album_messages", {})

    # Find the first (and likely only) media group
    media_group_id = None
    group_msgs = None
    for gid, msgs in album_messages.items():
        media_group_id = gid
        group_msgs = msgs
        break

    if not media_group_id or not group_msgs:
        return

    # Use the first message as the source reference
    first_msg = group_msgs[0]
    await state.update_data(
        source_chat_id=first_msg["chat_id"],
        source_message_id=first_msg["message_id"],
        media_group_id=media_group_id,
        message_ids=[m["message_id"] for m in group_msgs],
    )

    if db_path is None:
        # Get db_path from state or bot data
        db_path = str(trigger_message.bot.get("db_path", ""))

    recipients_count = 0
    if db_path:
        try:
            recipients = await broadcast_targets(db_path)
            recipients_count = len(recipients)
        except Exception:
            logger.exception("Failed to get broadcast targets")

    await state.update_data(recipient_count=recipients_count)
    await state.set_state(Broadcast.confirm)

    # Forward the first album message as preview
    try:
        await trigger_message.bot.copy_message(
            chat_id=trigger_message.chat.id,
            from_chat_id=first_msg["chat_id"],
            message_id=first_msg["message_id"],
        )
    except Exception:
        logger.exception("Failed to show album preview")

    await trigger_message.answer(
        f"Albom ko‘rinishi yuqoridagidek bo‘ladi.\n"
        f"Elementlar soni: {len(group_msgs)}\n\n"
        f"Qabul qiluvchilar: {recipients_count}\n"
        "Yuborish boshlansinmi?",
        reply_markup=_broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Tarqatish bekor qilindi.")
    await state.clear()
    if callback.message:
        await callback.message.answer("Hech kimga xabar yuborilmadi.", reply_markup=admin_menu())


@router.callback_query(F.data == "broadcast:send")
async def broadcast_confirmed(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    data = await state.get_data()
    source_chat_id = data.get("source_chat_id")
    source_message_id = data.get("source_message_id")
    media_group_id = data.get("media_group_id")

    if not source_chat_id or not source_message_id:
        await callback.answer("Xabar topilmadi. Qayta urinib ko‘ring.", show_alert=True)
        return

    # Handle album: collect all message_ids for the first media_group_id
    message_ids = None
    if media_group_id:
        album_messages = data.get("album_messages", {})
        group_msgs = album_messages.get(media_group_id)
        if group_msgs:
            message_ids = [m["message_id"] for m in group_msgs]
            # Use the first message as the reference
            source_message_id = message_ids[0]
            source_chat_id = group_msgs[0]["chat_id"]

    await callback.answer("Tarqatish boshlandi.")
    await state.set_state(Broadcast.sending)
    await state.update_data(job_running=True)

    if callback.message:
        await callback.message.edit_text(
            "Xabarlar yuborilmoqda...\n"
            "Jarayonni to‘xtatmoqchi bolsangiz, pastdagi tugmani bosing.",
            reply_markup=_broadcast_sending_keyboard(),
        )

    total, sent, failed = await broadcast(
        callback.bot, db_path, callback.from_user.id,
        source_chat_id, source_message_id,
        media_group_id=media_group_id,
        message_ids=message_ids,
    )

    await state.clear()

    if callback.message:
        await callback.message.edit_text(
            f"Tarqatish tugadi.\n"
            f"Jami foydalanuvchilar: {total}\n"
            f"Muvaffaqiyatli: {sent}\n"
            f"Yuborilmagan: {failed}\n"
            f"Foiz: {round(sent / total * 100, 1) if total else 0}%",
            reply_markup=admin_menu(),
        )


@router.callback_query(F.data == "broadcast:stop", Broadcast.sending)
async def broadcast_stop(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer("Tarqatish to‘xtatilmoqda...")
    cancelled = await stop_broadcast(db_path, callback.from_user.id)
    if cancelled:
        await state.clear()
        if callback.message:
            await callback.message.edit_text(
                "Tarqatish to‘xtatildi.",
                reply_markup=admin_menu(),
            )
    else:
        await callback.answer("Faol tarqatish topilmadi.", show_alert=True)
