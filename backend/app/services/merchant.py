"""Read side of the merchant page: what a code points at, for the merchant's own company. It
writes nothing; events are recorded by services/lifecycle.py. No unit or carton IDs leave here."""

from collections import Counter

from sqlmodel import Session, select

from app.models import Company, CompanyMember
from app.models.enums import CompanyReviewStatus, LifecycleEventType, LifecycleStatus
from app.services import lifecycle
from app.services.identity import normalise
from app.services.lifecycle import MerchantError, Subject


def lookup(db: Session, member: CompanyMember, code: str) -> tuple[Subject, str, dict]:
    company = lifecycle.merchant_company(db, member)
    subject = lifecycle.find_subject(db, code)
    counts = Counter(u.lifecycle_status for u in subject.units)
    first = subject.units[0] if subject.units else None
    if subject.carton is not None and first is None:
        raise MerchantError(lifecycle.MSG_NO_PACKS, 409)
    status = subject.carton.lifecycle_status if subject.carton else first.lifecycle_status
    allowed = lifecycle.allowed_events(subject, company.company_id)
    details = {
        "status": status,
        "status_counts": [{"status": s, "packs": n} for s, n in counts.items()],
        "you_hold": sum(
            1
            for u in subject.units
            if u.current_holder_company_id == company.company_id
            and u.lifecycle_status in (LifecycleStatus.IN_STOCK, LifecycleStatus.IN_TRANSIT)
        ),
        "sold_by_you": sum(
            1
            for u in subject.units
            if u.lifecycle_status == LifecycleStatus.SOLD
            and u.last_sold_company_id == company.company_id
        ),
        "allowed_events": allowed,
        "blocked_reason": None,
    }
    if not allowed:
        problem = lifecycle.subject_problem(
            subject, LifecycleEventType.RECEIVED, company.company_id
        )
        details["blocked_reason"] = problem[0] if problem else None
    return subject, normalise(code)[-4:], details


def destinations(db: Session, member: CompanyMember) -> list[Company]:
    """Approved companies a transfer can go to: everyone approved except the sender."""
    lifecycle.merchant_company(db, member)
    return list(
        db.exec(
            select(Company)
            .where(
                Company.review_status == CompanyReviewStatus.APPROVED,
                Company.company_id != member.company_id,
            )
            .order_by(Company.display_name)
        ).all()
    )
