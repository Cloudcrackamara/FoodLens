"""Lifecycle events and the derived unit/carton status (D112).

This module is the only writer of `lifecycle_status` and `current_holder_company_id`. Each
change is written in the same transaction as the event that causes it. Phase 2 covers the
manufacturer events: ISSUED, RELEASED and VOIDED. Phase 4 adds the merchant events (RECEIVED,
TRANSFERRED, SOLD, RETURNED, SALE_CORRECTED) with the custody, return and allocation rules.
Phase 5 adds replay_unit, which POS writes use so late offline events land in occurred_at order.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, insert, or_, update
from sqlmodel import Session, select

from app.models import (
    AllocationCarton,
    AllocationUnit,
    BatchAllocation,
    Carton,
    Company,
    CompanyMember,
    LifecycleEvent,
    Product,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    SupplierLocation,
)
from app.models.base import utc_now
from app.models.enums import (
    AnnouncementKind,
    AnnouncementStatus,
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    ReviewStatus,
)
from app.services.identity import token_hash

# Status a unit or carton moves to on each manufacturer event.
NEW_STATUS = {
    LifecycleEventType.ISSUED: LifecycleStatus.ISSUED,
    LifecycleEventType.RELEASED: LifecycleStatus.RELEASED,
    LifecycleEventType.VOIDED: LifecycleStatus.VOIDED,
}


def record_manufacturer_event(
    db: Session,
    member: CompanyMember,
    event_type: LifecycleEventType,
    *,
    unit_ids: Sequence[uuid.UUID],
    carton_ids: Sequence[uuid.UUID] = (),
    reason: str | None = None,
    occurred_at: datetime | None = None,
) -> uuid.UUID:
    """Write one event per unit and per carton, sharing a group_id, and move them to the event's
    status. The manufacturer stays the holder. Returns the group_id."""
    group_id = uuid.uuid4()
    when = occurred_at or utc_now()
    common = {
        "group_id": group_id,
        "event_type": event_type,
        "source": EventSource.MANUFACTURER,
        "actor_user_id": member.user_id,
        "actor_company_id": member.company_id,
        "occurred_at": when,
        "recorded_at": when,
        "reason": reason,
        "received_without_transfer": False,
        "outside_allocation": False,
    }
    rows = [{"event_id": uuid.uuid4(), "carton_id": c, **common} for c in carton_ids]
    rows += [{"event_id": uuid.uuid4(), "unit_id": u, **common} for u in unit_ids]
    if rows:
        db.execute(insert(LifecycleEvent), rows)

    values = {
        "lifecycle_status": NEW_STATUS[event_type],
        "current_holder_company_id": member.company_id,
        "updated_at": when,
    }
    if unit_ids:
        db.execute(
            update(ProductUnit).where(ProductUnit.unit_id.in_(unit_ids)).values(**values),
            execution_options={"synchronize_session": False},
        )
    if carton_ids:
        db.execute(
            update(Carton).where(Carton.carton_id.in_(carton_ids)).values(**values),
            execution_options={"synchronize_session": False},
        )
    return group_id


def refresh_batch_release(db: Session, batch: ProductBatch) -> None:
    """`released_at` is set while every live (not voided) unit of the batch is released, and
    cleared otherwise. It is a cache; the units are the truth."""
    counts = dict(
        db.exec(
            select(ProductUnit.lifecycle_status, func.count())
            .where(ProductUnit.batch_id == batch.batch_id)
            .group_by(ProductUnit.lifecycle_status)
        ).all()
    )
    live = sum(n for status, n in counts.items() if status != LifecycleStatus.VOIDED)
    unreleased = counts.get(LifecycleStatus.ISSUED, 0)
    if live and not unreleased:
        batch.released_at = batch.released_at or utc_now()
    else:
        batch.released_at = None
    db.add(batch)


# --- Merchant events (Phase 4: D112, D113, D140, D142) -----------------------------------------

MERCHANT_EVENTS = (
    LifecycleEventType.RECEIVED,
    LifecycleEventType.TRANSFERRED,
    LifecycleEventType.SOLD,
    LifecycleEventType.RETURNED,
    LifecycleEventType.SALE_CORRECTED,
)

# Wording shown to merchants. Kept together so it can be reviewed in one place.
MSG_NOT_APPROVED = "Your company profile must be approved before you can record events."
MSG_NOT_MERCHANT = "Only distributor and retailer companies can record stock events."
MSG_NO_LOCATION = "Your company needs a reviewed location with an area before it can record events."
MSG_UNKNOWN_CODE = "No FoodLens code found. Check the code and try again."
MSG_NO_PACKS = "This carton has no packs to record."
MSG_VOIDED = "This code was voided by the manufacturer, so it can't be recorded."
MSG_UNRELEASED = (
    "The manufacturer has not released this code for sale yet, so it can't be recorded."
)
MSG_RECALLED = "This pack is covered by a recall, so it can't be recorded."
MSG_SOLD = "This pack is already recorded as sold."
MSG_IN_STOCK = "Your company already has this pack in stock."
MSG_NOT_HOLDER = "Only the company holding this pack in stock can transfer it."
MSG_NOT_SOLD = "This pack is not recorded as sold."
MSG_NOT_SELLER = "Only the company that recorded the sale can do this."
MSG_NEED_TARGET = "Choose the company receiving the stock."
MSG_BAD_TARGET = "Choose another approved company."
MSG_NEED_REASON = "Give a reason for the correction."
MSG_BAD_EVENT = "Choose RECEIVED, TRANSFERRED, SOLD, RETURNED or SALE_CORRECTED."
NOTE_NO_TRANSFER = "Received without a recorded transfer."
NOTE_OUTSIDE = "Received outside its allocation."


def carton_problem(bad: int, total: int, first: str) -> str:
    return f"{bad} of the {total} packs in this carton can't take this event. {first}"


class MerchantError(Exception):
    """A refused merchant event. `status_code` is the HTTP status the router returns."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class Subject:
    """What a scanned or typed code points at, with the units an event would touch."""

    carton: Carton | None
    units: list[ProductUnit]
    product: Product
    batch: ProductBatch
    recalled: bool

    @property
    def kind(self) -> str:
        return "CARTON" if self.carton else "UNIT"


