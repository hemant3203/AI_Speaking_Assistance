"""Analytics overview."""
from typing import Annotated

from fastapi import APIRouter
from pydantic import AfterValidator

from app.api.deps import CurrentUser, DbSession
from app.core.timeutils import local_date
from app.schemas.analytics import Overview
from app.services.analytics import build_overview

router = APIRouter(prefix="/analytics", tags=["analytics"])

_ALLOWED_RANGES = (0, 7, 30, 90)


def _validate_range(days: int) -> int:
    # Not a Literal, because query values arrive as text and a Literal of ints never matches them.
    if days not in _ALLOWED_RANGES:
        raise ValueError("Must be 0, 7, 30 or 90")
    return days


@router.get("/overview", response_model=Overview)
def overview(user: CurrentUser, db: DbSession, days: Annotated[int, AfterValidator(_validate_range)] = 30) -> dict:
    """Return charts and insights for the last `days` days, or all time when `days` is 0."""
    return build_overview(db, user.id, days, local_date(user.timezone))
