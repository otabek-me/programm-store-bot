import pytest

from database.repositories import (
    cancel_broadcast_job, complete_broadcast_job, create_broadcast_job,
    get_broadcast_job, get_running_broadcast_job, start_broadcast_job,
    update_broadcast_job_progress, upsert_user,
)
from services.notification_service import broadcast, stop_broadcast


class MockBot:
    def __init__(self):
        self.calls = []
        self.errors = {}
        self.retry_after_users = set()
        self._retry_after_raised = set()

    async def copy_message(self, chat_id, from_chat_id, message_id):
        self.calls.append((chat_id, from_chat_id, message_id))
        if chat_id in self.errors:
            raise self.errors[chat_id]
        if chat_id in self.retry_after_users and chat_id not in self._retry_after_raised:
            self._retry_after_raised.add(chat_id)
            from aiogram.exceptions import TelegramRetryAfter
            raise TelegramRetryAfter(method="copyMessage", message="Too Many Requests", retry_after=0.1)


@pytest.mark.asyncio
async def test_create_and_complete_broadcast_job(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    job = await get_broadcast_job(db_path, job_id)
    assert job is not None
    assert job["admin_id"] == 1
    assert job["source_chat_id"] == 100
    assert job["source_message_id"] == 200
    assert job["status"] == "pending"
    assert job["recipient_count"] == 0

    await start_broadcast_job(db_path, job_id, 50)
    job = await get_broadcast_job(db_path, job_id)
    assert job["status"] == "running"
    assert job["recipient_count"] == 50

    await complete_broadcast_job(db_path, job_id, 45, 5)
    job = await get_broadcast_job(db_path, job_id)
    assert job["status"] == "completed"
    assert job["sent_count"] == 45
    assert job["failed_count"] == 5


@pytest.mark.asyncio
async def test_cancel_broadcast_job(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    await start_broadcast_job(db_path, job_id, 50)

    cancelled = await cancel_broadcast_job(db_path, job_id)
    assert cancelled is True

    job = await get_broadcast_job(db_path, job_id)
    assert job["status"] == "cancelled"

    cancelled = await cancel_broadcast_job(db_path, job_id)
    assert cancelled is False


@pytest.mark.asyncio
async def test_get_running_broadcast_job(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 2, "admin2", "Admin2")

    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    await start_broadcast_job(db_path, job_id, 50)

    running = await get_running_broadcast_job(db_path, 1)
    assert running is not None
    assert running["id"] == job_id

    running = await get_running_broadcast_job(db_path, 2)
    assert running is None


@pytest.mark.asyncio
async def test_update_broadcast_job_progress(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    await start_broadcast_job(db_path, job_id, 100)

    await update_broadcast_job_progress(db_path, job_id, 30, 10)
    job = await get_broadcast_job(db_path, job_id)
    assert job["sent_count"] == 30
    assert job["failed_count"] == 10


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_users(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 10, "user1", "User One")
    await upsert_user(db_path, 11, "user2", "User Two")
    await upsert_user(db_path, 12, "user3", "User Three")

    bot = MockBot()
    total, sent, failed = await broadcast(bot, db_path, 1, 100, 200)

    # Admin (1) + 3 users = 4 recipients total
    assert total == 4
    assert sent == 4
    assert failed == 0
    assert len(bot.calls) == 4
    user_ids = {call[0] for call in bot.calls}
    assert user_ids == {1, 10, 11, 12}


@pytest.mark.asyncio
async def test_broadcast_handles_blocked_users(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 10, "user1", "User One")
    await upsert_user(db_path, 11, "user2", "User Two")
    await upsert_user(db_path, 12, "user3", "User Three")

    bot = MockBot()
    from aiogram.exceptions import TelegramAPIError
    bot.errors[11] = TelegramAPIError(method="sendMessage", message="Forbidden")

    total, sent, failed = await broadcast(bot, db_path, 1, 100, 200)

    assert total == 4
    assert sent == 3
    assert failed == 1
    assert len(bot.calls) == 4


@pytest.mark.asyncio
async def test_broadcast_retry_after(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 10, "user1", "User One")

    bot = MockBot()
    from aiogram.exceptions import TelegramRetryAfter
    bot.retry_after_users.add(10)

    total, sent, failed = await broadcast(bot, db_path, 1, 100, 200)

    # Admin + user1 = 2 recipients
    assert total == 2
    assert sent == 2
    assert failed == 0


@pytest.mark.asyncio
async def test_broadcast_no_users(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    bot = MockBot()

    total, sent, failed = await broadcast(bot, db_path, 1, 100, 200)

    assert total == 1  # Only the admin exists
    assert sent == 1
    assert failed == 0


@pytest.mark.asyncio
async def test_broadcast_prevents_duplicate_running(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 10, "user1", "User One")

    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    await start_broadcast_job(db_path, job_id, 1)

    bot = MockBot()
    total, sent, failed = await broadcast(bot, db_path, 1, 100, 200)

    assert total == 0
    assert sent == 0
    assert failed == 0
    assert len(bot.calls) == 0


@pytest.mark.asyncio
async def test_stop_broadcast(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    await upsert_user(db_path, 10, "user1", "User One")
    await upsert_user(db_path, 11, "user2", "User Two")

    job_id = await create_broadcast_job(db_path, 1, 100, 200)
    await start_broadcast_job(db_path, job_id, 2)

    stopped = await stop_broadcast(db_path, 1)
    assert stopped is True

    job = await get_broadcast_job(db_path, job_id)
    assert job["status"] == "cancelled"

    stopped = await stop_broadcast(db_path, 1)
    assert stopped is False


@pytest.mark.asyncio
async def test_stop_broadcast_none_running(db_path):
    await upsert_user(db_path, 1, "admin", "Admin")
    stopped = await stop_broadcast(db_path, 1)
    assert stopped is False