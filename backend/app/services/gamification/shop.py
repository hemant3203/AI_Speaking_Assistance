"""The shop: browsing, buying and equipping. Purchases are serialised by the user row lock."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.models.gamification import LedgerEntry, OwnedItem, Profile
from app.models.user import User, lock_user
from app.services.catalog import COACHES, DEFAULT_COACH
from app.services.gamification.streaks import FREEZE_LIMIT

STREAK_FREEZE_ID = "streak_freeze"
_STREAK_FREEZE_PRICE = 40


def _owned_ids(db: Session, user_id: str) -> set[str]:
    owned = set(db.scalars(select(OwnedItem.item_id).where(OwnedItem.user_id == user_id)))
    owned.add(DEFAULT_COACH)
    return owned


def _sparks_shortfall_reason(price: int, sparks: int) -> str | None:
    return f"You need {price - sparks} more sparks." if sparks < price else None


def _freeze_view(profile: Profile, is_admin: bool) -> dict[str, Any]:
    price = 0 if is_admin else _STREAK_FREEZE_PRICE
    at_limit = profile.freezes >= FREEZE_LIMIT
    reason = (
        f"You already hold the maximum of {FREEZE_LIMIT} streak freezes."
        if at_limit
        else _sparks_shortfall_reason(price, profile.sparks)
    )
    return {
        "id": STREAK_FREEZE_ID,
        "kind": "consumable",
        "name": "Streak Freeze",
        "description": f"Covers one missed day so your streak survives. You hold {profile.freezes} of {FREEZE_LIMIT}.",
        "price": price,
        "icon": "Snowflake",
        "owned": profile.freezes > 0,
        "equipped": False,
        "can_buy": reason is None,
        "reason": reason,
    }


def _coach_view(coach_id: str, profile: Profile, owned: set[str], equipped_coach: str, is_admin: bool) -> dict[str, Any]:
    coach = COACHES[coach_id]
    price = 0 if is_admin else coach.price
    is_owned = coach_id in owned
    reason = "You already own this coach." if is_owned else _sparks_shortfall_reason(price, profile.sparks)
    return {
        "id": coach.id,
        "kind": "coach",
        "name": coach.name,
        "description": coach.description,
        "price": price,
        "icon": coach.icon,
        "owned": is_owned,
        "equipped": equipped_coach == coach_id,
        "can_buy": reason is None,
        "reason": reason,
    }


def shop_view(db: Session, user: User) -> dict[str, Any]:
    """Return the shop as this user sees it."""
    profile = db.get(Profile, user.id)
    owned = _owned_ids(db, user.id)
    items = [
        _freeze_view(profile, user.is_admin),
        *(_coach_view(cid, profile, owned, user.equipped_coach, user.is_admin) for cid in COACHES),
    ]
    return {"sparks": profile.sparks, "items": items}


def purchase(db: Session, user_id: str, item_id: str) -> dict[str, Any]:
    """Buy an item and commit. Holding the user lock means two tabs can't spend the same sparks."""
    if item_id != STREAK_FREEZE_ID and item_id not in COACHES:
        raise not_found("That item doesn't exist.")

    user = lock_user(db, user_id)
    profile = db.get(Profile, user_id)
    owned = _owned_ids(db, user_id)

    if item_id == STREAK_FREEZE_ID:
        if profile.freezes >= FREEZE_LIMIT:
            raise ApiError(409, "limit_reached", f"You can hold at most {FREEZE_LIMIT} streak freezes.")
        price, name = _STREAK_FREEZE_PRICE, "Streak Freeze"
    else:
        if item_id in owned:
            raise ApiError(409, "already_owned", "You already own this coach.")
        price, name = COACHES[item_id].price, COACHES[item_id].name

    if user.is_admin:
        price = 0
    if profile.sparks < price:
        raise ApiError(402, "insufficient_sparks", f"You need {price - profile.sparks} more sparks.")

    profile.sparks -= price
    if item_id == STREAK_FREEZE_ID:
        profile.freezes += 1
        item = _freeze_view(profile, user.is_admin)
    else:
        db.add(OwnedItem(user_id=user_id, item_id=item_id))
        owned.add(item_id)
        item = _coach_view(item_id, profile, owned, user.equipped_coach, user.is_admin)
    db.add(LedgerEntry(user_id=user_id, reason=f"Bought: {name}", xp=0, sparks=-price))
    db.commit()
    return {"sparks": profile.sparks, "item": item}


def equip_coach(db: Session, user: User, coach_id: str) -> User:
    """Equip an owned coach and commit. New sessions use it; a session already created keeps its coach."""
    if coach_id not in COACHES:
        raise not_found("That coach doesn't exist.")
    if coach_id not in _owned_ids(db, user.id):
        raise ApiError(403, "coach_locked", "Buy this coach in the shop first.")
    user.equipped_coach = coach_id
    db.commit()
    return user
