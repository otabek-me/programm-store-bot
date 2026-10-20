from database.repositories import search_programs


async def search(db_path: str, query: str, *, sort: str = "relevance", page: int = 0, category_id: int | None = None):
    return await search_programs(
        db_path, query, sort=sort, category_id=category_id, limit=9, offset=max(page, 0) * 8
    )
