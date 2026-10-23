import uuid

from sqlalchemy import CheckConstraint
from sqlmodel import Field

from app.models.base import ReviewFieldsMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import (
    CompanyReviewStatus,
    MemberRole,
    MembershipStatus,
    ReviewStatus,
)


class Company(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint(
            "is_manufacturer OR is_distributor OR is_retailer", name="at_least_one_type"
        ),
    )

    company_id: uuid.UUID = uuid_pk()
    # Type flags (D105): a company may be several; at least one is set.
    is_manufacturer: bool = Field(default=False)
    is_distributor: bool = Field(default=False)
    is_retailer: bool = Field(default=False)

    # Company-managed, shown publicly once approved.
    display_name: str
    contact_email: str
    contact_phone: str | None = None

    # Claimed by the company and never treated as verified fact.
    claimed_legal_name: str
    claimed_business_identifier: str | None = None
    claimed_address: str | None = None

    # Review (admin only).
    review_status: CompanyReviewStatus = Field(
        default=CompanyReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(CompanyReviewStatus, "review_status"),
    )


class CompanyMember(TimestampMixin, table=True):
    __tablename__ = "company_member"

    member_id: uuid.UUID = uuid_pk()
    # Unique: one company per user in the MVP.
    user_id: uuid.UUID = Field(foreign_key="app_user.user_id", unique=True)
    company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    role: MemberRole = Field(sa_type=enum_column(MemberRole, "member_role"))
    membership_status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        sa_type=enum_column(MembershipStatus, "membership_status"),
    )

    # Shown on the supplier directory only when is_public_contact is true.
    is_public_contact: bool = Field(default=False)
    public_title: str | None = None
    public_phone: str | None = None
    public_email: str | None = None


class SupplierLocation(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "supplier_location"

    location_id: uuid.UUID = uuid_pk()
    company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    name: str
    address: str
    # Free text for display; area_id is the coarse area used for events (D118).
    area: str
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id", index=True)
    contact_member_id: uuid.UUID | None = Field(
        default=None, foreign_key="company_member.member_id"
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(ReviewStatus, "review_status"),
    )
