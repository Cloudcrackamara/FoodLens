"""Company registration, admin company review, and supplier locations.

Rules (CLAUDE.md rules 4 and 7, docs/DECISIONS.md D54-D60):
- A new company starts PENDING_REVIEW; its registering user becomes OWNER.
- Only admins decide, and never on a company they belong to.
- Only approved companies can add locations; locations start PENDING_REVIEW.
- Every decision records reviewer, time, and note, and writes an audit entry.
"""

import uuid

from sqlmodel import Session, select

from app.models import AppUser, Company, CompanyMember, SupplierLocation
from app.models.base import utc_now
from app.models.enums import (
    CompanyReviewStatus,
    MemberRole,
    MembershipStatus,
    ReviewStatus,
)
from app.schemas.company import (
    CompanyDecision,
    CompanyRegisterRequest,
    LocationCreateRequest,
    LocationDecision,
)
from app.services import audit
from app.services.auth import active_membership


class AlreadyInCompanyError(Exception):
    pass


class AdminCannotRegisterCompanyError(Exception):
    pass


class NotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConflictOfInterestError(Exception):
    pass


class CompanyNotApprovedError(Exception):
    pass


class InvalidContactError(Exception):
    pass


# --- Registration ---------------------------------------------------------------------------


def register_company(db: Session, user: AppUser, data: CompanyRegisterRequest) -> Company:
    """Create a company in PENDING_REVIEW with `user` as OWNER. Only fields in the request
    schema are used; review status and reviewer always start empty."""
    if user.is_admin:
        raise AdminCannotRegisterCompanyError
    if db.exec(select(CompanyMember).where(CompanyMember.user_id == user.user_id)).first():
        raise AlreadyInCompanyError

    company = Company(
        company_type=data.company_type,
        display_name=data.display_name,
        contact_email=str(data.contact_email).lower(),
        contact_phone=data.contact_phone or None,
        claimed_legal_name=data.claimed_legal_name,
        claimed_business_identifier=data.claimed_business_identifier or None,
        claimed_address=data.claimed_address or None,
    )
    db.add(company)
    db.flush()
    db.add(
        CompanyMember(
            user_id=user.user_id,
            company_id=company.company_id,
            role=MemberRole.OWNER,
            membership_status=MembershipStatus.ACTIVE,
        )
    )
    audit.record(
        db,
        actor_user_id=user.user_id,
        entity_type="company",
        entity_id=company.company_id,
        action="registered",
        new_values={"review_status": company.review_status, "display_name": company.display_name},
    )
    db.commit()
    db.refresh(company)
    return company


# --- Reads ----------------------------------------------------------------------------------


