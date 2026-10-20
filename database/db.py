from pathlib import Path
from typing import Any

import aiosqlite
import psycopg
from psycopg.rows import dict_row

from database.postgres_schema import POSTGRES_SCHEMA


DatabaseErrors = (aiosqlite.Error, psycopg.Error)
DatabaseIntegrityErrors = (aiosqlite.IntegrityError, psycopg.IntegrityError)


class _ConnectionContext:
    def __init__(self, connection: Any, is_postgres: bool) -> None:
        self.connection = connection
        self.is_postgres = is_postgres

    async def __aenter__(self) -> "_ConnectionContext":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.connection.close()

    def _adapt_query(self, query: str) -> str:
        if not self.is_postgres:
            return query
        return (
            query.replace("?", "%s")
            .replace("strftime('%Y-%m-%dT%H:%M:%fZ','now')", "CURRENT_TIMESTAMP")
            .replace("group_concat(c.name, ', ')", "string_agg(c.name, ', ')")
            .replace("date(first_seen_at)=date('now')", "first_seen_at::date=CURRENT_DATE")
            .replace("date(downloaded_at)=date('now')", "downloaded_at::date=CURRENT_DATE")
        )

    async def execute(self, query: str, params: tuple[Any, ...] = ()):
        return await self.connection.execute(self._adapt_query(query), params)

    async def executemany(self, query: str, params) -> None:
        if self.is_postgres:
            async with self.connection.cursor() as cursor:
                await cursor.executemany(self._adapt_query(query), params)
        else:
            await self.connection.executemany(self._adapt_query(query), params)

    async def commit(self) -> None:
        await self.connection.commit()


DEFAULT_CATEGORIES = (
    "Windows dasturlari",
    "Android ilovalari",
    "Dasturlash vositalari",
    "Grafik va dizayn",
    "Video va audio",
    "Ofis dasturlari",
    "Brauzerlar",
    "Xavfsizlik vositalari",
    "Drayverlar",
    "Boshqa dasturlar",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_active_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    download_count INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0 CHECK (is_blocked IN (0, 1))
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    file_name TEXT,
    mime_type TEXT,
    file_size INTEGER,
    version TEXT,
    operating_system TEXT,
    keywords TEXT NOT NULL DEFAULT '',
    downloads INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_recommended INTEGER NOT NULL DEFAULT 0 CHECK (is_recommended IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS program_categories (
    program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (program_id, category_id)
);
CREATE TABLE IF NOT EXISTS download_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    downloaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS software_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    program_name TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS request_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES software_requests(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS broadcast_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    recipient_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS program_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_programs_active_category ON programs(is_active, category_id);
CREATE INDEX IF NOT EXISTS idx_program_categories_category ON program_categories(category_id, program_id);
CREATE INDEX IF NOT EXISTS idx_programs_created ON programs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_download_logs_date ON download_logs(downloaded_at);
CREATE INDEX IF NOT EXISTS idx_requests_status ON software_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_requests_user ON software_requests(user_id);
"""


async def connect(database: str | Path) -> _ConnectionContext:
    database_value = str(database)
    if database_value.startswith(("postgresql://", "postgres://")):
        connection = await psycopg.AsyncConnection.connect(
            database_value, row_factory=dict_row, connect_timeout=10, prepare_threshold=None
        )
        await connection.execute("CREATE SCHEMA IF NOT EXISTS programm_store_bot")
        await connection.execute("SET LOCAL search_path TO programm_store_bot")
        return _ConnectionContext(connection, is_postgres=True)

    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.execute("PRAGMA journal_mode = WAL")
    return _ConnectionContext(connection, is_postgres=False)


async def init_db(database: str | Path, *, seed_categories: bool = True) -> None:
    async with await connect(database) as db:
        schema = POSTGRES_SCHEMA if db.is_postgres else SCHEMA
        for statement in schema.split(";"):
            if statement.strip():
                await db.execute(statement)
        if seed_categories:
            await db.executemany(
                "INSERT INTO categories(name) VALUES (?) ON CONFLICT DO NOTHING",
                ((name,) for name in DEFAULT_CATEGORIES),
            )
        if db.is_postgres:
            await db.execute(
                """INSERT INTO program_categories(program_id, category_id)
                SELECT id, category_id FROM programs WHERE category_id IS NOT NULL
                ON CONFLICT DO NOTHING"""
            )
        else:
            await db.execute(
                """INSERT OR IGNORE INTO program_categories(program_id, category_id)
                SELECT id, category_id FROM programs WHERE category_id IS NOT NULL"""
            )
        await db.commit()
