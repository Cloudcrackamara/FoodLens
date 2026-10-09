import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import ReviewFieldsMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import (
    DataMode,
    ProductStatus,
    RegisterStatus,
    ReviewStatus,
)


class Product(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "product"

    product_id: uuid.UUID = uuid_pk()
    company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    name: str
    brand: str
    category: str
    product_code: str = Field(unique=True)
    package_size: str | None = None
    manufacturer_name: str
    label_information: str | None = Field(default=None, sa_type=Text)
    # Registration number printed on the pack, entered by the company. Not unique: a copied
    # number on another product is exactly what the lookup must detect (D81).
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
    # Opaque token for an optional QR link. Not secret, not proof of authenticity.
    qr_token: str | None = Field(default=None, unique=True)
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(ReviewStatus, "review_status"),
    )


class RegulatoryAgency(TimestampMixin, table=True):
    """Simulated issuer/scheme, e.g. 'NAFDAC (simulated)'. Never a real regulator connection."""

    __tablename__ = "regulatory_agency"
    __table_args__ = (UniqueConstraint("name", "scheme"),)

    agency_id: uuid.UUID = uuid_pk()
    name: str
    scheme: str
    data_mode: DataMode = Field(default=DataMode.DEMO, sa_type=enum_column(DataMode, "data_mode"))


class RegulatorRegister(TimestampMixin, table=True):
    """Simulated NAFDAC/SON register: the only source of registration status (D80).

    Seeded fictional data with DEMO- numbers. No API writes to it; companies and admins cannot
    create or edit records. It is not the regulators' own system.
    """

    __tablename__ = "regulator_register"

    register_id: uuid.UUID = uuid_pk()
    agency_id: uuid.UUID = Field(foreign_key="regulatory_agency.agency_id", index=True)
    # Stored normalised (upper-case, no spaces); unique across the register.
    registration_number: str = Field(unique=True)
    registered_product_name: str
    registered_company_name: str
    status: RegisterStatus = Field(sa_type=enum_column(RegisterStatus, "register_status"))
    expires_on: date | None = None
    data_mode: DataMode = Field(default=DataMode.DEMO, sa_type=enum_column(DataMode, "data_mode"))
    provenance: str = Field(sa_type=Text)
    last_checked_on: date
