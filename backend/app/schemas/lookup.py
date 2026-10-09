from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataMode, LookupResult
from app.schemas.announcement import LookupAnnouncement


class LookupRequest(BaseModel):
    """Both fields optional here so that missing input returns a helpful
    INSUFFICIENT_OR_AMBIGUOUS result instead of a validation error."""

    model_config = ConfigDict(extra="ignore")

    product_code: str | None = Field(default=None, max_length=200)
    batch_number: str | None = Field(default=None, max_length=200)


class CredentialDisplayStatus(StrEnum):
    """Status of the stored demo record, computed on the lookup date. Never an official status."""

    ACTIVE_IN_DEMO_DATA = "ACTIVE_IN_DEMO_DATA"
    EXPIRED_IN_DEMO_DATA = "EXPIRED_IN_DEMO_DATA"
    INACTIVE_IN_DEMO_DATA = "INACTIVE_IN_DEMO_DATA"
    NOT_YET_VALID_IN_DEMO_DATA = "NOT_YET_VALID_IN_DEMO_DATA"


class LookupWarning(BaseModel):
    code: str
    message: str


class LookupInput(BaseModel):
    """The normalised values that were looked up, shown back so the user can correct them."""

    product_code: str | None
    batch_number: str | None


class LookupMismatch(BaseModel):
    field: Literal["product_code", "credential"]


class LookupProduct(BaseModel):
    product_code: str
    name: str
    brand: str
    category: str
    package_size: str | None
    manufacturer_name: str
    company_display_name: str


class LookupBatch(BaseModel):
    batch_number: str
    production_date: date | None
    expiry_date: date | None


class LookupCredential(BaseModel):
    agency: str
    scheme: str
    reference_number: str
    scope: Literal["PRODUCT"] = "PRODUCT"
    status: CredentialDisplayStatus
    valid_from: date | None
    valid_until: date | None
    data_mode: DataMode
    provenance: str
    checked_on: date


class LookupCandidate(BaseModel):
    """A product the user can pick when the batch number alone is not enough."""

    product_code: str
    name: str
    brand: str


class LookupResponse(BaseModel):
    result: LookupResult
    data_mode: DataMode = DataMode.DEMO
    disclaimer: str
    title: str
    message: str
    warnings: list[LookupWarning] = []
    input: LookupInput
    mismatch: LookupMismatch | None = None
    product: LookupProduct | None = None
    batch: LookupBatch | None = None
    credentials: list[LookupCredential] = []
    credential_scope_note: str
    candidates: list[LookupCandidate] = []
    # Company pop-up messages, each labelled as not reviewed by FoodLens.
    announcements: list[LookupAnnouncement] = []
