import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.admin import request_admin_keyboard
from keyboards.user import main_menu, programs_keyboard, search_not_found_keyboard
from services.notification_service import notify_admins
from services.request_service import submit_request
from database.repositories import get_request
from services.search_service import search
from states.user import Search

logger = logging.getLogger(__name__)
router = Router(name="search")


@router.message(F.text == "🔎 Dastur qidirish")
async def begin_search(message: Message, state: FSMContext) -> None:
    await state.set_state(Search.query)
    await message.answer("Dastur nomi yoki kalit so‘zini yuboring. Bekor qilish: ❌ Bekor qilish")


@router.message(Search.query)
async def search_results(message: Message, state: FSMContext, db_path: str) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Qidiruv so‘zini matn ko‘rinishida yuboring.")
        return
    if len(query) < 2:
        await message.answer("Qidiruv so‘zi kamida 2 ta belgidan iborat bo‘lishi kerak.")
        return
    await state.update_data(query=query, search_sort="relevance")
    await state.set_state(None)
    rows = await search(db_path, query)
    if rows:
        await message.answer(
            f"“{html.escape(query)}” bo‘yicha natijalar:",
            reply_markup=programs_keyboard(rows, mode="search"),
        )
    else:
        safe_query = html.escape(query)
        await message.answer(
            f"🔎 Dastur topilmadi\n\n"
            f"“{safe_query}” bo‘yicha katalogda dastur topilmadi.\n\n"
            f"Ushbu dasturni katalogga qo‘shish uchun adminlarga so‘rov yuborasizmi?",
            reply_markup=search_not_found_keyboard(),
        )


@router.callback_query(F.data.startswith("sort_search:"))
async def sort_search_results(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer()
    data = await state.get_data()
    query = data.get("query", "")
    sort = callback.data.split(":", 1)[1]
    await state.update_data(search_sort=sort)
    rows = await search(db_path, query, sort=sort)
    if callback.message:
        await callback.message.answer(
            f"“{html.escape(query)}” bo‘yicha saralangan natijalar:" if rows else "Natija topilmadi.",
            reply_markup=programs_keyboard(rows, mode="search", sort=sort),
        )


@router.callback_query(F.data.startswith("page:search:"))
async def search_page(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer()
    try:
        _, _, sort, page_value = callback.data.split(":", 3)
        page = max(int(page_value), 0)
    except (ValueError, IndexError):
        return
    query = (await state.get_data()).get("query", "")
    rows = await search(db_path, query, sort=sort, page=page)
    if callback.message:
        await callback.message.answer(
            "Qidiruv natijalari:" if rows else "Boshqa natija yo‘q.",
            reply_markup=programs_keyboard(rows, page=page, mode="search", sort=sort),
        )


@router.callback_query(F.data == "search:request")
async def search_submit_request(
    callback: CallbackQuery, state: FSMContext, db_path: str, admin_ids: frozenset[int]
) -> None:
    data = await state.get_data()
    query = data.get("query")
    if not query:
        await callback.answer("So‘rov allaqachon qayta ishlandi.", show_alert=True)
        return

    await callback.answer()

    try:
        request_id = await submit_request(db_path, callback.from_user.id, query, "")
        request = await get_request(db_path, request_id)
    except Exception:
        logger.exception("So‘rovni saqlashda xato: user_id=%s", callback.from_user.id)
        if callback.message:
            await callback.message.answer(
                "So‘rovni yuborib bo‘lmadi. Iltimos, keyinroq qayta urinib ko‘ring."
            )
        return

    username = f"@{callback.from_user.username}" if callback.from_user.username else "Mavjud emas"
    notification = (
        f"Yangi dastur so‘rovi #{request_id}\n"
        f"Dastur: {query}\n"
        f"Izoh: Yo‘q\n"
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
        safe_query = html.escape(query)
        await callback.message.answer(
            f"✅ So‘rovingiz yuborildi!\n\n"
            f"“{safe_query}” dasturi bo‘yicha so‘rovingiz adminlarga yetkazildi. Rahmat!",
            reply_markup=main_menu(),
        )


@router.callback_query(F.data == "search:new")
async def search_new_query(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Search.query)
    await state.update_data(query="")
    if callback.message:
        await callback.message.answer(
            "Dastur nomi yoki kalit so‘zini yuboring. Bekor qilish: ❌ Bekor qilish"
        )
