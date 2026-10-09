from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataMode, LookupResult
from app.schemas.announcement import LookupAnnouncement


class LookupRequest(BaseModel):
    """The registration number printed on the pack (required) and, optionally, the batch number.
    Both are plain text so a scanned value can be passed straight in. Missing input returns
    INSUFFICIENT_OR_AMBIGUOUS rather than a validation error."""

    model_config = ConfigDict(extra="ignore")

    registration_number: str | None = Field(default=None, max_length=200)
    batch_number: str | None = Field(default=None, max_length=200)


class RegisterRecordStatus(StrEnum):
    """Status of the simulated register record on the lookup date. Never an official status."""

    ACTIVE_IN_DEMO_REGISTER = "ACTIVE_IN_DEMO_REGISTER"
    EXPIRED_IN_DEMO_REGISTER = "EXPIRED_IN_DEMO_REGISTER"
    INACTIVE_IN_DEMO_REGISTER = "INACTIVE_IN_DEMO_REGISTER"


class LookupWarning(BaseModel):
    code: str
    message: str


class LookupInput(BaseModel):
    """The normalised values that were looked up, shown back so the user can correct them."""

    registration_number: str | None
    batch_number: str | None


class LookupMismatch(BaseModel):
    reason: Literal["different_registration_number", "registered_names_differ"]


class RegisterRecord(BaseModel):
    """The simulated register entry for the number entered."""

    agency: str
    scheme: str
    registration_number: str
    registered_product_name: str
    registered_company_name: str
    status: RegisterRecordStatus
    expires_on: date | None
    data_mode: DataMode
    provenance: str
    last_checked_on: date


class LookupProduct(BaseModel):
    """The FoodLens catalogue product that the entered batch belongs to (company-entered)."""

    name: str
    brand: str
    category: str
    package_size: str | None
    manufacturer_name: str
    company_display_name: str
    registration_number: str | None


class LookupBatch(BaseModel):
    batch_number: str
    production_date: date | None
    expiry_date: date | None


class LookupResponse(BaseModel):
    result: LookupResult
    data_mode: DataMode = DataMode.DEMO
    disclaimer: str
    title: str
    message: str
    warnings: list[LookupWarning] = []
    input: LookupInput
    register_record: RegisterRecord | None = None
    mismatch: LookupMismatch | None = None
    product: LookupProduct | None = None
    batch: LookupBatch | None = None
    # Company pop-up messages, each labelled as not reviewed by FoodLens.
    announcements: list[LookupAnnouncement] = []
