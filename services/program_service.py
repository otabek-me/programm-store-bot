from typing import Any

from database.repositories import create_program
from utils.validators import required_text


async def publish_program(db_path: str, data: dict[str, Any]) -> int:
    data["name"] = required_text(data["name"], "Dastur nomi", 120)
    data["description"] = required_text(data["description"], "Tavsif", 1500)
    data["keywords"] = data.get("keywords", "").strip()[:500]
    return await create_program(db_path, data)

