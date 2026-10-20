from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.repositories import categories, get_program
from keyboards.user import categories_keyboard, program_detail, programs_keyboard
from services.search_service import search
from utils.validators import format_size

router = Router(name="catalog")


def _program_text(program) -> str:
    fields = [f"📦 {program['name']}"]
    if program["category_name"]:
        fields.append(f"📂 Kategoriya: {program['category_name']}")
    fields.append(f"\n{program['description']}")
    if program["version"]:
        fields.append(f"\n🔖 Versiya: {program['version']}")
    if program["operating_system"]:
        fields.append(f"💻 Tizim: {program['operating_system']}")
    if program["file_name"]:
        fields.append(f"📄 Fayl: {program['file_name']}")
    fields.append(f"📏 Hajmi: {format_size(program['file_size'])}")
    fields.append(f"⬇️ Yuklab olingan: {program['downloads']}")
    return "\n".join(fields)


@router.message(F.text == "📂 Kategoriyalar")
async def show_categories(message: Message, db_path: str) -> None:
    rows = await categories(db_path)
    await message.answer("Kategoriya tanlang:", reply_markup=categories_keyboard(rows))


@router.message(F.text.in_({"📋 Dasturlar katalogi", "🆕 Yangi dasturlar", "🔥 Mashhur dasturlar"}))
async def show_catalog(message: Message, db_path: str) -> None:
    modes = {
        "🆕 Yangi dasturlar": ("newest", "Yangi dasturlar"),
        "🔥 Mashhur dasturlar": ("popular", "Mashhur dasturlar"),
        "📋 Dasturlar katalogi": ("relevance", "Dasturlar katalogi"),
    }
    sort, title = modes[message.text]
    rows = await search(db_path, "", sort=sort)
    await message.answer(
        title + (":" if rows else " hozircha bo‘sh."),
        reply_markup=programs_keyboard(rows, sort=sort),
    )


@router.callback_query(F.data.startswith("category:"))
async def category_programs(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    rows = await search(db_path, "", category_id=category_id)
    if callback.message:
        await callback.message.answer(
            "Kategoriya dasturlari:" if rows else "Bu kategoriyada hozircha dastur yo‘q.",
            reply_markup=programs_keyboard(rows, mode=f"category_{category_id}"),
        )


@router.callback_query(F.data.startswith("program:"))
async def program_details(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return
    program = await get_program(db_path, program_id, active_only=True)
    if callback.message:
        if program is None:
            await callback.message.answer("Bu dastur endi mavjud emas.")
        else:
            await callback.message.answer(_program_text(program), reply_markup=program_detail(program_id))


@router.callback_query(F.data.startswith("page:"))
async def catalog_page(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        _, mode, sort, page_value = callback.data.split(":", 3)
        page = max(int(page_value), 0)
        category_id = int(mode.split("_", 1)[1]) if mode.startswith("category_") else None
    except (ValueError, IndexError):
        return
    if mode.startswith("category_"):
        sort = "relevance"
    rows = await search(db_path, "", sort=sort, page=page, category_id=category_id)
    if callback.message:
        if not rows and page > 0:
            await callback.message.answer("Boshqa natija yo‘q.")
        else:
            await callback.message.answer(
                "Dasturlar:" if rows else "Hozircha dastur yo‘q.",
                reply_markup=programs_keyboard(rows, page=page, mode=mode, sort=sort),
            )


@router.callback_query(F.data.startswith("sort:"))
async def change_sort(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    sort = callback.data.split(":", 1)[1]
    rows = await search(db_path, "", sort=sort)
    if callback.message:
        await callback.message.answer(
            "Saralangan dasturlar:" if rows else "Hozircha dastur topilmadi.",
            reply_markup=programs_keyboard(rows, sort=sort),
        )
