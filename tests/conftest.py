import pytest

from database.db import init_db


@pytest.fixture
async def db_path(tmp_path):
    path = tmp_path / "bot.sqlite3"
    await init_db(path)
    return str(path)
