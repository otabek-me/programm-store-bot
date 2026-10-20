from aiogram import Router
from aiogram.types import Message

router = Router(name="fallback")


@router.message()
async def unsupported_message(message: Message) -> None:
    await message.answer("Bu xabarni tushunmadim. Menyudagi tugmalardan foydalaning yoki /start yuboring.")
