import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnnouncementStatus

ANNOUNCEMENT_LABEL = "Message from the company — not reviewed by FoodLens"


class AnnouncementCreateRequest(BaseModel):
    """Only title and message are read; status and authorship are set by the server."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class AnnouncementHideRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


class AnnouncementRead(BaseModel):
    announcement_id: uuid.UUID
    product_id: uuid.UUID
    product_code: str
    product_name: str
    title: str
    message: str
    status: AnnouncementStatus
    created_at: datetime
    hidden_at: datetime | None


class AdminAnnouncementRead(AnnouncementRead):
    company_id: uuid.UUID
    company_display_name: str
    created_by_display_name: str | None
    hidden_by_display_name: str | None


class LookupAnnouncement(BaseModel):
    """Shown to consumers on a lookup result, always with the not-reviewed label."""

    title: str
    message: str
    posted_at: datetime
    label: str = ANNOUNCEMENT_LABEL
