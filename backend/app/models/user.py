"""The user account aggregate."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, false, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.core.timeutils import utcnow


class User(Base):
    """A registered user. Every other table cascades from this row."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Stored lower-case, so this unique constraint is what decides duplicate registrations.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(40))
    timezone: Mapped[str] = mapped_column(String(64))
    equipped_coach: Mapped[str] = mapped_column(String(32), default="mentor")
    # Only ensure_admin sets this, so no API request can make someone an admin.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def lock_user(db: Session, user_id: str) -> User | None:
    """Take `SELECT ... FOR UPDATE` on the user row, or return None if the user no longer exists.

    This is the serialisation point for a user's wallet, streak and rewards. Every transaction that
    writes several of a user's rows must call this first. A single lock order is what rules out
    deadlocks: inserting a child row takes FOR KEY SHARE on this row, which conflicts with FOR UPDATE.
    """
    return db.scalar(select(User).where(User.id == user_id).with_for_update())
