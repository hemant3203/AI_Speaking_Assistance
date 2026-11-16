"""Profile, badges, shop and reward activity."""
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.models.gamification import LedgerEntry, Profile
from app.schemas.auth import UserEnvelope
from app.schemas.gamification import ActivityOut, BadgeList, ProfileOut, PurchaseOut, ShopOut
from app.services.gamification import badges, shop
from app.services.gamification.profile import build_profile, unlocked_badges

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/profile", response_model=ProfileOut)
def profile(user: CurrentUser, db: DbSession, settings: AppSettings) -> dict:
    """Return XP, level, streak, quests, stats and limits."""
    return build_profile(db, user, settings)


@router.get("/badges", response_model=BadgeList)
def list_badges(user: CurrentUser, db: DbSession) -> dict:
    """Return every badge with the user's progress."""
    return {"items": badges.all_badge_views(db.get(Profile, user.id), unlocked_badges(db, user.id))}


@router.get("/shop", response_model=ShopOut)
def get_shop(user: CurrentUser, db: DbSession) -> dict:
    """Return the shop as this user sees it."""
    return shop.shop_view(db, user)


@router.post("/shop/{item_id}/purchase", response_model=PurchaseOut)
def purchase(item_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Buy an item."""
    return shop.purchase(db, user.id, item_id)


@router.post("/coaches/{coach_id}/equip", response_model=UserEnvelope)
def equip(coach_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Equip an owned coach."""
    return {"user": shop.equip_coach(db, user, coach_id)}


@router.get("/activity", response_model=ActivityOut)
def activity(user: CurrentUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict:
    """Return recent ledger entries, newest first."""
    rows = db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user.id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
    )
    return {
        "items": [
            {"created_at": row.created_at, "reason": row.reason, "xp": row.xp, "sparks": row.sparks} for row in rows
        ]
    }
