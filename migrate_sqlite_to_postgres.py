import argparse
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv

from database.db import DEFAULT_CATEGORIES, connect, init_db

TABLE_COLUMNS = {
    "users": (
        "user_id", "username", "first_name", "first_seen_at", "last_active_at",
        "download_count", "is_blocked",
    ),
    "categories": ("id", "name", "created_at"),
    "programs": (
        "id", "name", "description", "category_id", "file_id", "file_unique_id",
        "file_name", "mime_type", "file_size", "version", "operating_system",
        "keywords", "downloads", "is_active", "is_recommended", "created_at", "updated_at",
    ),
    "program_categories": ("program_id", "category_id"),
    "download_logs": ("id", "user_id", "program_id", "downloaded_at"),
    "software_requests": (
        "id", "user_id", "program_name", "details", "status", "created_at", "updated_at",
    ),
    "request_messages": ("id", "request_id", "sender_id", "message", "created_at"),
    "bot_settings": ("key", "value"),
    "broadcast_logs": (
        "id", "admin_id", "message", "recipient_count", "sent_count", "failed_count", "created_at",
    ),
    "program_drafts": ("id", "admin_id", "payload", "created_at", "updated_at"),
}
TIMESTAMP_COLUMNS = {
    "first_seen_at", "last_active_at", "created_at", "updated_at", "downloaded_at",
}
IDENTITY_TABLES = (
    "categories", "programs", "download_logs", "software_requests",
    "request_messages", "broadcast_logs", "program_drafts",
)


def _read_source(source_path: Path) -> dict[str, tuple[list[str], list[tuple]]]:
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite fayli topilmadi: {source_path}")

    imported = {}
    source_uri = source_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        source.row_factory = sqlite3.Row
        existing_tables = {
            row["name"]
            for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table, allowed_columns in TABLE_COLUMNS.items():
            if table not in existing_tables:
                continue
            source_columns = {
                row["name"] for row in source.execute(f"PRAGMA table_info({table})")
            }
            columns = [column for column in allowed_columns if column in source_columns]
            rows = [tuple(row[column] for column in columns) for row in source.execute(f"SELECT * FROM {table}")]
            imported[table] = (columns, rows)

        if "program_categories" not in imported and "programs" in imported:
            program_columns, program_rows = imported["programs"]
            if "category_id" in program_columns:
                program_index = program_columns.index("id")
                category_index = program_columns.index("category_id")
                relations = [
                    (row[program_index], row[category_index])
                    for row in program_rows if row[category_index] is not None
                ]
                imported["program_categories"] = (
                    ["program_id", "category_id"], relations,
                )
    return imported


def _postgres_value(column: str, value):
    if column not in TIMESTAMP_COLUMNS or value is None or isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def migrate(source_path: Path, database_url: str) -> None:
    imported = _read_source(source_path)
    await init_db(database_url, seed_categories=False)

    async with await connect(database_url) as db:
        for table, (columns, rows) in imported.items():
            if not columns or not rows:
                continue
            column_sql = ", ".join(columns)
            placeholders = ", ".join("%s" for _ in columns)
            statement = (
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
                "ON CONFLICT DO NOTHING"
            )
            values = [
                tuple(_postgres_value(column, value) for column, value in zip(columns, row))
                for row in rows
            ]
            await db.executemany(statement, values)
            print(f"{table}: {len(rows)} yozuv ko‘chirildi")

        await db.execute(
            """INSERT INTO program_categories(program_id, category_id)
            SELECT id, category_id FROM programs WHERE category_id IS NOT NULL
            ON CONFLICT DO NOTHING"""
        )
        await db.executemany(
            "INSERT INTO categories(name) VALUES (?) ON CONFLICT DO NOTHING",
            ((name,) for name in DEFAULT_CATEGORIES),
        )
        for table in IDENTITY_TABLES:
            await db.execute(
                f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                EXISTS (SELECT 1 FROM {table}))"""
            )
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite ma’lumotlarini PostgreSQL’ga ko‘chirish")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path(r"D:\Downloads\bot.sqlite3"),
        help="Eski SQLite faylining yo‘li",
    )
    args = parser.parse_args()

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("DATABASE_URL .env faylida PostgreSQL URL sifatida sozlanmagan.")
    asyncio.run(migrate(args.source, database_url), loop_factory=asyncio.SelectorEventLoop)
    print("SQLite ma’lumotlari PostgreSQL’ga ko‘chirildi.")


if __name__ == "__main__":
    main()