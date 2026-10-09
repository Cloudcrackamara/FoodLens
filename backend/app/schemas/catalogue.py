import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CredentialStatus, DataMode, ProductStatus, ReviewStatus

# --- Requests (no status, review, or ownership fields) ---------------------------------------


class ProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    product_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    package_size: str | None = Field(default=None, max_length=40)
    manufacturer_name: str = Field(min_length=1, max_length=200)
    label_information: str | None = Field(default=None, max_length=2000)


class BatchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    batch_number: str = Field(min_length=1, max_length=64)
    production_date: date | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def expiry_after_production(self):
        if self.production_date and self.expiry_date and self.expiry_date < self.production_date:
            raise ValueError("Expiry date cannot be before the production date")
        return self


class CredentialCreateRequest(BaseModel):
    """A company's claim. Status, review state, data mode, and provenance are set by the server."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    agency_id: uuid.UUID
    reference_number: str = Field(min_length=1, max_length=64)
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def until_after_from(self):
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("Valid-until date cannot be before the valid-from date")
        return self


class CredentialDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class CredentialDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    decision: CredentialDecision
    note: str | None = Field(default=None, max_length=1000)


# --- Responses ---------------------------------------------------------------------------


class AgencyRead(BaseModel):
    agency_id: uuid.UUID
    name: str
    scheme: str


class BatchRead(BaseModel):
    batch_id: uuid.UUID
    batch_number: str
    production_date: date | None
    expiry_date: date | None
    created_at: datetime


class CredentialRead(BaseModel):
    credential_id: uuid.UUID
    agency: str
    scheme: str
    reference_number: str
    status: CredentialStatus
    valid_from: date | None
    valid_until: date | None
    data_mode: DataMode
    review_status: ReviewStatus
    reviewed_at: datetime | None
    review_note: str | None


class ProductRead(BaseModel):
    product_id: uuid.UUID
    product_code: str
    name: str
    brand: str
    category: str
    package_size: str | None
    manufacturer_name: str
    label_information: str | None
    status: ProductStatus
    created_at: datetime
    batches: list[BatchRead]
    credentials: list[CredentialRead]


class AdminCredentialRead(CredentialRead):
    company_id: uuid.UUID
    company_display_name: str
    product_code: str
    product_name: str
    submitted_by_display_name: str | None
    created_at: datetime
