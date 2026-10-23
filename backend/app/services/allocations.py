"""Batch allocations, geo-batching (D131, D142). Advisory: they feed a timeline note and rule 9
later, never a per-unit alert.

Rules:
- Owners and staff of the batch's approved manufacturer allocate after codes are generated.
- Destination: an optional approved distributor or retailer, and a required area.
- By cartons (carton refs), by single units (their codes, from the label CSV), or by quantity.
  When cartons or units are listed, the quantity is the number of live units they cover.
- A carton sits in at most one allocation; so does a unit. A unit whose carton is listed in any
  allocation cannot be listed on its own.
- The total allocated never exceeds the batch's live (not voided) units.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    AllocationCarton,
    AllocationUnit,
    Area,
    BatchAllocation,
    Carton,
    Company,
    CompanyMember,
    ProductUnit,
)
from app.models.enums import CompanyReviewStatus, LifecycleStatus
from app.services import audit, identity
from app.services.companies import NotFoundError
from app.services.units import UnitConflictError, UnitRuleError, own_batch


@dataclass(frozen=True)
class AllocationInput:
    destination_area_id: uuid.UUID
    destination_company_id: uuid.UUID | None = None
    quantity: int | None = None
    planned_date: date | None = None
    carton_refs: list[str] = field(default_factory=list)
    unit_codes: list[str] = field(default_factory=list)


def _live_units(db: Session, *conditions) -> int:
    return db.exec(
        select(func.count()).where(
            ProductUnit.lifecycle_status != LifecycleStatus.VOIDED, *conditions
        )
    ).one()


def destinations(db: Session) -> list[Company]:
    """Companies stock can be allocated to: approved distributors and retailers."""
    return list(
        db.exec(
            select(Company)
            .where(
                Company.review_status == CompanyReviewStatus.APPROVED,
                Company.is_distributor | Company.is_retailer,
            )
            .order_by(Company.display_name)
        ).all()
    )


def create(
    db: Session, member: CompanyMember, batch_id: uuid.UUID, data: AllocationInput
) -> BatchAllocation:
    own_batch(db, member, batch_id)
    if db.get(Area, data.destination_area_id) is None:
        raise UnitRuleError("Choose an area from the list")
    if data.destination_company_id is not None:
        company = db.get(Company, data.destination_company_id)
        if (
            company is None
            or company.review_status != CompanyReviewStatus.APPROVED
            or not (company.is_distributor or company.is_retailer)
        ):
            raise UnitRuleError("The destination must be an approved distributor or retailer")

    cartons: list[Carton] = []
    for ref in dict.fromkeys(r.strip().upper() for r in data.carton_refs):
        carton = db.exec(
            select(Carton).where(Carton.batch_id == batch_id, Carton.carton_ref == ref)
        ).first()
        if carton is None or carton.lifecycle_status == LifecycleStatus.VOIDED:
            raise UnitRuleError(f"Carton {ref} is not a live carton of this batch")
        if db.exec(
            select(AllocationCarton).where(AllocationCarton.carton_id == carton.carton_id)
        ).first():
            raise UnitConflictError(f"Carton {ref} is already in another allocation")
        cartons.append(carton)
    carton_ids = {c.carton_id for c in cartons}

    units: dict[uuid.UUID, ProductUnit] = {}
    for code in data.unit_codes:
        unit = db.exec(
            select(ProductUnit).where(
                ProductUnit.qr_token_hash == identity.token_hash(code),
                ProductUnit.batch_id == batch_id,
            )
        ).first()
        ending = identity.normalise(code)[-4:]
        if unit is None or unit.lifecycle_status == LifecycleStatus.VOIDED:
            raise UnitRuleError(f"Code ending {ending} is not a live pack of this batch")
        if unit.parent_carton_id in carton_ids or (
            unit.parent_carton_id
            and db.exec(
                select(AllocationCarton).where(AllocationCarton.carton_id == unit.parent_carton_id)
            ).first()
        ):
            raise UnitConflictError(f"The carton of code ending {ending} is already allocated")
        if db.exec(select(AllocationUnit).where(AllocationUnit.unit_id == unit.unit_id)).first():
            raise UnitConflictError(f"Code ending {ending} is already in another allocation")
        units[unit.unit_id] = unit

    if cartons or units:
        listed = len(units)
        if carton_ids:
            listed += _live_units(db, ProductUnit.parent_carton_id.in_(carton_ids))
        if data.quantity is not None and data.quantity != listed:
            raise UnitRuleError(
                f"The listed cartons and packs hold {listed} packs; the quantity must match"
            )
        quantity = listed
    else:
        if not data.quantity or data.quantity < 1:
            raise UnitRuleError("Enter how many packs, or list cartons or codes")
        quantity = data.quantity
    if quantity < 1:
        raise UnitRuleError("The listed cartons hold no live packs")

    allocated = db.exec(
        select(func.coalesce(func.sum(BatchAllocation.quantity), 0)).where(
            BatchAllocation.batch_id == batch_id
        )
    ).one()
    available = _live_units(db, ProductUnit.batch_id == batch_id)
    if allocated + quantity > available:
        raise UnitRuleError(
            f"Only {available - allocated} of this batch's {available} packs are left to allocate"
        )

    allocation = BatchAllocation(
        batch_id=batch_id,
        destination_company_id=data.destination_company_id,
        destination_area_id=data.destination_area_id,
        quantity=quantity,
        planned_date=data.planned_date,
        created_by_user_id=member.user_id,
    )
    db.add(allocation)
    db.flush()
    db.add_all(
        AllocationCarton(allocation_id=allocation.allocation_id, carton_id=c.carton_id)
        for c in cartons
    )
    db.add_all(AllocationUnit(allocation_id=allocation.allocation_id, unit_id=u) for u in units)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="batch_allocation",
        entity_id=allocation.allocation_id,
        action="created",
        new_values={
            "batch_id": str(batch_id),
            "quantity": quantity,
            "carton_refs": [c.carton_ref for c in cartons],
            "units_listed": len(units),
        },
    )
    db.commit()
    db.refresh(allocation)
    return allocation


@dataclass(frozen=True)
class AllocationView:
    allocation: BatchAllocation
    area: Area
    company: Company | None
    carton_refs: list[str]
    units_listed: int


def list_for_batch(db: Session, member: CompanyMember, batch_id: uuid.UUID) -> list[AllocationView]:
    own_batch(db, member, batch_id)
    views = []
    for allocation in db.exec(
        select(BatchAllocation)
        .where(BatchAllocation.batch_id == batch_id)
        .order_by(BatchAllocation.created_at)
    ):
        refs = db.exec(
            select(Carton.carton_ref)
            .join(AllocationCarton, AllocationCarton.carton_id == Carton.carton_id)
            .where(AllocationCarton.allocation_id == allocation.allocation_id)
            .order_by(Carton.carton_ref)
        ).all()
        units_listed = db.exec(
            select(func.count()).where(AllocationUnit.allocation_id == allocation.allocation_id)
        ).one()
        company = (
            db.get(Company, allocation.destination_company_id)
            if allocation.destination_company_id
            else None
        )
        views.append(
            AllocationView(
                allocation,
                db.get(Area, allocation.destination_area_id),
                company,
                list(refs),
                units_listed,
            )
        )
    return views


def delete(
    db: Session, member: CompanyMember, batch_id: uuid.UUID, allocation_id: uuid.UUID
) -> None:
    own_batch(db, member, batch_id)
    allocation = db.get(BatchAllocation, allocation_id)
    if allocation is None or allocation.batch_id != batch_id:
        raise NotFoundError
    for model in (AllocationCarton, AllocationUnit):
        for row in db.exec(select(model).where(model.allocation_id == allocation_id)):
            db.delete(row)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="batch_allocation",
        entity_id=allocation_id,
        action="deleted",
        old_values={"quantity": allocation.quantity, "batch_id": str(batch_id)},
    )
    db.flush()
    db.delete(allocation)
    db.commit()
