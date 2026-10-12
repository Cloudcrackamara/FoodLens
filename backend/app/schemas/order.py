"""Order request schemas (D95-D100). Requests never carry status, company, user, reviewer, or
payment fields: the buyer is the path company, the seller is derived from the products."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CompanyType, DataMode, FulfilmentMethod, OrderStatus
from app.schemas.company import SupplierContactRead, SupplierRead

MAX_LINES = 20

# --- Requests ---------------------------------------------------------------------------------


class OrderLineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(min_length=1, max_length=30)


class OrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    lines: list[OrderLineRequest] = Field(min_length=1, max_length=MAX_LINES)
    fulfilment_method: FulfilmentMethod
    pickup_location_id: uuid.UUID | None = None
    delivery_details: str | None = Field(default=None, max_length=500)
    buyer_note: str | None = Field(default=None, max_length=500)


class DeclineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


class ReplyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=500)


class LineAllocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line_id: uuid.UUID
    batch_ids: list[uuid.UUID] = Field(max_length=10)


class FulfilRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allocations: list[LineAllocation] = Field(default_factory=list, max_length=MAX_LINES)


class OrderRole(StrEnum):
    BUYING = "buying"
    SELLING = "selling"


# --- Responses --------------------------------------------------------------------------------


class AllocatedBatchRead(BaseModel):
    batch_id: uuid.UUID
    batch_number: str
    expiry_date: date | None


class OrderLineRead(BaseModel):
    line_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_code: str
    quantity: Decimal
    unit: str
    batches: list[AllocatedBatchRead]


class OrderPartyRead(BaseModel):
    company_id: uuid.UUID
    display_name: str


class OrderPickupRead(BaseModel):
    location_id: uuid.UUID
    name: str
    address: str
    area: str


class OrderRead(BaseModel):
    order_id: uuid.UUID
    status: OrderStatus
    buyer: OrderPartyRead
    seller: OrderPartyRead
    fulfilment_method: FulfilmentMethod
    pickup_location: OrderPickupRead | None
    delivery_details: str | None
    buyer_note: str | None
    seller_note: str | None
    lines: list[OrderLineRead]
    created_at: datetime
    updated_at: datetime


# --- Supplier page ---------------------------------------------------------------------------


class RegistrationResult(StrEnum):
    """Registration status from the simulated register for a supplier's product (D100).
    Checked like a lookup: not found, expired/inactive, different product or company, active."""

    ACTIVE_IN_DEMO_REGISTER = "ACTIVE_IN_DEMO_REGISTER"
    EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER = "EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER"
    REGISTERED_TO_ANOTHER_PRODUCT = "REGISTERED_TO_ANOTHER_PRODUCT"
    NOT_FOUND_IN_DEMO_REGISTER = "NOT_FOUND_IN_DEMO_REGISTER"
    NO_NUMBER_GIVEN = "NO_NUMBER_GIVEN"


class SupplierProductRead(BaseModel):
    product_id: uuid.UUID
    name: str
    brand: str
    category: str
    package_size: str | None
    registration_number: str | None
    registration_result: RegistrationResult
    registration_label: str
    register_name: str | None


class SupplierDetailRead(SupplierRead):
    company_type: CompanyType
    products: list[SupplierProductRead]
    contacts: list[SupplierContactRead]
    data_mode: DataMode = DataMode.DEMO
    disclaimer: str
