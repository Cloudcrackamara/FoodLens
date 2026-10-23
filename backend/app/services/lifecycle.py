"""Lifecycle events and the derived unit/carton status (D112).

This module is the only writer of `lifecycle_status` and `current_holder_company_id`. Each
change is written in the same transaction as the event that causes it. Phase 2 covers the
manufacturer events: ISSUED, RELEASED and VOIDED. Merchant and POS events, custody and replay
arrive in Phase 4.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, insert, update
from sqlmodel import Session, select

from app.models import Carton, CompanyMember, LifecycleEvent, ProductBatch, ProductUnit
from app.models.base import utc_now
from app.models.enums import EventSource, LifecycleEventType, LifecycleStatus

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
