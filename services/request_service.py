from database.repositories import create_request, get_request, update_request_status


async def submit_request(db_path: str, user_id: int, name: str, details: str) -> int:
    return await create_request(db_path, user_id, name, details)


async def change_request_status(
    db_path: str, request_id: int, status: str, changed_by: int
) -> bool:
    return await update_request_status(db_path, request_id, status, changed_by)


async def request_for_reply(db_path: str, request_id: int):
    return await get_request(db_path, request_id)
