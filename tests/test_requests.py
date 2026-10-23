import pytest

from database.repositories import (
    create_request, get_request, requests, upsert_user, update_request_status,
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


@pytest.mark.asyncio
async def test_active_requests_include_pending_and_in_progress(db_path):
    await upsert_user(db_path, 10, "user1", "User One")
    await upsert_user(db_path, 11, "user2", "User Two")
    pending_id = await create_request(db_path, 10, "Pending app", "Details")
    in_progress_id = await create_request(db_path, 11, "In progress app", "Details")
    await update_request_status(db_path, in_progress_id, "in_progress", 123)
    await create_request(db_path, 10, "Completed app", "Details")
    await create_request(db_path, 11, "Rejected app", "Details")
    # We need to update statuses for completed/rejected ones - get their IDs first
    # Since we created 4 requests, IDs are pending_id, in_progress_id, +2, +3
    completed_id = pending_id + 2
    rejected_id = pending_id + 3
    await update_request_status(db_path, completed_id, "completed", 123)
    await update_request_status(db_path, rejected_id, "rejected", 123)

    active_rows = await requests(db_path, status=["pending", "in_progress"])
    active_ids = {row["id"] for row in active_rows}
    assert pending_id in active_ids
    assert in_progress_id in active_ids
    assert completed_id not in active_ids
    assert rejected_id not in active_ids


@pytest.mark.asyncio
async def test_active_requests_empty_when_none_pending(db_path):
    await upsert_user(db_path, 20, "user1", "User One")
    request_id = await create_request(db_path, 20, "Completed app", "Details")
    await update_request_status(db_path, request_id, "completed", 123)

    active_rows = await requests(db_path, status=["pending", "in_progress"])
    assert active_rows == []


@pytest.mark.asyncio
async def test_requests_are_ordered_by_id_desc(db_path):
    await upsert_user(db_path, 30, "user1", "User One")
    id1 = await create_request(db_path, 30, "First app", "Details")
    id2 = await create_request(db_path, 30, "Second app", "Details")

    rows = await requests(db_path, status=["pending", "in_progress"], limit=10, offset=0)
    assert len(rows) == 2
    assert rows[0]["id"] == id2  # newest first
    assert rows[1]["id"] == id1
