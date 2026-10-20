import pytest

from database.repositories import (
    create_request, get_request, upsert_user, update_request_status,
)


@pytest.mark.asyncio
async def test_request_is_created_and_status_updated(db_path):
    await upsert_user(db_path, 99, "tester", "Tester")
    request_id = await create_request(db_path, 99, "Example app", "Windows 11")
    row = await get_request(db_path, request_id)
    assert row["program_name"] == "Example app"
    assert row["status"] == "pending"
    assert await update_request_status(db_path, request_id, "in_progress", 123)
    row = await get_request(db_path, request_id)
    assert row["status"] == "in_progress"
    from database.db import connect
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "SELECT sender_id, message FROM request_messages WHERE request_id=? ORDER BY id DESC LIMIT 1",
            (request_id,),
        )
        history = await cursor.fetchone()
    assert history["sender_id"] == 123
    assert history["message"].endswith("in_progress")


@pytest.mark.asyncio
async def test_invalid_request_status_is_rejected(db_path):
    with pytest.raises(ValueError):
        await update_request_status(db_path, 1, "unknown", 123)
