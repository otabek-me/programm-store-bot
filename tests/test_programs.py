import pytest

from database.repositories import (
    categories, create_program, get_program, record_download, search_programs,
)


@pytest.mark.asyncio
async def test_program_file_id_is_saved_without_binary(db_path):
    category_id = (await categories(db_path))[0]["id"]
    program_id = await create_program(db_path, {
        "name": "Visual Studio Code",
        "description": "Kod muharriri",
        "category_id": category_id,
        "file_id": "telegram-file-id",
        "file_unique_id": "unique-file-id",
        "file_name": "vscode.zip",
        "mime_type": "application/zip",
        "file_size": 4096,
        "keywords": "vscode, vs code, visual studio code",
    })
    program = await get_program(db_path, program_id)
    assert program["file_id"] == "telegram-file-id"
    assert program["file_unique_id"] == "unique-file-id"
    assert "data" not in program.keys()


@pytest.mark.asyncio
async def test_program_can_belong_to_multiple_categories(db_path):
    category_ids = [row["id"] for row in (await categories(db_path))[:2]]
    program_id = await create_program(db_path, {
        "name": "Multi-category app", "description": "Description",
        "category_ids": category_ids, "file_id": "fid", "file_unique_id": "fuid",
    })

    program = await get_program(db_path, program_id)
    results = [await search_programs(db_path, "", category_id=category_id) for category_id in category_ids]

    expected_names = {row["name"] for row in (await categories(db_path))[:2]}
    assert set(program["category_name"].split(", ")) == expected_names
    assert all(any(row["id"] == program_id for row in result) for result in results)


@pytest.mark.asyncio
async def test_legacy_program_category_is_backfilled(db_path):
    from database.db import connect, init_db

    category_id = (await categories(db_path))[0]["id"]
    program_id = await create_program(db_path, {
        "name": "Legacy app", "description": "Description", "category_id": category_id,
        "file_id": "fid", "file_unique_id": "fuid",
    })
    async with await connect(db_path) as db:
        await db.execute("DELETE FROM program_categories")
        await db.commit()

    await init_db(db_path)
    found = await search_programs(db_path, "", category_id=category_id)
    assert any(row["id"] == program_id for row in found)


@pytest.mark.asyncio
async def test_program_can_be_searched_by_partial_name_and_synonym(db_path):
    category_id = (await categories(db_path))[0]["id"]
    await create_program(db_path, {
        "name": "Visual Studio Code", "description": "Editor", "category_id": category_id,
        "file_id": "fid", "file_unique_id": "fuid", "keywords": "vscode, vs code",
    })
    by_partial_name = await search_programs(db_path, "VISUAL")
    by_keyword = await search_programs(db_path, "vscode")
    assert len(by_partial_name) == 1
    assert len(by_keyword) == 1


@pytest.mark.asyncio
async def test_download_is_counted_only_for_existing_registered_user(db_path):
    from database.repositories import upsert_user
    category_id = (await categories(db_path))[0]["id"]
    program_id = await create_program(db_path, {
        "name": "Test", "description": "Test program", "category_id": category_id,
        "file_id": "fid", "file_unique_id": "fuid",
    })
    await upsert_user(db_path, 77, None, "Test User")
    await record_download(db_path, 77, program_id)
    program = await get_program(db_path, program_id)
    assert program["downloads"] == 1
