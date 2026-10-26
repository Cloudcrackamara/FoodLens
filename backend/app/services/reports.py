"""Anonymous consumer concern reports (D120).

A report may name the code the person checked; it is hashed to find the unit (or carton) and its
manufacturer, and the code itself is never stored. No contact details are taken. Reports are
visible only to the unit's manufacturer and admins (dashboards, Phase 7).
"""

from sqlmodel import Session, select

from app.models import Area, Carton, ConsumerReport, ProductUnit
from app.models.enums import ConcernType
from app.services import identity

RECEIVED = (
    "Thank you. Your report was sent to the manufacturer and FoodLens admins. FoodLens does not "
    "record who sent it, so nobody will contact you about it."
)


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
