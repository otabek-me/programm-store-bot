from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.user import programs_keyboard
from services.search_service import search
from states.user import Search

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
    await state.update_data(query=query, search_sort="relevance")
    await state.set_state(None)
    rows = await search(db_path, query)
    await message.answer(
        f"“{query}” bo‘yicha natijalar:" if rows else "Hech narsa topilmadi. Dastur so‘rovini yuborishingiz mumkin.",
        reply_markup=programs_keyboard(rows, mode="search"),
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
            f"“{query}” bo‘yicha saralangan natijalar:" if rows else "Natija topilmadi.",
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
