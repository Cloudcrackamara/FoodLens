"""Batch allocations (geo-batching, D131, D142). Advisory: they feed a timeline note and
rule 9, never a per-unit alert."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, uuid_pk


class BatchAllocation(TimestampMixin, table=True):
    __tablename__ = "batch_allocation"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    allocation_id: uuid.UUID = uuid_pk()
    batch_id: uuid.UUID = Field(foreign_key="product_batch.batch_id", index=True)
    destination_company_id: uuid.UUID | None = Field(
        default=None, foreign_key="company.company_id", index=True
    )
    destination_area_id: uuid.UUID = Field(foreign_key="area.area_id", index=True)
    quantity: int
    planned_date: date | None = None
    created_by_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")


class AllocationCarton(CreatedAtMixin, table=True):
    """A carton sits in at most one allocation."""

    __tablename__ = "allocation_carton"

    allocation_carton_id: uuid.UUID = uuid_pk()
    allocation_id: uuid.UUID = Field(foreign_key="batch_allocation.allocation_id", index=True)
    carton_id: uuid.UUID = Field(foreign_key="carton.carton_id", unique=True)


class AllocationUnit(CreatedAtMixin, table=True):
    """A unit sits in at most one allocation."""

    __tablename__ = "allocation_unit"

    allocation_unit_id: uuid.UUID = uuid_pk()
    allocation_id: uuid.UUID = Field(foreign_key="batch_allocation.allocation_id", index=True)
    unit_id: uuid.UUID = Field(foreign_key="product_unit.unit_id", unique=True)
