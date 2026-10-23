"""Unit codes, release, void and allocations. Requests never carry status, hashes, holders or
company fields: the company is the path company and the server derives everything else."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LifecycleStatus
from app.services.labels import DEFAULT_QR_MM
from app.services.units import MAX_UNITS_PER_REQUEST

# --- Requests ---------------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quantity: int = Field(ge=1, le=MAX_UNITS_PER_REQUEST)
    units_per_carton: int | None = Field(default=None, ge=1, le=MAX_UNITS_PER_REQUEST)
    # Below 15 mm is allowed with a warning (D139); below 10 mm is refused.
    qr_size_mm: float = Field(default=DEFAULT_QR_MM, ge=10, le=60)


class ReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    carton_ref: str | None = Field(default=None, max_length=20)


class VoidRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)
    whole_batch: bool = False
    carton_refs: list[str] = Field(default_factory=list, max_length=500)
    codes: list[str] = Field(default_factory=list, max_length=MAX_UNITS_PER_REQUEST)


class AllocationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    destination_area_id: uuid.UUID
    destination_company_id: uuid.UUID | None = None
    quantity: int | None = Field(default=None, ge=1)
    planned_date: date | None = None
    carton_refs: list[str] = Field(default_factory=list, max_length=500)
    unit_codes: list[str] = Field(default_factory=list, max_length=MAX_UNITS_PER_REQUEST)


# --- Responses --------------------------------------------------------------------------------


class UnitsChanged(BaseModel):
    units: int


class CartonSummaryRead(BaseModel):
    carton_ref: str
    status: LifecycleStatus
    units: dict[str, int]


class BatchSummaryRead(BaseModel):
    """Counts only: never a token, hash or unit ID."""

    product_name: str
    batch_number: str
    expiry_date: date | None
    released_at: datetime | None
    units: dict[str, int]
    loose_units: dict[str, int]
    cartons: list[CartonSummaryRead]


class AreaRead(BaseModel):
    area_id: uuid.UUID
    city: str
    state: str


class DestinationRead(BaseModel):
    company_id: uuid.UUID
    display_name: str
    is_distributor: bool
    is_retailer: bool


class AllocationRead(BaseModel):
    allocation_id: uuid.UUID
    destination_area: AreaRead
    destination_company: DestinationRead | None
    quantity: int
    planned_date: date | None
    carton_refs: list[str]
    units_listed: int
    created_at: datetime
