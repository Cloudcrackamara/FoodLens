"""POS API (/api/pos/v1) and admin POS requests and responses (D121, D122).

POS bodies forbid unknown fields, so a partner cannot send amounts, card or customer data even by
mistake. payment_reference is an opaque string of at most 100 characters. No request carries a
status, holder, area or ownership field: the server decides them.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import LifecycleEventType, LifecycleStatus, PosLinkStatus, PosPartnerStatus

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    retailer_id: uuid.UUID
    till_id: str = Field(min_length=1, max_length=64)


class PosLookupRequest(PosRequest):
    code: Code


class PosEventRequest(PosRequest):
    transaction_id: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    units: list[Code] = Field(min_length=1)


class PosSaleRequest(PosEventRequest):
    payment_reference: str = Field(min_length=1, max_length=100)


class PosRefundRequest(PosEventRequest):
    pass


class PosVoidRequest(PosEventRequest):
    # Checked by the service so a blank reason gets NEED_REASON, not a schema error.
    reason: str | None = Field(default=None, max_length=500)


class PosMessage(BaseModel):
    code: str
    message: str


class PosLookupResponse(BaseModel):
    """Only the D121 lookup fields. No unit, carton or batch IDs."""

    subject: Literal["UNIT", "CARTON"]
    code_last4: str
    product_name: str
    brand: str
    size: str | None
    gtin: str | None
    batch_number: str
    expiry_date: date | None
    status: LifecycleStatus
    warning: PosMessage | None


class PosUnitResult(BaseModel):
    index: int
    code_last4: str
    result: Literal["RECORDED", "ERROR"]
    error: PosMessage | None = None


class PosEventResponse(BaseModel):
    transaction_id: str
    event_type: LifecycleEventType
    recorded: int
    errors: int
    units: list[PosUnitResult]


# --- Admin -----------------------------------------------------------------------------------


class PartnerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)


class PartnerStatusRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: PosPartnerStatus


class LinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    retailer_id: uuid.UUID


class TillCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    retailer_id: uuid.UUID
    till_ref: str = Field(min_length=1, max_length=64)
    location_id: uuid.UUID


class KeyRead(BaseModel):
    key_id: uuid.UUID
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class LinkRead(BaseModel):
    link_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    status: PosLinkStatus


class TillRead(BaseModel):
    till_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    till_ref: str
    location_name: str
    area: str


class PartnerRead(BaseModel):
    partner_id: uuid.UUID
    name: str
    status: PosPartnerStatus
    created_at: datetime
    keys: list[KeyRead]
    links: list[LinkRead]
    tills: list[TillRead]


class OneTimeCredentials(BaseModel):
    """Shown once. FoodLens keeps only the key's hash and the secret's ciphertext."""

    api_key: str
    signing_secret: str | None = None


class PartnerCreated(BaseModel):
    partner: PartnerRead
    credentials: OneTimeCredentials


class KeyCreated(BaseModel):
    key: KeyRead
    credentials: OneTimeCredentials


class RetailerLocationRead(BaseModel):
    location_id: uuid.UUID
    name: str
    area: str


class RetailerOptionRead(BaseModel):
    retailer_id: uuid.UUID
    display_name: str
    locations: list[RetailerLocationRead]


# --- Simulated till (D123) -------------------------------------------------------------------


class DemoTillRead(BaseModel):
    till_ref: str
    retailer_name: str
    location_name: str
    area: str


class DemoLookupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    till_ref: str = Field(min_length=1, max_length=64)
    code: Code


class DemoVoidRequest(DemoLookupRequest):
    reason: str | None = Field(default=None, max_length=500)
