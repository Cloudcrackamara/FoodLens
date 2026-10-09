import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AttachmentMimeType, ChangeNoticeStatus, ChangeType

# --- Proposed changes: the only fields a notice may change ----------------------------------
# Product codes and batch numbers are printed on packages and identify the record, so they
# cannot be changed by a notice (D68).


class _Changes(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Fields that may be set to null; all others must keep a value.
    nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Propose at least one change")
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable:
                raise ValueError(f"{name} cannot be empty")
        return self


class ProductChanges(_Changes):
    nullable: ClassVar[frozenset[str]] = frozenset({"package_size", "label_information"})

    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    package_size: str | None = Field(default=None, max_length=40)
    manufacturer_name: str | None = Field(default=None, min_length=1, max_length=200)
    label_information: str | None = Field(default=None, max_length=2000)


class BatchChanges(_Changes):
    nullable: ClassVar[frozenset[str]] = frozenset({"production_date", "expiry_date"})

    production_date: date | None = None
    expiry_date: date | None = None


# --- Requests -----------------------------------------------------------------------------


class ChangeNoticeCreateRequest(BaseModel):
    """Targets exactly one of the company's products or batches. Review fields are never read."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    product_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    change_type: ChangeType
    reason: str = Field(min_length=1, max_length=2000)
    effective_date: date | None = None
    proposed_changes: dict[str, Any]

    @model_validator(mode="after")
    def one_target(self):
        if (self.product_id is None) == (self.batch_id is None):
            raise ValueError("Give either product_id or batch_id")
        return self


class ClarificationResponseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)


class NoticeDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"


class NoticeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    decision: NoticeDecision
    note: str | None = Field(default=None, max_length=1000)


# --- Responses ----------------------------------------------------------------------------


class NoticeFieldRead(BaseModel):
    field_name: str
    current_value: str | None
    proposed_value: str | None
    applied_old_value: str | None


class AttachmentRead(BaseModel):
    attachment_id: uuid.UUID
    original_filename: str
    mime_type: AttachmentMimeType
    size_bytes: int
    created_at: datetime


class ChangeNoticeRead(BaseModel):
    notice_id: uuid.UUID
    company_id: uuid.UUID
    target_type: Literal["product", "batch"]
    product_id: uuid.UUID
    product_code: str
    product_name: str
    batch_id: uuid.UUID | None
    batch_number: str | None
    change_type: ChangeType
    reason: str
    effective_date: date | None
    review_status: ChangeNoticeStatus
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    fields: list[NoticeFieldRead]
    attachments: list[AttachmentRead]


class AdminChangeNoticeRead(ChangeNoticeRead):
    company_display_name: str
    submitted_by_display_name: str | None
    reviewed_by_display_name: str | None
