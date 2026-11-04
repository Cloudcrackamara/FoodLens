"""Public partner directory and partner pages: approved companies with at least one
demo-reviewed location (D58, D100, D127).

Shows only reviewed locations, opted-in public contacts, and published products. The NAFDAC
number is shown as printed, as information only: FoodLens never checks it (D104, D107). Never
shows claimed fields, review notes, pending or rejected data, or login emails.
"""

import uuid
from collections import defaultdict

from sqlmodel import Session, select

from app.models import AppUser, Company, CompanyMember, Product, SupplierLocation
from app.models.enums import CompanyReviewStatus, MembershipStatus, ProductStatus, ReviewStatus
from app.schemas.company import SupplierContactRead, SupplierLocationRead, SupplierRead
from app.schemas.order import SupplierDetailRead, SupplierProductRead

SUPPLIER_DISCLAIMER = (
    "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. Company profiles are reviewed for the "
    "FoodLens demonstration database only. NAFDAC numbers are shown as the company printed "
    "them; FoodLens does not check them."
)


def _listed_rows(db: Session, company_id: uuid.UUID | None = None):
    statement = (
        select(Company, SupplierLocation)
        .join(SupplierLocation, SupplierLocation.company_id == Company.company_id)
        .where(
            Company.review_status == CompanyReviewStatus.APPROVED,
            SupplierLocation.review_status == ReviewStatus.APPROVED,
        )
        .order_by(Company.display_name, SupplierLocation.name)
    )
    if company_id is not None:
        statement = statement.where(Company.company_id == company_id)
    return db.exec(statement).all()


def is_listed(db: Session, company_id: uuid.UUID) -> bool:
    """Approved company with at least one reviewed location: the only kind that can sell."""
    return bool(_listed_rows(db, company_id))


def _suppliers(db: Session, rows) -> list[SupplierRead]:
    companies: dict = {}
    locations: dict = defaultdict(list)
    for company, location in rows:
        companies[company.company_id] = company
        locations[company.company_id].append(
            SupplierLocationRead(
                location_id=location.location_id,
                name=location.name,
                address=location.address,
                area=location.area,
                reviewed_at=location.reviewed_at,
            )
        )
    contacts = _public_contacts(db, list(companies))
    return [
        SupplierRead(
            company_id=company.company_id,
            display_name=company.display_name,
            is_manufacturer=company.is_manufacturer,
            is_distributor=company.is_distributor,
            is_retailer=company.is_retailer,
            contact_email=company.contact_email,
            contact_phone=company.contact_phone,
            reviewed_at=company.reviewed_at,
            locations=locations[company.company_id],
            contacts=contacts[company.company_id],
        )
        for company in companies.values()
    ]


def published_products(db: Session, company_id: uuid.UUID) -> list[Product]:
    return list(
        db.exec(
            select(Product)
            .where(Product.company_id == company_id, Product.status == ProductStatus.PUBLISHED)
            .order_by(Product.name)
        ).all()
    )


def list_suppliers(db: Session, query: str | None = None) -> list[SupplierRead]:
    """Search matches the company name, a location name or area, or a published product name."""
    suppliers = _suppliers(db, _listed_rows(db))
    if not query or not query.strip():
        return suppliers
    needle = query.strip().lower()
    product_matches = {
        product.company_id
        for product in db.exec(
            select(Product).where(
                Product.status == ProductStatus.PUBLISHED,
                Product.company_id.in_([s.company_id for s in suppliers]),
            )
        ).all()
        if needle in product.name.lower() or needle in product.brand.lower()
    }
    return [
        s
        for s in suppliers
        if needle in s.display_name.lower()
        or s.company_id in product_matches
        or any(needle in loc.area.lower() or needle in loc.name.lower() for loc in s.locations)
    ]


def supplier_detail(db: Session, company_id: uuid.UUID) -> SupplierDetailRead | None:
    suppliers = _suppliers(db, _listed_rows(db, company_id))
    if not suppliers:
        return None
    products = [
        SupplierProductRead(
            product_id=product.product_id,
            name=product.name,
            brand=product.brand,
            category=product.category,
            size=product.size,
            registration_number=product.registration_number,
        )
        for product in published_products(db, company_id)
    ]
    return SupplierDetailRead(
        **suppliers[0].model_dump(), products=products, disclaimer=SUPPLIER_DISCLAIMER
    )


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
