import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import (
    CreatedAtMixin,
    ReviewFieldsMixin,
    TimestampMixin,
    enum_column,
    uuid_pk,
)
from app.models.enums import (
    AnnouncementStatus,
    AttachmentMimeType,
    ChangeNoticeStatus,
    ChangeType,
)

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


class ChangeNotice(TimestampMixin, ReviewFieldsMixin, table=True):
    """Proposed change to published data. Applied only when an admin approves it."""

    __tablename__ = "change_notice"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(product_id, batch_id, credential_id, location_id) = 1",
            name="exactly_one_target",
        ),
    )

    notice_id: uuid.UUID = uuid_pk()
    company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)

    # Exactly one target is set.
    product_id: uuid.UUID | None = Field(default=None, foreign_key="product.product_id")
    batch_id: uuid.UUID | None = Field(default=None, foreign_key="product_batch.batch_id")
    credential_id: uuid.UUID | None = Field(
        default=None, foreign_key="credential_record.credential_id"
    )
    location_id: uuid.UUID | None = Field(default=None, foreign_key="supplier_location.location_id")

    change_type: ChangeType = Field(sa_type=enum_column(ChangeType, "change_type"))
    reason: str = Field(sa_type=Text)
    effective_date: date | None = None
    submitted_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")
    review_status: ChangeNoticeStatus = Field(
        default=ChangeNoticeStatus.PENDING_REVIEW,
        sa_type=enum_column(ChangeNoticeStatus, "change_notice_status"),
    )


class ChangeNoticeField(CreatedAtMixin, table=True):
    """One proposed field change. Append-only; applied_old_value is set once on approval."""

    __tablename__ = "change_notice_field"
    __table_args__ = (UniqueConstraint("notice_id", "field_name"),)

    field_change_id: uuid.UUID = uuid_pk()
    notice_id: uuid.UUID = Field(foreign_key="change_notice.notice_id", index=True)
    field_name: str
    current_value: str | None = Field(default=None, sa_type=Text)
    proposed_value: str | None = Field(default=None, sa_type=Text)
    applied_old_value: str | None = Field(default=None, sa_type=Text)


class NoticeAttachment(CreatedAtMixin, table=True):
    __tablename__ = "notice_attachment"
    __table_args__ = (
        CheckConstraint(
            f"size_bytes > 0 AND size_bytes <= {MAX_ATTACHMENT_BYTES}", name="size_limit"
        ),
    )

    attachment_id: uuid.UUID = uuid_pk()
    notice_id: uuid.UUID = Field(foreign_key="change_notice.notice_id", index=True)
    # Private storage key; never a public URL.
    storage_key: str = Field(unique=True)
    original_filename: str
    mime_type: AttachmentMimeType = Field(
        sa_type=enum_column(AttachmentMimeType, "attachment_mime_type")
    )
    size_bytes: int


class ProductAnnouncement(TimestampMixin, table=True):
    """Company pop-up message ("POPs"). Live without review, labelled as not reviewed by
    FoodLens, never changes product data. Admins may hide it."""

    __tablename__ = "product_announcement"

    announcement_id: uuid.UUID = uuid_pk()
    product_id: uuid.UUID = Field(foreign_key="product.product_id", index=True)
    title: str
    message: str = Field(sa_type=Text)
    image_storage_key: str | None = None
    status: AnnouncementStatus = Field(
        default=AnnouncementStatus.LIVE,
        sa_type=enum_column(AnnouncementStatus, "announcement_status"),
    )
    created_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")
    hidden_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.user_id")
    hidden_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class AuditLog(CreatedAtMixin, table=True):
    """Append-only record of meaningful changes. No passwords, tokens, or unneeded PII."""

    __tablename__ = "audit_log"

    audit_id: uuid.UUID = uuid_pk()
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.user_id")
    entity_type: str = Field(index=True)
    entity_id: uuid.UUID = Field(index=True)
    action: str
    old_values: dict[str, Any] | None = Field(default=None, sa_type=JSONB)
    new_values: dict[str, Any] | None = Field(default=None, sa_type=JSONB)
