from typing import Any

from database.db import connect


async def upsert_user(db_path: str, user_id: int, username: str | None, first_name: str) -> None:
    async with await connect(db_path) as db:
        await db.execute(
            """INSERT INTO users(user_id, username, first_name) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
            first_name=excluded.first_name, last_active_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
            (user_id, username, first_name),
        )
        await db.commit()


async def fetch_all(db: Any, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cursor = await db.execute(query, params)
    return await cursor.fetchall()


async def categories(db_path: str) -> list[Any]:
    async with await connect(db_path) as db:
        return await fetch_all(db, "SELECT id, name FROM categories ORDER BY lower(name)")


async def add_category(db_path: str, name: str) -> int:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO categories(name) VALUES (?) RETURNING id", (name.strip(),)
        )
        category_id = (await cursor.fetchone())["id"]
        await db.commit()
        return category_id


async def rename_category(db_path: str, category_id: int, name: str) -> bool:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "UPDATE categories SET name=? WHERE id=?", (name.strip(), category_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_category(db_path: str, category_id: int) -> bool:
    async with await connect(db_path) as db:
        cursor = await db.execute("DELETE FROM categories WHERE id=?", (category_id,))
        await db.commit()
        return cursor.rowcount > 0


async def create_program(db_path: str, data: dict[str, Any]) -> int:
    category_ids = data.get("category_ids")
    if category_ids is None:
        category_ids = [data["category_id"]] if data.get("category_id") is not None else []
    category_ids = list(dict.fromkeys(category_ids))
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """INSERT INTO programs
            (name, description, category_id, file_id, file_unique_id, file_name, mime_type,
             file_size, version, operating_system, keywords, is_active, is_recommended)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?) RETURNING id""",
            (
                data["name"], data["description"], category_ids[0] if category_ids else None,
                data["file_id"], data["file_unique_id"], data.get("file_name"),
                data.get("mime_type"), data.get("file_size"), data.get("version"),
                data.get("operating_system"), data.get("keywords", ""),
                int(data.get("is_recommended", False)),
            ),
        )
        program_id = (await cursor.fetchone())["id"]
        await db.executemany(
            "INSERT INTO program_categories(program_id, category_id) VALUES (?, ?)",
            ((program_id, category_id) for category_id in category_ids),
        )
        await db.commit()
        return program_id


async def save_draft(db_path: str, admin_id: int, payload: str, draft_id: int | None = None) -> int:
    async with await connect(db_path) as db:
        if draft_id is None:
            cursor = await db.execute(
                "INSERT INTO program_drafts(admin_id, payload) VALUES (?, ?) RETURNING id",
                (admin_id, payload),
            )
            draft_id = (await cursor.fetchone())["id"]
        else:
            await db.execute(
                """UPDATE program_drafts SET payload=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=? AND admin_id=?""",
                (payload, draft_id, admin_id),
            )
        await db.commit()
        return draft_id


async def get_draft(db_path: str, admin_id: int, draft_id: int) -> Any | None:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM program_drafts WHERE id=? AND admin_id=?", (draft_id, admin_id)
        )
        return await cursor.fetchone()


async def remove_draft(db_path: str, admin_id: int, draft_id: int) -> None:
    async with await connect(db_path) as db:
        await db.execute("DELETE FROM program_drafts WHERE id=? AND admin_id=?", (draft_id, admin_id))
        await db.commit()


async def list_drafts(db_path: str, admin_id: int) -> list[Any]:
    async with await connect(db_path) as db:
        return await fetch_all(
            db, "SELECT id, created_at FROM program_drafts WHERE admin_id=? ORDER BY updated_at DESC",
            (admin_id,),
        )


async def get_program(db_path: str, program_id: int, active_only: bool = False) -> Any | None:
    async with await connect(db_path) as db:
        query = """SELECT p.*,
        (SELECT group_concat(c.name, ', ') FROM program_categories pc
        JOIN categories c ON c.id=pc.category_id WHERE pc.program_id=p.id) AS category_name
        FROM programs p WHERE p.id=?"""
        if active_only:
            query += " AND p.is_active=1"
        cursor = await db.execute(query, (program_id,))
        return await cursor.fetchone()


async def search_programs(
    db_path: str, query: str = "", *, sort: str = "relevance", category_id: int | None = None,
    limit: int = 8, offset: int = 0,
) -> list[Any]:
    text = query.strip().casefold()
    sql = """SELECT p.id, p.name, p.description, p.version, p.operating_system,
    p.downloads, p.is_recommended, p.created_at,
    (SELECT group_concat(c.name, ', ') FROM program_categories pc
    JOIN categories c ON c.id=pc.category_id WHERE pc.program_id=p.id) AS category_name
    FROM programs p WHERE p.is_active=1"""
    params: list[Any] = []
    if text:
        sql += """ AND (lower(p.name) LIKE ? ESCAPE '\\' OR lower(p.keywords) LIKE ? ESCAPE '\\'
        OR lower(coalesce(p.description, '')) LIKE ? ESCAPE '\\')"""
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        params.extend((pattern, pattern, pattern))
    if category_id is not None:
        sql += " AND EXISTS (SELECT 1 FROM program_categories pc WHERE pc.program_id=p.id AND pc.category_id=?)"
        params.append(category_id)
    order_by = {
        "popular": "p.downloads DESC, lower(p.name)",
        "newest": "p.created_at DESC, p.id DESC",
        "relevance": """p.is_recommended DESC,
            CASE WHEN lower(p.name)=? THEN 0 WHEN lower(p.name) LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END,
            p.downloads DESC, lower(p.name)""",
    }
    if sort not in order_by:
        raise ValueError("Noma’lum saralash turi.")
    if sort == "relevance" and text:
        params.extend((text, f"{text.replace('%', r'\%').replace('_', r'\_')}%"))
    elif sort == "relevance":
        sql += " ORDER BY p.is_recommended DESC, p.downloads DESC, lower(p.name) LIMIT ? OFFSET ?"
        params.extend((limit, offset))
        async with await connect(db_path) as db:
            return await fetch_all(db, sql, tuple(params))
    sql += f" ORDER BY {order_by[sort]} LIMIT ? OFFSET ?"
    params.extend((limit, offset))
    async with await connect(db_path) as db:
        return await fetch_all(db, sql, tuple(params))


async def record_download(db_path: str, user_id: int, program_id: int) -> None:
    async with await connect(db_path) as db:
        await db.execute("INSERT INTO download_logs(user_id, program_id) VALUES (?, ?)", (user_id, program_id))
        await db.execute("UPDATE programs SET downloads=downloads+1 WHERE id=?", (program_id,))
        await db.execute("UPDATE users SET download_count=download_count+1 WHERE user_id=?", (user_id,))
        await db.commit()


async def create_request(db_path: str, user_id: int, name: str, details: str) -> int:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO software_requests(user_id, program_name, details) VALUES (?, ?, ?) RETURNING id",
            (user_id, name.strip(), details.strip()),
        )
        request_id = (await cursor.fetchone())["id"]
        await db.execute(
            "INSERT INTO request_messages(request_id, sender_id, message) VALUES (?, ?, ?)",
            (request_id, user_id, details.strip() or name.strip()),
        )
        await db.commit()
        return request_id


async def update_request_status(
    db_path: str, request_id: int, status: str, changed_by: int
) -> bool:
    if status not in {"pending", "in_progress", "completed", "rejected"}:
        raise ValueError("Noto‘g‘ri so‘rov holati.")
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """UPDATE software_requests SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id=?""", (status, request_id),
        )
        if cursor.rowcount:
            await db.execute(
                "INSERT INTO request_messages(request_id, sender_id, message) VALUES (?, ?, ?)",
                (request_id, changed_by, f"Status o‘zgartirildi: {status}"),
            )
        await db.commit()
        return cursor.rowcount > 0


async def add_request_message(db_path: str, request_id: int, sender_id: int, message: str) -> None:
    async with await connect(db_path) as db:
        await db.execute(
            "INSERT INTO request_messages(request_id, sender_id, message) VALUES (?, ?, ?)",
            (request_id, sender_id, message),
        )
        await db.commit()


async def requests(db_path: str, *, status: str | None = None, limit: int = 10, offset: int = 0) -> list[Any]:
    async with await connect(db_path) as db:
        if status:
            return await fetch_all(
                db, """SELECT r.*, u.username, u.first_name FROM software_requests r
                JOIN users u ON u.user_id=r.user_id WHERE r.status=? ORDER BY r.id DESC LIMIT ? OFFSET ?""",
                (status, limit, offset),
            )
        return await fetch_all(
            db, """SELECT r.*, u.username, u.first_name FROM software_requests r
            JOIN users u ON u.user_id=r.user_id ORDER BY r.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        )


