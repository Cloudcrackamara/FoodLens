import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import CompanyReviewStatus, CompanyType, ReviewStatus

SUPPLIER_BADGE = "FoodLens demo-reviewed profile"
SUPPLIER_BADGE_NOTE = (
    "Reviewed for the FoodLens demonstration database only. This is not a NAFDAC or SON "
    "approval, and it does not verify the company's identity or products."
)


# --- Requests (client input never includes review, status, or ownership fields) -------------


class CompanyRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    company_type: CompanyType
    display_name: str = Field(min_length=1, max_length=120)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    claimed_legal_name: str = Field(min_length=1, max_length=200)
    claimed_business_identifier: str | None = Field(default=None, max_length=60)
    claimed_address: str | None = Field(default=None, max_length=300)


class LocationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=300)
    area: str = Field(min_length=1, max_length=120)
    contact_member_id: uuid.UUID | None = None


class CompanyDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUSPEND = "SUSPEND"


class LocationDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class CompanyDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    decision: CompanyDecision
    note: str | None = Field(default=None, max_length=1000)


class LocationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    decision: LocationDecision
    note: str | None = Field(default=None, max_length=1000)


# --- Responses ----------------------------------------------------------------------------


class ReviewRead(BaseModel):
    reviewed_at: datetime | None
    review_note: str | None


class LocationRead(ReviewRead):
    location_id: uuid.UUID
    name: str
    address: str
    area: str
    contact_member_id: uuid.UUID | None
    review_status: ReviewStatus
    created_at: datetime


class CompanyRead(ReviewRead):
    """Owner's and admin's view of a company, including claimed fields and review state."""

    company_id: uuid.UUID
    company_type: CompanyType
    display_name: str
    contact_email: str
    contact_phone: str | None
    claimed_legal_name: str
    claimed_business_identifier: str | None
    claimed_address: str | None
    review_status: CompanyReviewStatus
    created_at: datetime
    locations: list[LocationRead]


class AdminCompanyRead(CompanyRead):
    owner_display_name: str | None
    owner_email: str | None
    reviewed_by_display_name: str | None


class AdminLocationRead(LocationRead):
    company_id: uuid.UUID
    company_display_name: str
    company_review_status: CompanyReviewStatus


class SupplierLocationRead(BaseModel):
    name: str
    address: str
    area: str
    reviewed_at: datetime | None


class SupplierContactRead(BaseModel):
    display_name: str
    title: str | None
    phone: str | None
    email: str | None


class SupplierRead(BaseModel):
    """Public directory entry. Never includes claimed fields, review notes, or login emails."""

    company_id: uuid.UUID
    display_name: str
    company_type: CompanyType
    contact_email: str
    contact_phone: str | None
    badge: str = SUPPLIER_BADGE
    badge_note: str = SUPPLIER_BADGE_NOTE
    reviewed_at: datetime | None
    locations: list[SupplierLocationRead]
    contacts: list[SupplierContactRead]
