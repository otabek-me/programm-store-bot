import pytest

from database.repositories import categories, create_program, search_programs


@pytest.mark.asyncio
async def test_categories_are_seeded_and_filterable(db_path):
    category_rows = await categories(db_path)
    assert len(category_rows) >= 10
    target = category_rows[0]
    program_id = await create_program(db_path, {
        "name": "Categorized app", "description": "A description",
        "category_id": target["id"], "file_id": "fid", "file_unique_id": "fuid",
    })
    found = await search_programs(db_path, "", category_id=target["id"])
    assert any(row["id"] == program_id for row in found)


@pytest.mark.asyncio
async def test_pagination_and_empty_search_results(db_path):
    category_id = (await categories(db_path))[0]["id"]
    for index in range(9):
        await create_program(db_path, {
            "name": f"Program {index}", "description": "Pagination test",
            "category_id": category_id, "file_id": f"fid-{index}",
            "file_unique_id": f"fuid-{index}",
        })
    first_page = await search_programs(db_path, "", limit=8, offset=0)
    second_page = await search_programs(db_path, "", limit=8, offset=8)
    no_matches = await search_programs(db_path, "definitely-not-found")
    assert len(first_page) == 8
    assert len(second_page) == 1
    assert no_matches == []
