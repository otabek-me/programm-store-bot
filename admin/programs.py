import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.db import DatabaseErrors
from database.repositories import (
    delete_program, get_draft, get_program, list_drafts, list_programs_admin, remove_draft, save_draft,
    replace_program_categories, replace_program_file, search_programs, toggle_program_active,
    update_program_field,
)
from keyboards.admin import admin_menu, edit_program_keyboard
from services.program_service import publish_program
from states.admin import AddProgram, AdminSearch, EditProgram
from utils.validators import optional_text, required_text

logger = logging.getLogger(__name__)
router = Router(name="admin-programs")


def _parse_category_ids(raw: str, available_ids: set[int]) -> list[int]:
    if raw.strip() == "-":
        return []
    try:
        category_ids = list(dict.fromkeys(int(item.strip()) for item in raw.split(",")))
    except ValueError as exc:
        raise ValueError("Kategoriya ID raqamlarini vergul bilan yuboring.") from exc
    if not category_ids or any(category_id not in available_ids for category_id in category_ids):
        raise ValueError("Kategoriya ID sini tekshiring.")
    return category_ids


async def _save_current_draft(state: FSMContext, db_path: str, admin_id: int) -> dict:
    data = await state.get_data()
    payload = data["draft_payload"]
    data["draft_id"] = await save_draft(db_path, admin_id, json.dumps(payload, ensure_ascii=False), data["draft_id"])
    await state.update_data(draft_id=data["draft_id"])
    return payload


@router.callback_query(F.data == "admin:add")
async def add_program_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(AddProgram.file)
    if callback.message:
        await callback.message.answer(
            "Dastur faylini Telegram hujjati (Document) sifatida yuboring. "
            "Bot faylni serverga yuklab olmaydi. Bekor qilish: ❌ Bekor qilish"
        )


@router.message(AddProgram.file, F.document)
async def receive_program_file(
    message: Message, state: FSMContext, db_path: str,
    allowed_file_extensions: frozenset[str] | None,
) -> None:
    document = message.document
    if allowed_file_extensions and not any(
        (document.file_name or "").casefold().endswith(extension)
        for extension in allowed_file_extensions
    ):
        await message.answer("Bu fayl turi administrator sozlamalaridagi ruxsat etilgan ro‘yxatda yo‘q.")
        return
    payload = {
        "file_id": document.file_id,
        "file_unique_id": document.file_unique_id,
        "file_name": document.file_name,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
    }
    draft_id = await save_draft(db_path, message.from_user.id, json.dumps(payload, ensure_ascii=False))
    await state.update_data(draft_id=draft_id, draft_payload=payload)
    await state.set_state(AddProgram.name)
    await message.answer("Dastur nomini yuboring:")


@router.message(AddProgram.file)
async def file_required(message: Message) -> None:
    await message.answer("Iltimos, faylni Telegram Document sifatida yuboring.")


@router.message(AddProgram.name)
async def program_name(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        name = required_text(message.text or "", "Dastur nomi", 120)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = await _save_current_draft(state, db_path, message.from_user.id)
    payload["name"] = name
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.description)
    await message.answer("Qisqacha tavsifni yuboring:")


@router.message(AddProgram.description)
async def program_description(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        description = required_text(message.text or "", "Tavsif", 1500)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = (await state.get_data())["draft_payload"]
    payload["description"] = description
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.category)
    from database.repositories import categories
    available = await categories(db_path)
    options = "\n".join(f"{row['id']}: {row['name']}" for row in available)
    await message.answer(f"Kategoriya ID raqamlarini vergul bilan yuboring:\n{options}")


@router.message(AddProgram.category)
async def program_category(message: Message, state: FSMContext, db_path: str) -> None:
    from database.repositories import categories

    available = await categories(db_path)
    try:
        category_ids = _parse_category_ids((message.text or "").strip(), {row["id"] for row in available})
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = (await state.get_data())["draft_payload"]
    payload["category_ids"] = category_ids
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.keywords)
    await message.answer("Qidiruv kalit so‘zlari va sinonimlarini vergul bilan yuboring (bo‘sh qoldirish uchun -):")


