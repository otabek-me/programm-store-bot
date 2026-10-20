from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name="admin-settings")


@router.callback_query(F.data == "admin:settings")
async def show_settings(
    callback: CallbackQuery,
    db_path: str,
    allowed_file_extensions: frozenset[str] | None,
) -> None:
    await callback.answer()
    extension_policy = (
        ", ".join(sorted(allowed_file_extensions))
        if allowed_file_extensions else "Cheklanmagan (faqat admin yuklay oladi)"
    )
    if callback.message:
        await callback.message.answer(
            "⚙️ Bot sozlamalari\n"
            f"Fayl turi siyosati: {extension_policy}\n"
            f"Ma’lumotlar bazasi: {db_path}\n"
            "Maxfiy token .env faylidan olinadi va bu yerda ko‘rsatilmaydi."
        )
