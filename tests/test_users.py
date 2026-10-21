import html

import pytest

from admin.users import _escape, _format_user_row, _format_users_message
from database.repositories import admin_categories, admin_user_stats


def test_escape_html_special_characters():
    """Foydalanuvchi kiritgan maxsus belgilar HTML formatini buzmasligi kerak."""
    assert _escape("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;"
    assert _escape('O\'Brien & Co.') == "O&#39;Brien &amp; Co."
    assert _escape(None) == ""
    assert _escape("") == ""


def test_format_user_row_with_username():
    row = {"first_name": "Otabek", "username": "Otabekk_05", "user_id": 5867100858, "download_count": 6, "is_blocked": 0}
    text = _format_user_row(1, row)
    assert "<b>1. Otabek</b>" in text
    assert "Username: @Otabekk_05" in text
    assert "Telegram ID: <code>5867100858</code>" in text
    assert "Yuklab olishlar: <b>6 ta</b>" in text
    assert "🟢 Faol" in text


def test_format_user_row_without_username():
    row = {"first_name": "Omonov", "username": None, "user_id": 8424375506, "download_count": 0, "is_blocked": 0}
    text = _format_user_row(2, row)
    assert "Username: mavjud emas" in text


def test_format_user_row_blocked():
    row = {"first_name": "Blocked User", "username": None, "user_id": 111, "download_count": 0, "is_blocked": 1}
    text = _format_user_row(1, row)
    assert "🔴 Bloklangan" in text


def test_format_user_row_escapes_special_chars():
    row = {"first_name": "<script>", "username": "evil&user", "user_id": 999, "download_count": 0, "is_blocked": 0}
    text = _format_user_row(1, row)
    assert "&lt;script&gt;" in text
    assert "evil&amp;user" in text


def test_format_users_message_structure():
    stats = {"total": 25, "active": 20, "blocked": 5, "total_downloads": 42}
    rows = [
        {"first_name": "User1", "username": "u1", "user_id": 1, "download_count": 3, "is_blocked": 0},
        {"first_name": "User2", "username": None, "user_id": 2, "download_count": 0, "is_blocked": 1},
    ]
    text = _format_users_message(0, stats, rows, has_next=False)
    assert "<b>👥 FOYDALANUVCHILAR</b>" in text
    assert "<b>📊 Umumiy statistika</b>" in text
    assert "├ Jami: <b>25</b>" in text
    assert "├ Faol: <b>20</b>" in text
    assert "└ Yuklab olishlar: <b>42 ta</b>" in text
    assert "📄 Sahifa: 1/3" in text


def test_format_users_message_empty():
    stats = {"total": 0, "active": 0, "blocked": 0, "total_downloads": 0}
    text = _format_users_message(0, stats, [], has_next=False)
    assert "📄 Sahifa: 1/1" in text


@pytest.mark.asyncio
async def test_admin_user_stats(db_path):
    from database.repositories import upsert_user

    await upsert_user(db_path, 1, "user1", "User One")
    await upsert_user(db_path, 2, None, "User Two")
    await upsert_user(db_path, 3, "user3", "User Three")

    stats = await admin_user_stats(db_path)
    assert stats["total"] == 3
    assert stats["active"] == 3
    assert stats["blocked"] == 0
    assert stats["total_downloads"] == 0


@pytest.mark.asyncio
async def test_admin_categories_ordered_by_id(db_path):
    rows = await admin_categories(db_path)
    ids = [row["id"] for row in rows]
    assert ids == sorted(ids), f"Kategoriyalar ID bo‘yicha saralangan emas: {ids}"