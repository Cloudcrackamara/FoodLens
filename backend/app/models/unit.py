"""Unit identity and lifecycle (docs/SCHEMA.md, D112, D113, D138-D140).

QR identities are stored only as sha256(normalised token) hex; raw tokens never reach the
database. lifecycle_status, current_holder_company_id and last_sold_* are derived columns,
written only by services/lifecycle.py. lifecycle_event is append-only: a database trigger
(migration 0006) refuses UPDATE and DELETE.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, enum_column, utc_now, uuid_pk
from app.models.enums import EventSource, LifecycleEventType, LifecycleStatus

HASH_FORMAT = "qr_token_hash ~ '^[0-9a-f]{64}$'"


class Carton(TimestampMixin, table=True):
    """One packaging level: a carton holds units."""

    __tablename__ = "carton"
    __table_args__ = (
        UniqueConstraint("batch_id", "carton_ref"),
        CheckConstraint(HASH_FORMAT, name="qr_token_hash_is_sha256"),
    )

    carton_id: uuid.UUID = uuid_pk()
    batch_id: uuid.UUID = Field(foreign_key="product_batch.batch_id", index=True)
    manufacturer_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    # Printed reference such as C001, for labels and the printer CSV only (D139).
    carton_ref: str = Field(max_length=20)
    qr_token_hash: str = Field(sa_type=String(64), unique=True)
    lifecycle_status: LifecycleStatus = Field(
        default=LifecycleStatus.ISSUED, sa_type=enum_column(LifecycleStatus, "lifecycle_status")
    )
    current_holder_company_id: uuid.UUID | None = Field(
        default=None, foreign_key="company.company_id"
    )


class ProductUnit(TimestampMixin, table=True):
    __tablename__ = "product_unit"
    __table_args__ = (CheckConstraint(HASH_FORMAT, name="qr_token_hash_is_sha256"),)

    unit_id: uuid.UUID = uuid_pk()
    # Denormalised for fast checks; the service keeps them consistent.
    batch_id: uuid.UUID = Field(foreign_key="product_batch.batch_id", index=True)
    product_id: uuid.UUID = Field(foreign_key="product.product_id", index=True)
    manufacturer_id: uuid.UUID = Field(foreign_key="company.company_id", index=True)
    parent_carton_id: uuid.UUID | None = Field(
        default=None, foreign_key="carton.carton_id", index=True
    )
    qr_token_hash: str = Field(sa_type=String(64), unique=True)

    # Derived (services/lifecycle.py only).
    lifecycle_status: LifecycleStatus = Field(
        default=LifecycleStatus.ISSUED, sa_type=enum_column(LifecycleStatus, "lifecycle_status")
    )
    current_holder_company_id: uuid.UUID | None = Field(
        default=None, foreign_key="company.company_id"
    )
    last_sold_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_sold_area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id")
    last_sold_company_id: uuid.UUID | None = Field(default=None, foreign_key="company.company_id")


class LifecycleEvent(CreatedAtMixin, table=True):
    """Append-only. A carton event writes one carton row plus one row per unit, sharing a
    group_id. Nothing about payment beyond the opaque payment_reference (D122)."""

    __tablename__ = "lifecycle_event"
    __table_args__ = (
        CheckConstraint("num_nonnulls(unit_id, carton_id) = 1", name="exactly_one_subject"),
        CheckConstraint(
            "event_type NOT IN ('SALE_CORRECTED', 'VOIDED') "
            "OR (reason IS NOT NULL AND btrim(reason) <> '')",
            name="reason_required",
        ),
        CheckConstraint(
            "event_type <> 'TRANSFERRED' OR to_company_id IS NOT NULL", name="transfer_has_target"
        ),
        # POS events are per unit and carry a transaction, so the idempotency key is complete.
        CheckConstraint(
            "pos_partner_id IS NULL OR (unit_id IS NOT NULL AND transaction_ref IS NOT NULL)",
            name="pos_event_keyed",
        ),
        Index(
            "uq_lifecycle_event_pos_idempotency",
            "pos_partner_id",
            "transaction_ref",
            "unit_id",
            "event_type",
            unique=True,
            postgresql_where=text("pos_partner_id IS NOT NULL"),
        ),
    )

    event_id: uuid.UUID = uuid_pk()
    unit_id: uuid.UUID | None = Field(default=None, foreign_key="product_unit.unit_id", index=True)
    carton_id: uuid.UUID | None = Field(default=None, foreign_key="carton.carton_id", index=True)
    group_id: uuid.UUID | None = Field(default=None, index=True)
    event_type: LifecycleEventType = Field(
        sa_type=enum_column(LifecycleEventType, "lifecycle_event_type")
    )
    source: EventSource = Field(sa_type=enum_column(EventSource, "event_source"))

    # Null for CONSUMER_CHECK and POS events (the POS actor is the partner plus the retailer).
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.user_id")
    actor_company_id: uuid.UUID | None = Field(default=None, foreign_key="company.company_id")
    retailer_company_id: uuid.UUID | None = Field(default=None, foreign_key="company.company_id")
    to_company_id: uuid.UUID | None = Field(default=None, foreign_key="company.company_id")
    pos_partner_id: uuid.UUID | None = Field(default=None, foreign_key="pos_partner.partner_id")
    till_ref: str | None = Field(default=None, max_length=64)
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id")

    # occurred_at may be earlier than recorded_at (late offline POS events).
    occurred_at: datetime = Field(sa_type=DateTime(timezone=True))
    recorded_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
    )
    transaction_ref: str | None = Field(default=None, sa_type=String(100))
    payment_reference: str | None = Field(default=None, sa_type=String(100))
    reason: str | None = Field(default=None, sa_type=Text)

    corrects_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="lifecycle_event.event_id"
    )
    returns_event_id: uuid.UUID | None = Field(default=None, foreign_key="lifecycle_event.event_id")
    received_without_transfer: bool = Field(default=False)
    outside_allocation: bool = Field(default=False)