@dataclass
class MerchantResult:
    event_type: LifecycleEventType
    subject: str
    units: int
    group_id: uuid.UUID
    status_after: LifecycleStatus
    notes: list[str]


def merchant_company(db: Session, member: CompanyMember) -> Company:
    """The member's company, if it may record merchant events: approved, distributor or retailer."""
    company = db.get(Company, member.company_id)
    if company is None or company.review_status != CompanyReviewStatus.APPROVED:
        raise MerchantError(MSG_NOT_APPROVED, 409)
    if not (company.is_distributor or company.is_retailer):
        raise MerchantError(MSG_NOT_MERCHANT, 403)
    return company


def company_area_id(db: Session, company_id: uuid.UUID) -> uuid.UUID:
    """The area of the company's oldest reviewed location (never sent by the client)."""
    location = db.exec(
        select(SupplierLocation)
        .where(
            SupplierLocation.company_id == company_id,
            SupplierLocation.review_status == ReviewStatus.APPROVED,
            SupplierLocation.area_id.is_not(None),
        )
        .order_by(SupplierLocation.created_at)
    ).first()
    if location is None or location.area_id is None:
        raise MerchantError(MSG_NO_LOCATION, 409)
    return location.area_id


def find_subject(db: Session, code: str) -> Subject:
    digest = token_hash(code)
    carton: Carton | None = None
    unit = db.exec(select(ProductUnit).where(ProductUnit.qr_token_hash == digest)).first()
    if unit is not None:
        units = [unit]
        batch = db.get(ProductBatch, unit.batch_id)
    else:
        carton = db.exec(select(Carton).where(Carton.qr_token_hash == digest)).first()
        if carton is None:
            raise MerchantError(MSG_UNKNOWN_CODE, 404)
        units = list(
            db.exec(select(ProductUnit).where(ProductUnit.parent_carton_id == carton.carton_id))
        )
        batch = db.get(ProductBatch, carton.batch_id)
    product = db.get(Product, batch.product_id) if batch else None
    manufacturer = db.get(Company, product.company_id) if product else None
    if batch is None or product is None or manufacturer is None:
        raise MerchantError(MSG_UNKNOWN_CODE, 404)
    if manufacturer.review_status != CompanyReviewStatus.APPROVED:
        raise MerchantError(MSG_UNKNOWN_CODE, 404)
    live_recall = db.exec(
        select(ProductAnnouncement.announcement_id).where(
            ProductAnnouncement.product_id == product.product_id,
            ProductAnnouncement.kind == AnnouncementKind.RECALL,
            ProductAnnouncement.status == AnnouncementStatus.LIVE,
            or_(
                ProductAnnouncement.batch_id.is_(None),
                ProductAnnouncement.batch_id == batch.batch_id,
            ),
        )
    ).first()
    return Subject(carton, units, product, batch, live_recall is not None)


