"""Alert workflow (D125, D152): listing, status changes and investigation notes.

Members (owner or staff) of the alert's manufacturer and platform admins may read an alert, change
its status and add notes. Rule 4 alerts have no manufacturer, so only admins see them. Every status
change writes an audit entry; resolving records who and when, and reopening clears them.
"""

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import (
    AppUser,
    Area,
    Carton,
    Company,
    Product,
    ProductBatch,
    ProductUnit,
    RiskAlert,
    RiskAlertNote,
)
from app.models.base import utc_now
from app.models.enums import AlertStatus, RiskRule
from app.services import audit

# Approved wording (30 Oct and 2 Nov 2026).
MSG_NOT_FOUND = "Not found"
MSG_ALREADY_OPEN = "Another open alert already covers this rule and pack."
MSG_NEED_NOTE = "Write a note first."
MSG_BAD_CHANGE = "This status change isn't allowed."

RESOLVED = (AlertStatus.RESOLVED_LEGITIMATE, AlertStatus.RESOLVED_SUSPECTED_COPY)
ALLOWED = {
    AlertStatus.OPEN: {AlertStatus.INVESTIGATING, *RESOLVED},
    AlertStatus.INVESTIGATING: {AlertStatus.OPEN, *RESOLVED},
    AlertStatus.RESOLVED_LEGITIMATE: {AlertStatus.OPEN},
    AlertStatus.RESOLVED_SUSPECTED_COPY: {AlertStatus.OPEN},
}
FILTERS = {
    "OPEN": (AlertStatus.OPEN,),
    "INVESTIGATING": (AlertStatus.INVESTIGATING,),
    "RESOLVED": RESOLVED,
    "ALL": tuple(AlertStatus),
}
MAX_LIST = 200


class AlertError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class AlertDetail:
    alert: RiskAlert
    manufacturer_name: str | None
    product_name: str | None
    batch_number: str | None
    carton_ref: str | None
    area: str | None
    resolved_by_name: str | None
    notes: list[tuple[RiskAlertNote, str]]


def _list(db: Session, status_filter: str, manufacturer_id: uuid.UUID | None, admin: bool):
    statement = select(RiskAlert).where(RiskAlert.status.in_(FILTERS[status_filter]))
    if not admin:
        statement = statement.where(RiskAlert.manufacturer_id == manufacturer_id)
    rows = db.exec(statement.order_by(RiskAlert.updated_at.desc()).limit(MAX_LIST)).all()
    return [detail(db, alert, with_notes=False) for alert in rows]


def list_for_company(db: Session, company_id: uuid.UUID, status_filter: str) -> list[AlertDetail]:
    return _list(db, status_filter, company_id, admin=False)


def list_all(db: Session, status_filter: str) -> list[AlertDetail]:
    return _list(db, status_filter, None, admin=True)


def get_for_company(db: Session, company_id: uuid.UUID, alert_id: uuid.UUID) -> RiskAlert:
    """Another company's alert is reported as not found, so ids cannot be probed."""
    alert = db.get(RiskAlert, alert_id)
    if alert is None or alert.manufacturer_id != company_id:
        raise AlertError(MSG_NOT_FOUND, 404)
    return alert


def get_any(db: Session, alert_id: uuid.UUID) -> RiskAlert:
    alert = db.get(RiskAlert, alert_id)
    if alert is None:
        raise AlertError(MSG_NOT_FOUND, 404)
    return alert


def detail(db: Session, alert: RiskAlert, *, with_notes: bool = True) -> AlertDetail:
    unit = db.get(ProductUnit, alert.unit_id) if alert.unit_id else None
    carton = db.get(Carton, alert.carton_id) if alert.carton_id else None
    batch_id = (
        alert.batch_id or (unit.batch_id if unit else None) or (carton.batch_id if carton else None)
    )
    batch = db.get(ProductBatch, batch_id) if batch_id else None
    product = db.get(Product, batch.product_id) if batch else None
    manufacturer = db.get(Company, alert.manufacturer_id) if alert.manufacturer_id else None
    area = db.get(Area, alert.area_id) if alert.area_id else None
    resolver = db.get(AppUser, alert.resolved_by_user_id) if alert.resolved_by_user_id else None
    notes: list[tuple[RiskAlertNote, str]] = []
    if with_notes:
        rows = db.exec(
            select(RiskAlertNote, AppUser)
            .join(AppUser, AppUser.user_id == RiskAlertNote.author_user_id)
            .where(RiskAlertNote.alert_id == alert.alert_id)
            .order_by(RiskAlertNote.created_at)
        ).all()
        notes = [(note, user.display_name) for note, user in rows]
    return AlertDetail(
        alert=alert,
        manufacturer_name=manufacturer.display_name if manufacturer else None,
        product_name=product.name if product else None,
        batch_number=batch.batch_number if batch else None,
        carton_ref=carton.carton_ref if carton else None,
        area=area.city if area else None,
        resolved_by_name=resolver.display_name if resolver else None,
        notes=notes,
    )


def _open_twin(db: Session, alert: RiskAlert) -> bool:
    """Another OPEN or INVESTIGATING alert with the same rule and subject (the uniqueness the
    database enforces)."""
    statement = select(RiskAlert.alert_id).where(
        RiskAlert.rule == alert.rule,
        RiskAlert.alert_id != alert.alert_id,
        RiskAlert.status.in_((AlertStatus.OPEN, AlertStatus.INVESTIGATING)),
    )
    if alert.rule == RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED:
        statement = statement.where(
            RiskAlert.batch_id == alert.batch_id, RiskAlert.area_id == alert.area_id
        )
    elif alert.unit_id is not None:
        statement = statement.where(RiskAlert.unit_id == alert.unit_id)
    elif alert.carton_id is not None:
        statement = statement.where(RiskAlert.carton_id == alert.carton_id)
    else:
        statement = statement.where(RiskAlert.area_id == alert.area_id)
    return db.exec(statement).first() is not None


def change_status(
    db: Session, user: AppUser, alert: RiskAlert, new_status: AlertStatus
) -> AlertDetail:
    old = alert.status
    if new_status not in ALLOWED[old]:
        raise AlertError(MSG_BAD_CHANGE, 409)
    if old in RESOLVED and _open_twin(db, alert):
        # Reopening would clash with a newer open alert for the same rule and subject.
        raise AlertError(MSG_ALREADY_OPEN, 409)
    now = utc_now()
    alert.status = new_status
    if new_status in RESOLVED:
        alert.resolved_by_user_id, alert.resolved_at = user.user_id, now
    elif new_status == AlertStatus.OPEN:
        alert.resolved_by_user_id, alert.resolved_at = None, None
    alert.updated_at = now
    db.add(alert)
    audit.record(
        db,
        actor_user_id=user.user_id,
        entity_type="risk_alert",
        entity_id=alert.alert_id,
        action="change_status",
        old_values={"status": old},
        new_values={"status": new_status},
    )
    db.commit()
    return detail(db, alert)


def add_note(db: Session, user: AppUser, alert: RiskAlert, body: str) -> AlertDetail:
    body = body.strip()
    if not body:
        raise AlertError(MSG_NEED_NOTE, 422)
    db.add(RiskAlertNote(alert_id=alert.alert_id, author_user_id=user.user_id, body=body))
    alert.updated_at = utc_now()
    db.add(alert)
    db.commit()
    return detail(db, alert)
