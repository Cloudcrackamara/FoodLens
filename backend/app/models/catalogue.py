import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import ReviewFieldsMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import (
    CredentialStatus,
    DataMode,
    ProductStatus,
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


class CredentialRecord(TimestampMixin, ReviewFieldsMixin, table=True):
    """Product-level credential. Never a batch test or batch certificate."""

    __tablename__ = "credential_record"
    __table_args__ = (
        UniqueConstraint("agency_id", "reference_number"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="valid_until_after_from",
        ),
    )

    credential_id: uuid.UUID = uuid_pk()
    product_id: uuid.UUID = Field(foreign_key="product.product_id", index=True)
    agency_id: uuid.UUID = Field(foreign_key="regulatory_agency.agency_id", index=True)
    reference_number: str
    status: CredentialStatus = Field(sa_type=enum_column(CredentialStatus, "credential_status"))
    valid_from: date | None = None
    valid_until: date | None = None
    data_mode: DataMode = Field(default=DataMode.DEMO, sa_type=enum_column(DataMode, "data_mode"))
    provenance: str = Field(sa_type=Text)
    checked_on: date
    # Null for seeded records.
    submitted_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.user_id")
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(ReviewStatus, "review_status"),
    )