def unit_problem(
    unit: ProductUnit, event: LifecycleEventType, company_id: uuid.UUID, recalled: bool
) -> tuple[str, int] | None:
    """Why this unit cannot take this event from this company, or None."""
    status = unit.lifecycle_status
    held = unit.current_holder_company_id == company_id
    if status == LifecycleStatus.VOIDED:
        return MSG_VOIDED, 409
    if status == LifecycleStatus.ISSUED:
        return MSG_UNRELEASED, 409
    if recalled or status == LifecycleStatus.RECALLED:
        return MSG_RECALLED, 409
    match event:
        case LifecycleEventType.RECEIVED:
            if status == LifecycleStatus.SOLD:
                return MSG_SOLD, 409
            if status == LifecycleStatus.IN_STOCK and held:
                return MSG_IN_STOCK, 409
        case LifecycleEventType.SOLD:
            if status == LifecycleStatus.SOLD:
                return MSG_SOLD, 409
        case LifecycleEventType.TRANSFERRED:
            if status == LifecycleStatus.SOLD:
                return MSG_SOLD, 409
            if not (status == LifecycleStatus.IN_STOCK and held):
                return MSG_NOT_HOLDER, 409
        case LifecycleEventType.RETURNED | LifecycleEventType.SALE_CORRECTED:
            if status != LifecycleStatus.SOLD:
                return MSG_NOT_SOLD, 409
            if unit.last_sold_company_id != company_id:
                return MSG_NOT_SELLER, 403
    return None


def subject_problem(
    subject: Subject, event: LifecycleEventType, company_id: uuid.UUID
) -> tuple[str, int] | None:
    if not subject.units:
        return MSG_NO_PACKS, 409
    problems = [
        p
        for unit in subject.units
        if (p := unit_problem(unit, event, company_id, subject.recalled)) is not None
    ]
    if not problems:
        return None
    status_code = 403 if any(code == 403 for _, code in problems) else problems[0][1]
    first = next(message for message, code in problems if code == status_code)
    if subject.carton is None:
        return first, status_code
    return carton_problem(len(problems), len(subject.units), first), status_code


def without_transfer(unit: ProductUnit, event: LifecycleEventType, company_id: uuid.UUID) -> bool:
    """D113: a receipt or sale with no transfer to this company is allowed but labelled."""
    held = unit.current_holder_company_id == company_id
    status = unit.lifecycle_status
    if event == LifecycleEventType.RECEIVED:
        return not (status == LifecycleStatus.IN_TRANSIT and held)
    if event == LifecycleEventType.SOLD:
        return not (held and status in (LifecycleStatus.IN_TRANSIT, LifecycleStatus.IN_STOCK))
    return False


def _outside_allocation(
    db: Session,
    batch_id: uuid.UUID,
    company_id: uuid.UUID,
    area_id: uuid.UUID,
    units: Sequence[ProductUnit],
) -> dict[uuid.UUID, bool]:
    """D142, advisory. A listed unit, then its listed carton, then any allocation of the batch to
    this company and area that still has quantity left. A batch with no allocations is never
    outside its allocation."""
    allocations = list(db.exec(select(BatchAllocation).where(BatchAllocation.batch_id == batch_id)))
    if not allocations:
        return {unit.unit_id: False for unit in units}
    ids = [a.allocation_id for a in allocations]
    by_unit = dict(
        db.exec(
            select(AllocationUnit.unit_id, AllocationUnit.allocation_id).where(
                AllocationUnit.allocation_id.in_(ids)
            )
        ).all()
    )
    by_carton = dict(
        db.exec(
            select(AllocationCarton.carton_id, AllocationCarton.allocation_id).where(
                AllocationCarton.allocation_id.in_(ids)
            )
        ).all()
    )
    by_id = {a.allocation_id: a for a in allocations}

    def matches(a: BatchAllocation) -> bool:
        return a.destination_company_id in (None, company_id) and a.destination_area_id == area_id

    remaining: dict[uuid.UUID, int] = {}
    for a in allocations:
        if not matches(a):
            continue
        received = [
            ProductUnit.batch_id == batch_id,
            LifecycleEvent.event_type == LifecycleEventType.RECEIVED,
            LifecycleEvent.outside_allocation.is_(False),
            LifecycleEvent.area_id == area_id,
        ]
        if a.destination_company_id:
            received.append(LifecycleEvent.actor_company_id == company_id)
        used = db.exec(
            select(func.count())
            .select_from(LifecycleEvent)
            .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
            .where(*received)
        ).one()
        remaining[a.allocation_id] = a.quantity - used

    outside: dict[uuid.UUID, bool] = {}
    for unit in units:
        listed = by_unit.get(unit.unit_id) or by_carton.get(unit.parent_carton_id)
        if listed:
            inside = matches(by_id[listed])
            if inside and listed in remaining:
                remaining[listed] -= 1
        else:
            pick = next((aid for aid, left in remaining.items() if left > 0), None)
            inside = pick is not None
            if pick is not None:
                remaining[pick] -= 1
        outside[unit.unit_id] = not inside
    return outside