async def get_request(db_path: str, request_id: int) -> Any | None:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """SELECT r.*, u.username, u.first_name FROM software_requests r
            JOIN users u ON u.user_id=r.user_id WHERE r.id=?""", (request_id,),
        )
        return await cursor.fetchone()


async def admin_stats(db_path: str) -> dict[str, Any]:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """SELECT (SELECT count(*) FROM programs) AS programs,
            (SELECT count(*) FROM programs WHERE is_active=1) AS active,
            (SELECT count(*) FROM programs WHERE is_active=0) AS hidden,
            (SELECT count(*) FROM categories) AS categories,
            (SELECT count(*) FROM users) AS users,
            (SELECT count(*) FROM users WHERE date(first_seen_at)=date('now')) AS new_users,
            (SELECT coalesce(sum(downloads),0) FROM programs) AS downloads,
            (SELECT count(*) FROM download_logs WHERE date(downloaded_at)=date('now')) AS today_downloads,
            (SELECT count(*) FROM software_requests WHERE status='pending') AS pending_requests"""
        )
        row = await cursor.fetchone()
        popular = await fetch_all(db, "SELECT id, name, downloads FROM programs ORDER BY downloads DESC LIMIT 5")
        recent = await fetch_all(db, "SELECT id, name, created_at FROM programs ORDER BY id DESC LIMIT 5")
        return {**dict(row), "popular": popular, "recent": recent}


