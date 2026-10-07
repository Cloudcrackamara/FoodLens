"""Shared column helpers for all table models.

Conventions (see docs/SCHEMA.md):
- UUID primary keys named <entity>_id.
- Enums are stored as VARCHAR with a CHECK constraint listing allowed values.
- created_at on every table; updated_at only on tables whose rows are edited.
- Reviewable tables carry the same review columns; only admin services may set them.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_cls: type[Enum], name: str) -> SAEnum:
    """VARCHAR + CHECK constraint, storing enum values (not names)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [m.value for m in members],
    )


def uuid_pk() -> uuid.UUID:
    return Field(default_factory=uuid.uuid4, primary_key=True)


class CreatedAtMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "onupdate": utc_now},
        nullable=False,
    )


class ReviewFieldsMixin(SQLModel):
    """Who reviewed a record and when. Each table declares its own review_status enum."""

    reviewed_by_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="app_user.user_id", nullable=True
    )
    reviewed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    review_note: str | None = Field(default=None)
