"""Request and response models for authentication."""
import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.timeutils import is_valid_timezone
from app.schemas.common import UtcDatetime, strip_control_characters

# Deliberately loose: real validation of an address is sending mail to it, and stricter libraries
# reject addresses on internal or special-use domains that people legitimately use.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    normalised = value.strip().lower()
    if len(normalised) > 254 or not _EMAIL_PATTERN.match(normalised):
        raise ValueError("Enter a valid email address")
    return normalised


def _validate_timezone(value: str) -> str:
    if not is_valid_timezone(value):
        raise ValueError("Unknown timezone")
    return value


Email = Annotated[str, AfterValidator(_validate_email)]
Timezone = Annotated[str, AfterValidator(_validate_timezone)]
DisplayName = Annotated[
    str,
    AfterValidator(strip_control_characters),
    StringConstraints(strip_whitespace=True, min_length=2, max_length=40),
]


class RegisterRequest(BaseModel):
    """Body of POST /auth/register."""

    email: Email
    password: str = Field(min_length=8, max_length=128)
    display_name: DisplayName
    timezone: Timezone


class LoginRequest(BaseModel):
    """Body of POST /auth/login. Only the shape is checked, so errors don't describe password rules."""

    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class UpdateMeRequest(BaseModel):
    """Body of PATCH /auth/me."""

    display_name: DisplayName | None = None
    timezone: Timezone | None = None


class DeleteMeRequest(BaseModel):
    """Body of DELETE /auth/me."""

    password: str = Field(max_length=128)


class UserOut(BaseModel):
    """The public view of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    timezone: str
    equipped_coach: str
    is_admin: bool
    created_at: UtcDatetime


class UserEnvelope(BaseModel):
    """`{user}`, as returned by the auth endpoints."""

    user: UserOut
