"""POS partners (D121-D123). API keys are stored as SHA-256 hashes; the signing secret is
Fernet-encrypted under POS_SECRET_KEY because verifying an HMAC needs the raw secret."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import PosLinkStatus, PosPartnerStatus


class PosPartner(TimestampMixin, table=True):
    __tablename__ = "pos_partner"

    partner_id: uuid.UUID = uuid_pk()
    name: str
    status: PosPartnerStatus = Field(
        default=PosPartnerStatus.ACTIVE,
        sa_type=enum_column(PosPartnerStatus, "pos_partner_status"),
    )
    signing_secret_encrypted: str = Field(sa_type=Text)
    # Always an admin (service).
    created_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")


class PosPartnerKey(CreatedAtMixin, table=True):
    """The raw key is shown once and never stored."""

    __tablename__ = "pos_partner_key"
    __table_args__ = (CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name="key_hash_is_sha256"),)

    key_id: uuid.UUID = uuid_pk()
    partner_id: uuid.UUID = Field(foreign_key="pos_partner.partner_id", index=True)
    key_prefix: str = Field(max_length=8)
    key_hash: str = Field(sa_type=String(64), unique=True)
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class PosPartnerRetailer(TimestampMixin, table=True):
    __tablename__ = "pos_partner_retailer"
    __table_args__ = (UniqueConstraint("partner_id", "retailer_company_id"),)

    link_id: uuid.UUID = uuid_pk()
    partner_id: uuid.UUID = Field(foreign_key="pos_partner.partner_id", index=True)
    # An approved company with is_retailer set (service).
    retailer_company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    status: PosLinkStatus = Field(
        default=PosLinkStatus.ACTIVE, sa_type=enum_column(PosLinkStatus, "pos_link_status")
    )
    created_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")


class PosTill(CreatedAtMixin, table=True):
    __tablename__ = "pos_till"
    __table_args__ = (UniqueConstraint("partner_id", "retailer_company_id", "till_ref"),)

    till_id: uuid.UUID = uuid_pk()
    partner_id: uuid.UUID = Field(foreign_key="pos_partner.partner_id", index=True)
    retailer_company_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    till_ref: str = Field(max_length=64)
    # A reviewed location of that retailer (service); it supplies the event area.
    location_id: uuid.UUID = Field(foreign_key="supplier_location.location_id")
