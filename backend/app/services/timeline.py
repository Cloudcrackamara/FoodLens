"""A pack's or carton's history in plain words, for its own manufacturer (D118, D144).

Reached by typing the code, or from an alert. Reuses the consumer check's wording for the events,
and adds what only the manufacturer sees: voids and the neutral allocation note. Another company's
code looks the same as an unknown one. No token, hash or internal id is returned.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, select

from app.models import Carton, LifecycleEvent, ProductUnit, RiskAlert
from app.models.enums import AlertLevel, LifecycleEventType, LifecycleStatus
from app.services import check, identity, lifecycle
from app.services.check import event_fact
from app.services.risk import OPEN_STATUSES, RULE_NAMES

MSG_NOT_FOUND = "We couldn't find that code among your packs."


class TimelineNotFound(Exception):
    pass


@dataclass(frozen=True)
class TimelineEntry:
    at: datetime
    event_type: LifecycleEventType
    text: str
    note: str | None


@dataclass(frozen=True)
class OpenAlert:
    alert_id: uuid.UUID
    rule_name: str
    level: AlertLevel


@dataclass(frozen=True)
class Timeline:
    subject: str
    code_last4: str | None
    product_name: str
    size: str | None
    batch_number: str
    expiry_date: date | None
    status: LifecycleStatus
    entries: list[TimelineEntry]
    open_alerts: list[OpenAlert]


def _build(
    db: Session, unit: ProductUnit | None, carton: Carton | None, last4: str | None
) -> Timeline:
    subject = unit or carton
    ctx = check.batch_context(db, subject.batch_id) if subject else None
    if subject is None or ctx is None:
        raise TimelineNotFound
    column = LifecycleEvent.unit_id if unit else LifecycleEvent.carton_id
    subject_id = unit.unit_id if unit else carton.carton_id
    events = db.exec(
        select(LifecycleEvent)
        .where(column == subject_id)
        .order_by(LifecycleEvent.occurred_at, LifecycleEvent.recorded_at)
    ).all()
    entries = []
    for event in events:
        text = event_fact(db, event, ctx)
        if event.event_type == LifecycleEventType.VOIDED:
            day = check._day(event.occurred_at)
            text = f"Code voided by {ctx.manufacturer.display_name} on {day}."
        if text:
            note = lifecycle.NOTE_OUTSIDE if event.outside_allocation else None
            entries.append(TimelineEntry(event.occurred_at, event.event_type, text, note))
    alert_filter = (
        RiskAlert.unit_id == unit.unit_id
        if unit
        else (RiskAlert.carton_id == carton.carton_id) & RiskAlert.unit_id.is_(None)
    )
    alerts = db.exec(
        select(RiskAlert)
        .where(alert_filter, RiskAlert.status.in_(OPEN_STATUSES))
        .order_by(RiskAlert.created_at)
    ).all()
    return Timeline(
        subject="PACK" if unit else "CARTON",
        code_last4=last4,
        product_name=ctx.product.name,
        size=ctx.product.size,
        batch_number=ctx.batch.batch_number,
        expiry_date=ctx.batch.expiry_date,
        status=subject.lifecycle_status,
        entries=entries,
        open_alerts=[OpenAlert(a.alert_id, RULE_NAMES[a.rule], a.level) for a in alerts],
    )


def by_code(db: Session, company_id: uuid.UUID, code: str) -> Timeline:
    digest = identity.token_hash(code)
    unit = db.exec(select(ProductUnit).where(ProductUnit.qr_token_hash == digest)).first()
    carton = None if unit else db.exec(select(Carton).where(Carton.qr_token_hash == digest)).first()
    subject = unit or carton
    if subject is None or subject.manufacturer_id != company_id:
        raise TimelineNotFound
    return _build(db, unit, carton, check.last4(code))


def by_alert(db: Session, company_id: uuid.UUID, alert_id: uuid.UUID) -> Timeline:
    """Rule 4 and rule 9 alerts have no pack, so they have no timeline. No code is stored, so the
    last four characters are unknown here."""
    alert = db.get(RiskAlert, alert_id)
    if alert is None or alert.manufacturer_id != company_id:
        raise TimelineNotFound
    unit = db.get(ProductUnit, alert.unit_id) if alert.unit_id else None
    carton = db.get(Carton, alert.carton_id) if alert.carton_id else None
    return _build(db, unit, carton, None)
