from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    database_url: str
    log_level: str
    allowed_file_extensions: frozenset[str] | None


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "your_telegram_bot_token":
        raise ValueError("BOT_TOKEN .env faylida sozlanmagan.")

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    try:
        admin_ids = frozenset(
            int(item.strip()) for item in raw_admin_ids.split(",") if item.strip()
        )
    except ValueError as exc:
        raise ValueError("ADMIN_IDS vergul bilan ajratilgan butun sonlar bo‘lishi kerak.") from exc
    if not admin_ids:
        raise ValueError("ADMIN_IDS ichida kamida bitta administrator ID bo‘lishi kerak.")

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL PostgreSQL ulanish manzili .env faylida sozlanmagan.")
    raw_extensions = os.getenv("ALLOWED_FILE_EXTENSIONS", "").strip()
    extensions = (
        frozenset(
            item.strip().casefold() if item.strip().startswith(".") else f".{item.strip().casefold()}"
            for item in raw_extensions.split(",") if item.strip()
        )
        if raw_extensions else None
    )
    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        database_url=database_url,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        allowed_file_extensions=extensions,
    )
