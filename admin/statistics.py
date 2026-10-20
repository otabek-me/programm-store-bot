from database.repositories import admin_stats


async def statistics_text(db_path: str) -> str:
    stats = await admin_stats(db_path)
    return (
        f"Jami dasturlar: {stats['programs']}\n"
        f"Faol: {stats['active']}\nYashirin: {stats['hidden']}\n"
        f"Kategoriyalar: {stats['categories']}\nFoydalanuvchilar: {stats['users']}\n"
        f"Bugun yangi foydalanuvchilar: {stats['new_users']}\n"
        f"Jami yuklab olishlar: {stats['downloads']}\n"
        f"Bugungi yuklab olishlar: {stats['today_downloads']}\n"
        f"Kutilayotgan so‘rovlar: {stats['pending_requests']}"
    )
