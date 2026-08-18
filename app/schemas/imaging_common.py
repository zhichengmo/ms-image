from datetime import datetime, timezone


def normalize_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value_must_not_be_blank")
    return normalized


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime_timezone_required")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


__all__ = ["normalize_required_text", "normalize_utc_datetime"]
