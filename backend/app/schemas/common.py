"""Field types shared across schemas."""
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def strip_control_characters(value: str) -> str:
    """Remove control characters, which have no place in names or topics and could break prompts or logs."""
    return "".join(ch for ch in value if unicodedata.category(ch) != "Cc")


UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]