def get_company(db: Session, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError
    return company


def company_locations(db: Session, company_id: uuid.UUID) -> list[SupplierLocation]:
    return list(
        db.exec(
            select(SupplierLocation)
            .where(SupplierLocation.company_id == company_id)
            .order_by(SupplierLocation.created_at)
        ).all()
    )


def list_companies(db: Session, status: CompanyReviewStatus | None) -> list[Company]:
    statement = select(Company).order_by(Company.created_at)
    if status is not None:
        statement = statement.where(Company.review_status == status)
    return list(db.exec(statement).all())


def company_owner(db: Session, company_id: uuid.UUID) -> AppUser | None:
    return db.exec(
        select(AppUser)
        .join(CompanyMember, CompanyMember.user_id == AppUser.user_id)
        .where(CompanyMember.company_id == company_id, CompanyMember.role == MemberRole.OWNER)
    ).first()


def list_locations(
    db: Session, status: ReviewStatus | None
) -> list[tuple[SupplierLocation, Company]]:
    statement = (
        select(SupplierLocation, Company)
        .join(Company, Company.company_id == SupplierLocation.company_id)
        .order_by(SupplierLocation.created_at)
    )
    if status is not None:
        statement = statement.where(SupplierLocation.review_status == status)
    return list(db.exec(statement).all())


# --- Admin decisions ------------------------------------------------------------------------

_COMPANY_TRANSITIONS = {
    CompanyDecision.APPROVE: (
        {CompanyReviewStatus.PENDING_REVIEW, CompanyReviewStatus.SUSPENDED},
        CompanyReviewStatus.APPROVED,
    ),
    CompanyDecision.REJECT: ({CompanyReviewStatus.PENDING_REVIEW}, CompanyReviewStatus.REJECTED),
    CompanyDecision.SUSPEND: ({CompanyReviewStatus.APPROVED}, CompanyReviewStatus.SUSPENDED),
}

_LOCATION_TRANSITIONS = {
    LocationDecision.APPROVE: ({ReviewStatus.PENDING_REVIEW}, ReviewStatus.APPROVED),
    LocationDecision.REJECT: ({ReviewStatus.PENDING_REVIEW}, ReviewStatus.REJECTED),
}


def _ensure_no_conflict(db: Session, admin: AppUser, company_id: uuid.UUID) -> None:
    """Admins never review a company they belong to (no self-approval, rule 4)."""
    if active_membership(db, user_id=admin.user_id, company_id=company_id) is not None:
        raise ConflictOfInterestError


def decide_company(
    db: Session,
    admin: AppUser,
    company_id: uuid.UUID,
    decision: CompanyDecision,
    note: str | None,
) -> Company:
    company = get_company(db, company_id)
    _ensure_no_conflict(db, admin, company_id)

    allowed_from, new_status = _COMPANY_TRANSITIONS[decision]
    if company.review_status not in allowed_from:
        raise InvalidTransitionError(
            f"Cannot {decision.lower()} a company that is {company.review_status}."
        )

    old_status = company.review_status
    company.review_status = new_status
    company.reviewed_by_user_id = admin.user_id
    company.reviewed_at = utc_now()
    company.review_note = note or None
    db.add(company)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="company",
        entity_id=company.company_id,
        action=f"review:{decision.lower()}",
        old_values={"review_status": old_status},
        new_values={"review_status": new_status, "review_note": company.review_note},
    )
    db.commit()
    db.refresh(company)
    return company


def decide_location(
    db: Session,
    admin: AppUser,
    location_id: uuid.UUID,
    decision: LocationDecision,
    note: str | None,
) -> SupplierLocation:
    location = db.get(SupplierLocation, location_id)
    if location is None:
        raise NotFoundError
    _ensure_no_conflict(db, admin, location.company_id)

    allowed_from, new_status = _LOCATION_TRANSITIONS[decision]
    if location.review_status not in allowed_from:
        raise InvalidTransitionError(
            f"Cannot {decision.lower()} a location that is {location.review_status}."
        )
    if decision == LocationDecision.APPROVE:
        company = get_company(db, location.company_id)
        if company.review_status != CompanyReviewStatus.APPROVED:
            raise InvalidTransitionError(
                "Only locations of approved companies can be marked demo-reviewed."
            )

    old_status = location.review_status
    location.review_status = new_status
    location.reviewed_by_user_id = admin.user_id
    location.reviewed_at = utc_now()
    location.review_note = note or None
    db.add(location)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="supplier_location",
        entity_id=location.location_id,
        action=f"review:{decision.lower()}",
        old_values={"review_status": old_status},
        new_values={"review_status": new_status, "review_note": location.review_note},
    )
    db.commit()
    db.refresh(location)
    return location


# --- Supplier locations (company side) ------------------------------------------------------


def add_location(
    db: Session, member: CompanyMember, data: LocationCreateRequest
) -> SupplierLocation:
    """Add a location for the member's company. Starts PENDING_REVIEW; company must be
    approved. The contact, if given, must be an active member of the same company."""
    company = get_company(db, member.company_id)
    if company.review_status != CompanyReviewStatus.APPROVED:
        raise CompanyNotApprovedError

    if data.contact_member_id is not None:
        contact = db.get(CompanyMember, data.contact_member_id)
        if (
            contact is None
            or contact.company_id != company.company_id
            or contact.membership_status != MembershipStatus.ACTIVE
        ):
            raise InvalidContactError

    location = SupplierLocation(
        company_id=company.company_id,
        name=data.name,
        address=data.address,
        area=data.area,
        contact_member_id=data.contact_member_id,
    )
    db.add(location)
    db.flush()
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="supplier_location",
        entity_id=location.location_id,
        action="created",
        new_values={"review_status": location.review_status, "name": location.name},
    )
    db.commit()
    db.refresh(location)
    return location
