import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import ReviewFieldsMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import ProductStatus, ReviewStatus


class Product(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "product"
    __table_args__ = (
        # GTIN is optional; when set it is unique per company (D107).
        Index(
            "uq_product_company_id_gtin",
            "company_id",
            "gtin",
            unique=True,
            postgresql_where=text("gtin IS NOT NULL"),
        ),
    )

    product_id: uuid.UUID = uuid_pk()
    company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    name: str
    brand: str
    category: str
    product_code: str = Field(unique=True)
    size: str | None = None
    # At most 20 keys with string values (service, D107).
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    # 8/12/13/14 digits with a valid GS1 check digit (service, D107).
    gtin: str | None = None
    manufacturer_name: str
    label_information: str | None = Field(default=None, sa_type=Text)
    # NAFDAC number as printed on the pack. Information only: not unique, never checked (D107).
    registration_number: str | None = Field(default=None, index=True)
    status: ProductStatus = Field(
        default=ProductStatus.DRAFT, sa_type=enum_column(ProductStatus, "product_status")
    )


class ProductBatch(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "product_batch"
    __table_args__ = (
        UniqueConstraint("product_id", "batch_number"),
        CheckConstraint(
            "expiry_date IS NULL OR production_date IS NULL OR expiry_date >= production_date",
            name="expiry_after_production",
        ),
    )

    batch_id: uuid.UUID = uuid_pk()
    product_id: uuid.UUID = Field(foreign_key="product.product_id", index=True)
    batch_number: str
    production_date: date | None = None
    expiry_date: date | None = None
    # Set when every unit has been released. Cache only (service).
    released_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(ReviewStatus, "review_status"),
    )
