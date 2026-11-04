"""Inventory view per destination for one batch (D142). Computed from events and unit state;
nothing is stored.

A destination is an allocation's (company, area); allocations to the same one are added together.
An event belongs to the destination naming its company and area, otherwise to one naming only its
area, otherwise to the "Not allocated" row. Each count is distinct packs:

- received: packs with a RECEIVED event there;
- in stock: packs IN_STOCK now, placed by their latest receipt, return or correction;
- sold: packs with a standing sale there (a return clears it);
- returned: packs with a RETURNED event there. A returned pack also counts in stock again.
"""

import uuid
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import Area, BatchAllocation, Company, CompanyMember, LifecycleEvent, ProductUnit
from app.models.enums import LifecycleEventType, LifecycleStatus
from app.services.units import own_batch

_STOCK_EVENTS = (
    LifecycleEventType.RECEIVED,
    LifecycleEventType.RETURNED,
    LifecycleEventType.SALE_CORRECTED,
)
Key = tuple[uuid.UUID | None, uuid.UUID | None]
NOT_ALLOCATED: Key = (None, None)


@dataclass
class _Row:
    allocated: int = 0
    received: set[uuid.UUID] = field(default_factory=set)
    in_stock: set[uuid.UUID] = field(default_factory=set)
    sold: set[uuid.UUID] = field(default_factory=set)
    returned: set[uuid.UUID] = field(default_factory=set)


@dataclass(frozen=True)
class InventoryRow:
    company_name: str | None
    area: str | None
    not_allocated: bool
    allocated: int
    received: int
    in_stock: int
    sold: int
    returned: int


def inventory(db: Session, member: CompanyMember, batch_id: uuid.UUID) -> list[InventoryRow]:
    own_batch(db, member, batch_id)
    rows: dict[Key, _Row] = {}
    for allocation in db.exec(select(BatchAllocation).where(BatchAllocation.batch_id == batch_id)):
        key = (allocation.destination_company_id, allocation.destination_area_id)
        rows.setdefault(key, _Row()).allocated += allocation.quantity
    destinations = set(rows)

    def place(company_id: uuid.UUID | None, area_id: uuid.UUID | None) -> _Row:
        for key in ((company_id, area_id), (None, area_id)):
            if key in destinations:
                return rows[key]
        return rows.setdefault(NOT_ALLOCATED, _Row())

    units = db.exec(select(ProductUnit).where(ProductUnit.batch_id == batch_id)).all()
    by_id = {unit.unit_id: unit for unit in units}
    events = db.exec(
        select(LifecycleEvent)
        .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
        .where(
            ProductUnit.batch_id == batch_id,
            LifecycleEvent.event_type.in_([*_STOCK_EVENTS]),
        )
        .order_by(LifecycleEvent.occurred_at, LifecycleEvent.recorded_at)
    ).all()
    latest_stock_event: dict[uuid.UUID, LifecycleEvent] = {}
    for event in events:
        company_id = event.retailer_company_id or event.actor_company_id
        latest_stock_event[event.unit_id] = event
        if event.event_type == LifecycleEventType.RECEIVED:
            place(company_id, event.area_id).received.add(event.unit_id)
        elif event.event_type == LifecycleEventType.RETURNED:
            place(company_id, event.area_id).returned.add(event.unit_id)

    for unit_id, event in latest_stock_event.items():
        if by_id[unit_id].lifecycle_status == LifecycleStatus.IN_STOCK:
            company_id = event.retailer_company_id or event.actor_company_id
            place(company_id, event.area_id).in_stock.add(unit_id)
    for unit in units:
        if unit.last_sold_at is not None:
            place(unit.last_sold_company_id, unit.last_sold_area_id).sold.add(unit.unit_id)

    result = []
    for (company_id, area_id), row in rows.items():
        company = db.get(Company, company_id) if company_id else None
        area = db.get(Area, area_id) if area_id else None
        result.append(
            InventoryRow(
                company_name=company.display_name if company else None,
                area=area.city if area else None,
                not_allocated=(company_id, area_id) == NOT_ALLOCATED,
                allocated=row.allocated,
                received=len(row.received),
                in_stock=len(row.in_stock),
                sold=len(row.sold),
                returned=len(row.returned),
            )
        )
    # Destinations by place, with the "Not allocated" row last.
    return sorted(result, key=lambda r: (r.not_allocated, r.area or "", r.company_name or ""))
