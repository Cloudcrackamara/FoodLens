"""Merchant page requests and responses. A request carries only a code, an event type and, for a
transfer, the receiving company or, for a correction, a reason. It never carries status, holder,
area or ownership fields: the server decides them (CLAUDE.md, client input rules)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LifecycleEventType, LifecycleStatus, MemberRole, MembershipStatus


class LookupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=100)


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=100)
    event_type: LifecycleEventType
    to_company_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class StatusCount(BaseModel):
    status: LifecycleStatus
    packs: int


class LookupResponse(BaseModel):
    """What a code points at, for the merchant's own company. No unit or carton IDs."""

    subject: str
    code_last4: str
    product_name: str
    brand: str
    size: str | None
    batch_number: str
    expiry_date: date | None
    packs: int
    status_counts: list[StatusCount]
    recalled: bool
    you_hold: int
    sold_by_you: int
    allowed_events: list[LifecycleEventType]
    # Why nothing can be recorded, when allowed_events is empty.
    blocked_reason: str | None


class EventResponse(BaseModel):
    event_type: LifecycleEventType
    subject: str
    packs: int
    status_after: LifecycleStatus
    notes: list[str]


class DestinationRead(BaseModel):
    company_id: uuid.UUID
    display_name: str


class MemberRead(BaseModel):
    member_id: uuid.UUID
    email: str
    display_name: str
    role: MemberRole
    membership_status: MembershipStatus


class AddStaffRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254)
