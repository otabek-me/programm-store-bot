import sqlite3

import pytest

from database.repositories import (
    categories, create_program, get_program, record_download, search_programs,
    update_program_field,
)
from admin.programs import _parse_category_ids
from migrate_sqlite_to_postgres import _read_source


def test_category_input_accepts_multiple_comma_separated_ids():
    assert _parse_category_ids("1,6", {1, 6}) == [1, 6]


def test_category_input_accepts_ids_with_spaces():
    assert _parse_category_ids("1, 6", {1, 6}) == [1, 6]


def test_category_input_accepts_mixed_spaces():
    assert _parse_category_ids(" 1 , 6 ", {1, 6}) == [1, 6]


def test_category_input_rejects_invalid_ids():
    with pytest.raises(ValueError):
        _parse_category_ids("1,abc", {1, 6})


def test_sqlite_importer_restores_legacy_category_relation(tmp_path):
    source_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(source_path) as source:
        source.executescript(
            """CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE programs(id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER);
            INSERT INTO categories(id, name) VALUES (6, 'Office');
            INSERT INTO programs(id, name, category_id) VALUES (41, 'Legacy app', 6);"""
        )

    imported = _read_source(source_path)

    assert imported["program_categories"] == (["program_id", "category_id"], [(41, 6)])


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
    assert all(sum(row["id"] == program_id for row in result) == 1 for result in results)


@pytest.mark.asyncio
async def test_legacy_category_field_accepts_comma_separated_ids(db_path):
    category_ids = [row["id"] for row in (await categories(db_path))[:2]]
    program_id = await create_program(db_path, {
        "name": "Legacy category edit", "description": "Description",
        "file_id": "fid", "file_unique_id": "fuid",
    })

    changed = await update_program_field(
        db_path, program_id, "category_id", f"{category_ids[0]},{category_ids[1]}"
    )
    program = await get_program(db_path, program_id)
    results = [await search_programs(db_path, "", category_id=category_id) for category_id in category_ids]

    assert changed
    assert len(program["category_name"].split(", ")) == 2
    assert all(sum(row["id"] == program_id for row in result) == 1 for result in results)


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
