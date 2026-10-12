"""Public supplier directory and supplier pages: approved companies with at least one
demo-reviewed location (D58, D100).

Shows only reviewed locations, opted-in public contacts, and published products with their
registration result from the simulated register. Never shows claimed fields, review notes,
pending or rejected data, or login emails, and never says a product is "safe".
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlmodel import Session, select

from app.models import AppUser, Company, CompanyMember, Product, SupplierLocation
from app.models.enums import CompanyReviewStatus, MembershipStatus, ProductStatus, ReviewStatus
from app.schemas.company import SupplierContactRead, SupplierLocationRead, SupplierRead
from app.schemas.lookup import RegisterRecordStatus
from app.schemas.order import RegistrationResult, SupplierDetailRead, SupplierProductRead
from app.services import register

SUPPLIER_DISCLAIMER = (
    "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. Registration results come from a simulated, "
    "fictional register held by FoodLens, not NAFDAC's or SON's own system. They are not a "
    "laboratory or food-safety test."
)

REGISTRATION_LABELS = {
    RegistrationResult.ACTIVE_IN_DEMO_REGISTER: "Active in the simulated register (demo data)",
    RegistrationResult.EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER: (
        "Expired or inactive in the simulated register (demo data)"
    ),
    RegistrationResult.REGISTERED_TO_ANOTHER_PRODUCT: (
        "Number belongs to a different product or company in the simulated register (demo data)"
    ),
    RegistrationResult.NOT_FOUND_IN_DEMO_REGISTER: (
        "Not found in the simulated register (demo data)"
    ),
    RegistrationResult.NO_NUMBER_GIVEN: "No registration number given by the company",
}


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
            company_type=company.company_type,
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


def registration_result(
    db: Session, product: Product, company: Company, today: date
) -> tuple[RegistrationResult, str | None]:
    """Result for the number the company printed, from the simulated register only (D80).
    Names are compared like lookups do, ignoring capitals and spaces (D83)."""
    if not product.registration_number:
        return RegistrationResult.NO_NUMBER_GIVEN, None
    found = register.find_record(db, product.registration_number)
    if found is None:
        return RegistrationResult.NOT_FOUND_IN_DEMO_REGISTER, None
    record, agency = found
    names_match = register.normalize_name(product.name) == register.normalize_name(
        record.registered_product_name
    ) and register.normalize_name(company.claimed_legal_name) == register.normalize_name(
        record.registered_company_name
    )
    if register.record_status(record, today) != RegisterRecordStatus.ACTIVE_IN_DEMO_REGISTER:
        result = RegistrationResult.EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER
    elif not names_match:
        result = RegistrationResult.REGISTERED_TO_ANOTHER_PRODUCT
    else:
        result = RegistrationResult.ACTIVE_IN_DEMO_REGISTER
    return result, register.register_label(agency)


def supplier_detail(
    db: Session, company_id: uuid.UUID, today: date | None = None
) -> SupplierDetailRead | None:
    suppliers = _suppliers(db, _listed_rows(db, company_id))
    if not suppliers:
        return None
    today = today or date.today()
    company = db.get(Company, company_id)
    products = []
    for product in published_products(db, company_id):
        result, register_name = registration_result(db, product, company, today)
        products.append(
            SupplierProductRead(
                product_id=product.product_id,
                name=product.name,
                brand=product.brand,
                category=product.category,
                package_size=product.package_size,
                registration_number=product.registration_number,
                registration_result=result,
                registration_label=REGISTRATION_LABELS[result],
                register_name=register_name,
            )
        )
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