def standing_sale(db: Session, unit_id: uuid.UUID) -> uuid.UUID | None:
    return db.exec(
        select(LifecycleEvent.event_id)
        .where(
            LifecycleEvent.unit_id == unit_id,
            LifecycleEvent.event_type == LifecycleEventType.SOLD,
        )
        .order_by(LifecycleEvent.occurred_at.desc(), LifecycleEvent.recorded_at.desc())
    ).first()


def record_merchant_event(
    db: Session,
    member: CompanyMember,
    code: str,
    event_type: LifecycleEventType,
    *,
    to_company_id: uuid.UUID | None = None,
    reason: str | None = None,
    occurred_at: datetime | None = None,
) -> MerchantResult:
    """Record one merchant event for a unit or a carton (every unit inside, all or nothing).
    The status, holder, sold state and area are decided here, never by the client."""
    if event_type not in MERCHANT_EVENTS:
        raise MerchantError(MSG_BAD_EVENT, 422)
    company = merchant_company(db, member)
    reason = (reason or "").strip() or None
    if event_type == LifecycleEventType.SALE_CORRECTED and reason is None:
        raise MerchantError(MSG_NEED_REASON, 422)
    if event_type == LifecycleEventType.TRANSFERRED:
        if to_company_id is None:
            raise MerchantError(MSG_NEED_TARGET, 422)
        target = db.get(Company, to_company_id)
        if (
            target is None
            or target.review_status != CompanyReviewStatus.APPROVED
            or target.company_id == company.company_id
        ):
            raise MerchantError(MSG_BAD_TARGET, 422)
    else:
        to_company_id = None
    area_id = company_area_id(db, company.company_id)
    subject = find_subject(db, code)
    problem = subject_problem(subject, event_type, company.company_id)
    if problem:
        raise MerchantError(*problem)

    group_id = uuid.uuid4()
    when = occurred_at or utc_now()
    units = subject.units
    flags = {u.unit_id: without_transfer(u, event_type, company.company_id) for u in units}
    if event_type == LifecycleEventType.RECEIVED:
        outside = _outside_allocation(
            db, subject.batch.batch_id, company.company_id, area_id, units
        )
    else:
        outside = {u.unit_id: False for u in units}

    new_status, new_holder = {
        LifecycleEventType.RECEIVED: (LifecycleStatus.IN_STOCK, company.company_id),
        LifecycleEventType.TRANSFERRED: (LifecycleStatus.IN_TRANSIT, to_company_id),
        LifecycleEventType.SOLD: (LifecycleStatus.SOLD, company.company_id),
        LifecycleEventType.RETURNED: (LifecycleStatus.IN_STOCK, company.company_id),
        LifecycleEventType.SALE_CORRECTED: (LifecycleStatus.IN_STOCK, company.company_id),
    }[event_type]

    common = {
        "group_id": group_id,
        "event_type": event_type,
        "source": EventSource.MERCHANT_APP,
        "actor_user_id": member.user_id,
        "actor_company_id": company.company_id,
        "to_company_id": to_company_id,
        "area_id": area_id,
        "occurred_at": when,
        "recorded_at": when,
        "reason": reason,
    }
    rows = []
    if subject.carton is not None:
        rows.append(
            {
                "event_id": uuid.uuid4(),
                "carton_id": subject.carton.carton_id,
                "received_without_transfer": any(flags.values()),
                "outside_allocation": any(outside.values()),
                **common,
            }
        )
    undoing = event_type in (LifecycleEventType.RETURNED, LifecycleEventType.SALE_CORRECTED)
    for unit in units:
        sale = standing_sale(db, unit.unit_id) if undoing else None
        rows.append(
            {
                "event_id": uuid.uuid4(),
                "unit_id": unit.unit_id,
                "received_without_transfer": flags[unit.unit_id],
                "outside_allocation": outside[unit.unit_id],
                "returns_event_id": sale if event_type == LifecycleEventType.RETURNED else None,
                "corrects_event_id": (
                    sale if event_type == LifecycleEventType.SALE_CORRECTED else None
                ),
                **common,
            }
        )
    db.execute(insert(LifecycleEvent), rows)

    values: dict = {
        "lifecycle_status": new_status,
        "current_holder_company_id": new_holder,
        "updated_at": when,
    }
    unit_values = dict(values)
    if event_type == LifecycleEventType.SOLD:
        unit_values |= {
            "last_sold_at": when,
            "last_sold_area_id": area_id,
            "last_sold_company_id": company.company_id,
        }
    elif undoing:
        unit_values |= {
            "last_sold_at": None,
            "last_sold_area_id": None,
            "last_sold_company_id": None,
        }
    db.execute(
        update(ProductUnit)
        .where(ProductUnit.unit_id.in_([u.unit_id for u in units]))
        .values(**unit_values),
        execution_options={"synchronize_session": False},
    )
    if subject.carton is not None:
        db.execute(
            update(Carton).where(Carton.carton_id == subject.carton.carton_id).values(**values),
            execution_options={"synchronize_session": False},
        )
    db.commit()

    notes = []
    if any(flags.values()):
        notes.append(NOTE_NO_TRANSFER)
    if any(outside.values()):
        notes.append(NOTE_OUTSIDE)
    return MerchantResult(event_type, subject.kind, len(units), group_id, new_status, notes)


