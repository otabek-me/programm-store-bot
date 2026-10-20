def required_text(value: str, field_name: str, maximum: int = 1000) -> str:
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} bo‘sh bo‘lmasligi kerak.")
    if len(result) > maximum:
        raise ValueError(f"{field_name} {maximum} belgidan oshmasligi kerak.")
    return result


def optional_text(value: str, maximum: int = 300) -> str:
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"Matn {maximum} belgidan oshmasligi kerak.")
    return result


def format_size(size: int | None) -> str:
    if size is None:
        return "Noma’lum"
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{size} B"
        amount /= 1024
    return f"{size} B"
