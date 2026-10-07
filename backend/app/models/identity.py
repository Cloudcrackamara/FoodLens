import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, uuid_pk


class AppUser(TimestampMixin, table=True):
    __tablename__ = "app_user"

    user_id: uuid.UUID = uuid_pk()
    # Stored lowercased by the auth service; uniqueness relies on that.
    email: str = Field(unique=True)
    password_hash: str
    display_name: str
    # Set only by seed/CLI. No API schema may accept it.
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)


class UserSession(CreatedAtMixin, table=True):
    """Server-side session for the httpOnly cookie. Only a hash of the token is stored."""

    __tablename__ = "user_session"

    session_id: uuid.UUID = uuid_pk()
    user_id: uuid.UUID = Field(foreign_key="app_user.user_id", index=True)
    token_hash: str = Field(unique=True)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
