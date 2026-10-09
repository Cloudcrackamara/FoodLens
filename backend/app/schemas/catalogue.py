import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProductStatus

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
    # The NAFDAC/SON number printed on the pack. FoodLens never treats it as proof; lookups
    # check it against the simulated register (D81).
    registration_number: str | None = Field(default=None, max_length=200)


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


# --- Responses ---------------------------------------------------------------------------


class BatchRead(BaseModel):
    batch_id: uuid.UUID
    batch_number: str
    production_date: date | None
    expiry_date: date | None
    created_at: datetime


class ProductRead(BaseModel):
    product_id: uuid.UUID
    product_code: str
    name: str
    brand: str
    category: str
    package_size: str | None
    manufacturer_name: str
    label_information: str | None
    registration_number: str | None
    status: ProductStatus
    created_at: datetime
    batches: list[BatchRead]
