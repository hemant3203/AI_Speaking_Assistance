"""Resolves which Gemini key to use for a user.

Today every user shares the server's key. This is the single place to change for the "bring your own
API key" item on the roadmap.
"""
from app.core.config import Settings


def resolve_api_key(settings: Settings, user_id: str | None = None) -> str | None:
    """Return the Gemini key for a user, or None if none is configured."""
    return settings.gemini_api_key.get_secret_value() or None
