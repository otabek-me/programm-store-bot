import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from database.repositories import get_program, record_download

logger = logging.getLogger(__name__)
router = Router(name="downloads")


@router.callback_query(F.data.startswith("download:"))
async def download_program(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    program = await get_program(db_path, program_id, active_only=True)
    if program is None:
        if callback.message:
            await callback.message.answer("Bu dastur hozir mavjud emas.")
        return
    try:
        await callback.bot.send_document(
            chat_id=callback.from_user.id,
            document=program["file_id"],
            caption=program["name"],
        )
        await record_download(db_path, callback.from_user.id, program_id)
    except TelegramAPIError:
        logger.exception(
            "Telegram file_id bilan yuborish xatosi: program_id=%s user_id=%s",
            program_id, callback.from_user.id,
        )
        if callback.message:
            await callback.message.answer(
                "Faylni yuborib bo‘lmadi. Keyinroq qayta urinib ko‘ring yoki administratorga xabar bering."
            )
