import re
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.exceptions import AppError


def validate_currency(value: str) -> str:
    v = (value or "").upper()
    if not re.fullmatch(r"[A-Z]{3}", v):
        raise ValueError("currency must be a 3-letter ISO code")
    return v


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValueError("unknown timezone") from exc
    return value


def safe_filename(name: str) -> str:
    """Strip any path, keep a conservative character set."""
    base = Path(name or "upload").name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "upload"
    return base[:120]


def unique_storage_name(original: str) -> str:
    return f"{uuid.uuid4().hex}_{safe_filename(original)}"


def validate_upload(filename: str, size: int, allowed_ext: set[str], max_bytes: int) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise AppError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed_ext))}.",
                       code="UNSUPPORTED_FILE_TYPE", status_code=415)
    if size <= 0:
        raise AppError("Uploaded file is empty.", code="EMPTY_FILE")
    if size > max_bytes:
        raise AppError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.", code="FILE_TOO_LARGE",
                       status_code=413)
    return ext


def looks_binary(sample: bytes) -> bool:
    return b"\x00" in sample
