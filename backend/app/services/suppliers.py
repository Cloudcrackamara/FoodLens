"""Public supplier directory: approved companies with at least one demo-reviewed location.

Shows only reviewed locations and opted-in public contacts. Never shows claimed fields,
review notes, pending or rejected data, or login emails.
"""

from collections import defaultdict

from sqlmodel import Session, select

from app.models import AppUser, Company, CompanyMember, SupplierLocation
from app.models.enums import CompanyReviewStatus, MembershipStatus, ReviewStatus
from app.schemas.company import SupplierContactRead, SupplierLocationRead, SupplierRead


def list_suppliers(db: Session, query: str | None = None) -> list[SupplierRead]:
    statement = (
        select(Company, SupplierLocation)
        .join(SupplierLocation, SupplierLocation.company_id == Company.company_id)
        .where(
            Company.review_status == CompanyReviewStatus.APPROVED,
            SupplierLocation.review_status == ReviewStatus.APPROVED,
        )
        .order_by(Company.display_name, SupplierLocation.name)
    )
    rows = db.exec(statement).all()

    companies: dict = {}
    locations: dict = defaultdict(list)
    for company, location in rows:
        companies[company.company_id] = company
        locations[company.company_id].append(
            SupplierLocationRead(
                name=location.name,
                address=location.address,
                area=location.area,
                reviewed_at=location.reviewed_at,
            )
        )

    contacts = _public_contacts(db, list(companies))

    suppliers = [
        SupplierRead(
            company_id=company.company_id,
            display_name=company.display_name,
            company_type=company.company_type,
            contact_email=company.contact_email,
            contact_phone=company.contact_phone,
            reviewed_at=company.reviewed_at,
            locations=locations[company.company_id],
            contacts=contacts[company.company_id],
        )
        for company in companies.values()
    ]
    if query:
        needle = query.strip().lower()
        suppliers = [
            s
            for s in suppliers
            if needle in s.display_name.lower()
            or any(needle in loc.area.lower() or needle in loc.name.lower() for loc in s.locations)
        ]
    return suppliers


def _public_contacts(db: Session, company_ids: list) -> dict:
    contacts: dict = defaultdict(list)
    if not company_ids:
        return contacts
    rows = db.exec(
        select(CompanyMember, AppUser)
        .join(AppUser, AppUser.user_id == CompanyMember.user_id)
        .where(
            CompanyMember.company_id.in_(company_ids),
            CompanyMember.is_public_contact.is_(True),
            CompanyMember.membership_status == MembershipStatus.ACTIVE,
            AppUser.is_active.is_(True),
        )
        .order_by(AppUser.display_name)
    ).all()
    for member, user in rows:
        contacts[member.company_id].append(
            SupplierContactRead(
                display_name=user.display_name,
                title=member.public_title,
                phone=member.public_phone,
                email=member.public_email,
            )
        )
    return contacts
