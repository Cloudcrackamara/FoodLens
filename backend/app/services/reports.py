"""Anonymous consumer concern reports (D120).

A report may name the code the person checked; it is hashed to find the unit (or carton) and its
manufacturer, and the code itself is never stored. No contact details are taken. Reports are
visible only to the unit's manufacturer and admins, who can mark them reviewed or closed.
"""

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import (
    AppUser,
    Area,
    Carton,
    Company,
    ConsumerReport,
    Product,
    ProductBatch,
    ProductUnit,
)
from app.models.base import utc_now
from app.models.enums import ConcernType, ReportStatus
from app.services import audit, identity

RECEIVED = (
    "Thank you. Your report was sent to the manufacturer and FoodLens admins. FoodLens does not "
    "record who sent it, so nobody will contact you about it."
)


MAX_LIST = 200
MSG_NOT_FOUND = "Not found"
MSG_BAD_CHANGE = "This status change isn't allowed."
ALLOWED = {
    ReportStatus.NEW: {ReportStatus.REVIEWED, ReportStatus.CLOSED},
    ReportStatus.REVIEWED: {ReportStatus.CLOSED},
    ReportStatus.CLOSED: set(),
}


def submit_report(
    db: Session,
    *,
    code: str | None,
    concern_type: ConcernType,
    description: str,
    area: Area | None,
) -> ConsumerReport:
    unit = carton = None
    if code and code.strip():
        digest = identity.token_hash(code)
        unit = db.exec(select(ProductUnit).where(ProductUnit.qr_token_hash == digest)).first()
        if unit is None:
            carton = db.exec(select(Carton).where(Carton.qr_token_hash == digest)).first()
    subject = unit or carton
    report = ConsumerReport(
        unit_id=unit.unit_id if unit else None,
        manufacturer_id=subject.manufacturer_id if subject else None,
        concern_type=concern_type,
        description=description.strip(),
        area_id=area.area_id if area else None,
    )
    db.add(report)
    db.commit()
    return report


# --- Reading and reviewing reports (D120, D154) ---------------------------------------------


class ReportError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ReportView:
    report: ConsumerReport
    manufacturer_name: str | None
    product_name: str | None
    batch_number: str | None
    area: str | None


def _view(db: Session, report: ConsumerReport) -> ReportView:
    unit = db.get(ProductUnit, report.unit_id) if report.unit_id else None
    batch = db.get(ProductBatch, unit.batch_id) if unit else None
    product = db.get(Product, unit.product_id) if unit else None
    company = db.get(Company, report.manufacturer_id) if report.manufacturer_id else None
    area = db.get(Area, report.area_id) if report.area_id else None
    return ReportView(
        report=report,
        manufacturer_name=company.display_name if company else None,
        product_name=product.name if product else None,
        batch_number=batch.batch_number if batch else None,
        area=area.city if area else None,
    )


def list_reports(
    db: Session, *, manufacturer_id: uuid.UUID | None, status: ReportStatus | None, admin: bool
) -> list[ReportView]:
    """Newest first. A manufacturer sees only reports on its own packs; admins see all."""
    statement = select(ConsumerReport).order_by(ConsumerReport.created_at.desc()).limit(MAX_LIST)
    if not admin:
        statement = statement.where(ConsumerReport.manufacturer_id == manufacturer_id)
    if status is not None:
        statement = statement.where(ConsumerReport.status == status)
    return [_view(db, report) for report in db.exec(statement).all()]


def change_status(
    db: Session,
    user: AppUser,
    report_id: uuid.UUID,
    new_status: ReportStatus,
    *,
    manufacturer_id: uuid.UUID | None,
    admin: bool,
) -> ReportView:
    report = db.get(ConsumerReport, report_id)
    if report is None or (not admin and report.manufacturer_id != manufacturer_id):
        raise ReportError(MSG_NOT_FOUND, 404)  # another company's report looks like a missing one
    old = report.status
    if new_status not in ALLOWED[old]:
        raise ReportError(MSG_BAD_CHANGE, 409)
    report.status = new_status
    report.updated_at = utc_now()
    db.add(report)
    audit.record(
        db,
        actor_user_id=user.user_id,
        entity_type="consumer_report",
        entity_id=report.report_id,
        action="change_status",
        old_values={"status": old},
        new_values={"status": new_status},
    )
    db.commit()
    return _view(db, report)