async def toggle_program_active(db_path: str, program_id: int) -> bool:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """UPDATE programs SET is_active=1-is_active,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""", (program_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_program_field(db_path: str, program_id: int, field: str, value: Any) -> bool:
    if field == "category_id":
        category_ids = [] if value is None else [value]
        return await replace_program_categories(db_path, program_id, category_ids)
    allowed_fields = {
        "name", "description", "category_id", "keywords", "version",
        "operating_system", "file_id", "file_unique_id", "file_name", "mime_type", "file_size",
    }
    if field not in allowed_fields:
        raise ValueError("Bu maydonni tahrirlash mumkin emas.")
    async with await connect(db_path) as db:
        cursor = await db.execute(
            f"""UPDATE programs SET {field}=?,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
            (value, program_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def replace_program_categories(db_path: str, program_id: int, category_ids: list[int]) -> bool:
    category_ids = list(dict.fromkeys(category_ids))
    async with await connect(db_path) as db:
        cursor = await db.execute(
            "UPDATE programs SET category_id=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
            (category_ids[0] if category_ids else None, program_id),
        )
        if cursor.rowcount == 0:
            return False
        await db.execute("DELETE FROM program_categories WHERE program_id=?", (program_id,))
        await db.executemany(
            "INSERT INTO program_categories(program_id, category_id) VALUES (?, ?)",
            ((program_id, category_id) for category_id in category_ids),
        )
        await db.commit()
        return True


async def replace_program_file(db_path: str, program_id: int, document: Any) -> bool:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """UPDATE programs SET file_id=?, file_unique_id=?, file_name=?, mime_type=?, file_size=?,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
            (
                document.file_id, document.file_unique_id, document.file_name,
                document.mime_type, document.file_size, program_id,
            ),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_program(db_path: str, program_id: int) -> bool:
    async with await connect(db_path) as db:
        cursor = await db.execute(
            """UPDATE programs SET is_active=0,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
            (program_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_users(db_path: str, limit: int = 10, offset: int = 0) -> list[Any]:
    async with await connect(db_path) as db:
        return await fetch_all(
            db, "SELECT user_id, username, first_name, last_active_at, download_count, is_blocked FROM users ORDER BY last_active_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )


async def list_programs_admin(db_path: str, limit: int = 8, offset: int = 0) -> list[Any]:
    async with await connect(db_path) as db:
        return await fetch_all(
            db, """SELECT p.id, p.name, p.is_active, p.downloads,
            (SELECT group_concat(c.name, ', ') FROM program_categories pc
            JOIN categories c ON c.id=pc.category_id WHERE pc.program_id=p.id) AS category_name
            FROM programs p
            ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        )


async def broadcast_targets(db_path: str) -> list[int]:
    async with await connect(db_path) as db:
        rows = await fetch_all(db, "SELECT user_id FROM users WHERE is_blocked=0")
        return [int(row["user_id"]) for row in rows]


async def log_broadcast(
    db_path: str, admin_id: int, message: str, recipient_count: int, sent_count: int, failed_count: int
) -> None:
    async with await connect(db_path) as db:
        await db.execute(
            """INSERT INTO broadcast_logs(admin_id, message, recipient_count, sent_count, failed_count)
            VALUES (?, ?, ?, ?, ?)""",
            (admin_id, message, recipient_count, sent_count, failed_count),
        )
        await db.commit()