def allowed_events(subject: Subject, company_id: uuid.UUID) -> list[LifecycleEventType]:
    return [e for e in MERCHANT_EVENTS if subject_problem(subject, e, company_id) is None]


# --- Replay (D112, D151) -------------------------------------------------------------------


def replay_unit(db: Session, unit: ProductUnit) -> None:
    """Derive the unit's status, holder and sold state from all its events in occurred_at order
    (recorded_at breaks ties), so a late offline event takes its place in the history. A late
    event older than an existing later event ends with the later event's state (D151)."""
    events = db.exec(
        select(LifecycleEvent)
        .where(LifecycleEvent.unit_id == unit.unit_id)
        .order_by(LifecycleEvent.occurred_at, LifecycleEvent.recorded_at, LifecycleEvent.created_at)
    ).all()
    status, holder = LifecycleStatus.ISSUED, unit.manufacturer_id
    sold: LifecycleEvent | None = None
    for event in events:
        company = event.retailer_company_id or event.actor_company_id
        match event.event_type:
            case LifecycleEventType.ISSUED | LifecycleEventType.RELEASED:
                status, holder = NEW_STATUS[event.event_type], company or holder
            case LifecycleEventType.VOIDED:
                status = LifecycleStatus.VOIDED
            case LifecycleEventType.RECALLED:
                status = LifecycleStatus.RECALLED
            case LifecycleEventType.TRANSFERRED:
                status, holder = LifecycleStatus.IN_TRANSIT, event.to_company_id
            case LifecycleEventType.RECEIVED:
                status, holder = LifecycleStatus.IN_STOCK, company
            case LifecycleEventType.SOLD:
                status, holder, sold = LifecycleStatus.SOLD, company, event
            case LifecycleEventType.RETURNED | LifecycleEventType.SALE_CORRECTED:
                status, holder, sold = LifecycleStatus.IN_STOCK, company, None
    db.execute(
        update(ProductUnit)
        .where(ProductUnit.unit_id == unit.unit_id)
        .values(
            lifecycle_status=status,
            current_holder_company_id=holder,
            last_sold_at=sold.occurred_at if sold else None,
            last_sold_area_id=sold.area_id if sold else None,
            last_sold_company_id=(sold.retailer_company_id or sold.actor_company_id)
            if sold
            else None,
            updated_at=utc_now(),
        ),
        execution_options={"synchronize_session": False},
    )
