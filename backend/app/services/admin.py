"""The admin account, defined by ADMIN_EMAIL and ADMIN_PASSWORD in .env.

.env is the source of truth: the listed account is the only admin, and its password always matches.
That also makes changing the admin password a matter of editing .env and restarting.
"""
import logging

from sqlalchemy import select, update

from app.core.config import Settings
from app.core.database import session_scope
from app.core.security import hash_password, verify_password
from app.models.gamification import Profile
from app.models.user import User

logger = logging.getLogger("spotlight.admin")

_MIN_PASSWORD_LENGTH = 8
_DISPLAY_NAME = "Admin"
_TIMEZONE = "Asia/Kolkata"


def ensure_admin(settings: Settings) -> None:
    """Create or update the admin account, and remove admin rights from every other account."""
    email = settings.admin_email.strip().lower()
    password = settings.admin_password.get_secret_value()

    with session_scope() as db:
        others = User.is_admin.is_(True) if not email else (User.is_admin.is_(True) & (User.email != email))
        db.execute(update(User).where(others).values(is_admin=False))

        if not email or not password:
            logger.info("no admin account configured")
            return
        if len(password) < _MIN_PASSWORD_LENGTH:
            logger.warning("admin account skipped: ADMIN_PASSWORD needs at least %d characters", _MIN_PASSWORD_LENGTH)
            return

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(password),
                display_name=_DISPLAY_NAME,
                timezone=_TIMEZONE,
                is_admin=True,
            )
            db.add(user)
            db.flush()
            db.add(Profile(user_id=user.id))
            logger.info("admin account created")
            return

        # Replacing the password matters: someone else could have registered this email first, and
        # promoting their account without this would hand admin rights to whoever knows their password.
        if not verify_password(user.password_hash, password):
            user.password_hash = hash_password(password)
        user.is_admin = True
