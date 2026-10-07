import uuid

from sqlmodel import Field

from app.models.base import ReviewFieldsMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import (
    CompanyReviewStatus,
    CompanyType,
    MemberRole,
    MembershipStatus,
    ReviewStatus,
)


class Company(TimestampMixin, ReviewFieldsMixin, table=True):
    __tablename__ = "company"

    company_id: uuid.UUID = uuid_pk()
    company_type: CompanyType = Field(sa_type=enum_column(CompanyType, "company_type"))

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
    area: str
    contact_member_id: uuid.UUID | None = Field(
        default=None, foreign_key="company_member.member_id"
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING_REVIEW,
        sa_type=enum_column(ReviewStatus, "review_status"),
    )