@router.message(AddProgram.keywords)
async def program_keywords(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        keywords = optional_text(message.text or "", 500)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = (await state.get_data())["draft_payload"]
    payload["keywords"] = "" if keywords == "-" else keywords
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.version)
    await message.answer("Versiya raqami (yo‘q bo‘lsa -):")


@router.message(AddProgram.version)
async def program_version(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        version = optional_text(message.text or "", 80)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = (await state.get_data())["draft_payload"]
    payload["version"] = "" if version == "-" else version
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.operating_system)
    await message.answer("Qo‘llab-quvvatlanadigan tizim (yo‘q bo‘lsa -):")


@router.message(AddProgram.operating_system)
async def program_os(message: Message, state: FSMContext, db_path: str) -> None:
    try:
        operating_system = optional_text(message.text or "", 120)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    payload = (await state.get_data())["draft_payload"]
    payload["operating_system"] = "" if operating_system == "-" else operating_system
    await state.update_data(draft_payload=payload)
    await _save_current_draft(state, db_path, message.from_user.id)
    await state.set_state(AddProgram.confirm)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ E’lon qilish", callback_data="admin:publish"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:cancel_draft"),
    ]])
    await message.answer(
        f"Tekshiring:\n📦 {payload['name']}\n📝 {payload['description']}\n"
        f"🔎 Kalit so‘zlar: {payload.get('keywords') or '—'}\n"
        f"📄 Fayl: {payload.get('file_name') or 'Telegram hujjati'}",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:publish", AddProgram.confirm)
async def publish_draft(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer()
    data = await state.get_data()
    try:
        program_id = await publish_program(db_path, data["draft_payload"])
    except (ValueError, KeyError, *DatabaseErrors):
        logger.exception("Dastur e’lon qilishda xato: admin_id=%s", callback.from_user.id)
        if callback.message:
            await callback.message.answer("Dastur saqlanmadi. Ma’lumotlarni tekshirib, qayta urinib ko‘ring.")
        return
    await remove_draft(db_path, callback.from_user.id, data["draft_id"])
    await state.clear()
    if callback.message:
        await callback.message.answer(f"✅ Dastur katalogga qo‘shildi (ID: {program_id}).", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:cancel_draft")
async def cancel_draft(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer("Draft bekor qilindi.")
    data = await state.get_data()
    draft_id = data.get("draft_id")
    if draft_id:
        await remove_draft(db_path, callback.from_user.id, draft_id)
    await state.clear()
    if callback.message:
        await callback.message.answer("Dastur qo‘shish bekor qilindi.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:drafts")
async def show_drafts(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    drafts = await list_drafts(db_path, callback.from_user.id)
    if not callback.message:
        return
    if not drafts:
        await callback.message.answer("Davom ettiriladigan draft topilmadi.", reply_markup=admin_menu())
        return
    buttons = [[InlineKeyboardButton(text=f"Draft #{row['id']}", callback_data=f"admin:resume:{row['id']}")] for row in drafts]
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:home")])
    await callback.message.answer("Draft tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("admin:resume:"))
async def resume_draft(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer()
    try:
        draft_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    row = await get_draft(db_path, callback.from_user.id, draft_id)
    if row is None:
        if callback.message:
            await callback.message.answer("Draft topilmadi yoki u sizga tegishli emas.")
        return
    payload = json.loads(row["payload"])
    await state.clear()
    await state.update_data(draft_id=draft_id, draft_payload=payload)
    next_state = next(
        (fsm_state for key, fsm_state in (
            ("name", AddProgram.name), ("description", AddProgram.description),
            ("category_ids", AddProgram.category), ("category_id", AddProgram.category),
            ("keywords", AddProgram.keywords),
            ("version", AddProgram.version), ("operating_system", AddProgram.operating_system),
        ) if key not in payload),
        AddProgram.confirm,
    )
    await state.set_state(next_state)
    prompts = {
        AddProgram.name: "Draft davom etmoqda. Dastur nomini yuboring:",
        AddProgram.description: "Draft davom etmoqda. Tavsifni yuboring:",
        AddProgram.category: "Draft davom etmoqda. Kategoriya ID raqamlarini vergul bilan yuboring:",
        AddProgram.keywords: "Draft davom etmoqda. Kalit so‘zlarni yuboring:",
        AddProgram.version: "Draft davom etmoqda. Versiyani yuboring:",
        AddProgram.operating_system: "Draft davom etmoqda. Operatsion tizimni yuboring:",
    }
    if callback.message:
        if next_state == AddProgram.confirm:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ E’lon qilish", callback_data="admin:publish"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:cancel_draft"),
            ]])
            await callback.message.answer("Draft e’lon qilishga tayyor.", reply_markup=keyboard)
        else:
            await callback.message.answer(prompts[next_state])


@router.callback_query(F.data == "admin:programs")
async def program_list(callback: CallbackQuery, db_path: str) -> None:
    await _show_program_page(callback, db_path, 0)


@router.callback_query(F.data.startswith("admin:programs:"))
async def program_list_page(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        page = max(int(callback.data.rsplit(":", 1)[1]), 0)
    except ValueError:
        return
    await _show_program_page(callback, db_path, page, answered=True)


async def _show_program_page(callback: CallbackQuery, db_path: str, page: int, answered: bool = False) -> None:
    if not answered:
        await callback.answer()
    rows = await list_programs_admin(db_path, limit=9, offset=page * 8)
    visible_rows = rows[:8]
    buttons = [
        [InlineKeyboardButton(
            text=f"{'✅' if row['is_active'] else '🙈'} {row['name']} · {row['downloads']}⬇",
            callback_data=f"admin:program:{row['id']}",
        )]
        for row in visible_rows
    ]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:programs:{page - 1}"))
    if len(rows) > 8:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:programs:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:home")])
    if callback.message:
        await callback.message.answer(
            "Dasturlar ro‘yxati:" if visible_rows else "Katalog bo‘sh.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


@router.callback_query(F.data == "admin:search")
async def admin_search_begin(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(AdminSearch.query)
    if callback.message:
        await callback.message.answer("Qidiriladigan dastur nomi yoki kalit so‘zini yuboring:")


@router.message(AdminSearch.query)
async def admin_search_results(message: Message, state: FSMContext, db_path: str) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Qidiruv so‘zini yuboring.")
        return
    rows = await search_programs(db_path, query, limit=8)
    await state.clear()
    buttons = [
        [InlineKeyboardButton(text=row["name"], callback_data=f"admin:program:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:home")])
    await message.answer(
        f"“{query}” bo‘yicha natijalar:" if rows else "Dastur topilmadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("admin:program:"))
async def program_admin_detail(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    program = await get_program(db_path, program_id)
    if callback.message:
        if program is None:
            await callback.message.answer("Dastur topilmadi.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ma’lumotlarni tahrirlash", callback_data=f"admin:edit_menu:{program_id}")],
            [InlineKeyboardButton(
                text="🙈 Yashirish" if program["is_active"] else "👁 Ko‘rsatish",
                callback_data=f"admin:toggle:{program_id}",
            )],
            [InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"admin:delete_confirm:{program_id}")],
            [InlineKeyboardButton(text="⬅️ Ro‘yxat", callback_data="admin:programs")],
        ])
        await callback.message.answer(
            f"{program['name']}\nHolati: {'Faol' if program['is_active'] else 'Yashirin'}\n"
            f"Yuklab olishlar: {program['downloads']}",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("admin:edit_menu:"))
async def edit_program_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    if callback.message:
        await callback.message.answer("Tahrirlanadigan maydonni tanlang:", reply_markup=edit_program_keyboard(program_id))


@router.callback_query(F.data.startswith("admin:edit:"))
async def edit_program_field(callback: CallbackQuery, state: FSMContext, db_path: str) -> None:
    await callback.answer()
    try:
        _, _, program_id_raw, field = callback.data.split(":", 3)
        program_id = int(program_id_raw)
    except ValueError:
        return
    program = await get_program(db_path, program_id)
    if program is None:
        if callback.message:
            await callback.message.answer("Dastur topilmadi.")
        return
    await state.clear()
    await state.update_data(edit_program_id=program_id, edit_field=field)
    if field == "file":
        await state.set_state(EditProgram.file)
        prompt = "Yangi Telegram hujjatini yuboring (fayl serverga yuklab olinmaydi):"
    else:
        await state.set_state(EditProgram.value)
        if field in {"category_id", "category_ids"}:
            from database.repositories import categories
            rows = await categories(db_path)
            prompt = "Yangi kategoriya ID raqamlarini vergul bilan yuboring (-: kategoriyasiz):\n" + "\n".join(
                f"{row['id']}: {row['name']}" for row in rows
            )
        elif field in {"keywords", "version", "operating_system"}:
            prompt = f"Yangi qiymatni yuboring. Maydonni bo‘shatish uchun -:\n{program[field] or '—'}"
        else:
            prompt = f"Yangi qiymatni yuboring:\n{program[field]}"
    if callback.message:
        await callback.message.answer(prompt)


@router.message(EditProgram.value)
async def save_program_field(message: Message, state: FSMContext, db_path: str) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    value = (message.text or "").strip()
    try:
        if field in {"category_id", "category_ids"}:
            from database.repositories import categories
            available_ids = {row["id"] for row in await categories(db_path)}
            category_ids = _parse_category_ids(value, available_ids)
            changed = await replace_program_categories(db_path, data["edit_program_id"], category_ids)
        elif field in {"keywords", "version", "operating_system"} and value == "-":
            value = ""
        else:
            maximum = 1500 if field == "description" else 120
            value = required_text(value, "Qiymat", maximum)
        if field not in {"category_id", "category_ids"}:
            changed = await update_program_field(db_path, data["edit_program_id"], field, value)
    except (ValueError, KeyError) as exc:
        await message.answer(str(exc) or "Qiymatni tekshiring.")
        return
    except DatabaseErrors:
        logger.exception("Dastur maydonini saqlashda xato: admin_id=%s", message.from_user.id)
        await message.answer("Dastur ma’lumotini saqlab bo‘lmadi. Qayta urinib ko‘ring.")
        return
    await state.clear()
    await message.answer("Dastur yangilandi." if changed else "Dastur topilmadi.", reply_markup=admin_menu())


@router.message(EditProgram.file, F.document)
async def replace_program_file_handler(
    message: Message, state: FSMContext, db_path: str,
    allowed_file_extensions: frozenset[str] | None,
) -> None:
    document = message.document
    if allowed_file_extensions and not any(
        (document.file_name or "").casefold().endswith(extension)
        for extension in allowed_file_extensions
    ):
        await message.answer("Bu fayl turi administrator sozlamalaridagi ruxsat etilgan ro‘yxatda yo‘q.")
        return
    program_id = (await state.get_data())["edit_program_id"]
    await replace_program_file(db_path, program_id, document)
    await state.clear()
    await message.answer("Telegram fayli yangilandi; serverga ko‘chirilmadi.", reply_markup=admin_menu())


@router.message(EditProgram.file)
async def replacement_file_required(message: Message) -> None:
    await message.answer("Iltimos, yangi faylni Telegram Document sifatida yuboring.")


@router.callback_query(F.data.startswith("admin:toggle:"))
async def toggle_program(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    if await toggle_program_active(db_path, program_id) and callback.message:
        await callback.message.answer("Dastur ko‘rinish holati o‘zgartirildi.")


@router.callback_query(F.data.startswith("admin:delete_confirm:"))
async def confirm_program_delete(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha, o‘chirish", callback_data=f"admin:delete:{program_id}"),
        InlineKeyboardButton(text="Yo‘q", callback_data="admin:programs"),
    ]])
    if callback.message:
        await callback.message.answer("Dastur katalogdan o‘chiriladi. Tasdiqlaysizmi?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:delete:"))
async def delete_program_confirmed(callback: CallbackQuery, db_path: str) -> None:
    await callback.answer()
    try:
        program_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return
    deleted = await delete_program(db_path, program_id)
    if callback.message:
        await callback.message.answer(
            "Dastur katalogdan olib tashlandi; statistika tarixi saqlandi."
            if deleted else "Dastur topilmadi.",
            reply_markup=admin_menu(),
        )
