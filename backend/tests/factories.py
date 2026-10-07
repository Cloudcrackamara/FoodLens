"""Minimal builders for valid rows. All values are obviously fictional."""

import uuid
from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.models import (
    AppUser,
    ChangeNotice,
    Company,
    CompanyMember,
    CredentialRecord,
    OrderLine,
    Product,
    ProductBatch,
    RegulatoryAgency,
    WholesaleOrder,
)
from app.models.enums import (
    ChangeType,
    CompanyType,
    CredentialStatus,
    FulfilmentMethod,
    MemberRole,
)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def make_user(db: Session, **overrides) -> AppUser:
    values = {
        "email": f"demo-{_suffix()}@example.test",
        "password_hash": "not-a-real-hash",
        "display_name": "Demo User",
    }
    user = AppUser(**(values | overrides))
    db.add(user)
    db.flush()
    return user


def make_company(db: Session, **overrides) -> Company:
    values = {
        "company_type": CompanyType.MANUFACTURER,
        "display_name": "Demo Harvest Foods",
        "contact_email": "contact@demo-harvest.example.test",
        "claimed_legal_name": "Demo Harvest Foods Ltd (fictional)",
    }
    company = Company(**(values | overrides))
    db.add(company)
    db.flush()
    return company


def make_member(db: Session, user: AppUser, company: Company, **overrides) -> CompanyMember:
    values = {"user_id": user.user_id, "company_id": company.company_id, "role": MemberRole.OWNER}
    member = CompanyMember(**(values | overrides))
    db.add(member)
    db.flush()
    return member


def make_product(db: Session, company: Company, **overrides) -> Product:
    values = {
        "company_id": company.company_id,
        "name": "Sample Palm Oil",
        "brand": "Demo Harvest",
        "category": "Oils",
        "product_code": f"DEMO-{_suffix()}",
        "manufacturer_name": "Demo Harvest Foods Ltd (fictional)",
    }
    product = Product(**(values | overrides))
    db.add(product)
    db.flush()
    return product


def make_batch(db: Session, product: Product, **overrides) -> ProductBatch:
    values = {"product_id": product.product_id, "batch_number": "DEMO-LOT-001"}
    batch = ProductBatch(**(values | overrides))
    db.add(batch)
    db.flush()
    return batch


def make_agency(db: Session, **overrides) -> RegulatoryAgency:
    values = {
        "name": "NAFDAC (simulated)",
        "scheme": f"Food product registration (demo) {_suffix()}",
    }
    agency = RegulatoryAgency(**(values | overrides))
    db.add(agency)
    db.flush()
    return agency


def make_credential(
    db: Session, product: Product, agency: RegulatoryAgency, **overrides
) -> CredentialRecord:
    values = {
        "product_id": product.product_id,
        "agency_id": agency.agency_id,
        "reference_number": f"DEMO-NAFDAC-{_suffix()}",
        "status": CredentialStatus.ACTIVE,
        "provenance": "Seeded fictional record for the FoodLens capstone demo",
        "checked_on": date(2026, 10, 1),
    }
    credential = CredentialRecord(**(values | overrides))
    db.add(credential)
    db.flush()
    return credential


def make_notice(db: Session, company: Company, user: AppUser, **targets) -> ChangeNotice:
    notice = ChangeNotice(
        company_id=company.company_id,
        submitted_by_user_id=user.user_id,
        change_type=ChangeType.PACKAGING,
        reason="New packaging design",
        **targets,
    )
    db.add(notice)
    db.flush()
    return notice


def make_order(
    db: Session, buyer: Company, seller: Company, user: AppUser, **overrides
) -> WholesaleOrder:
    values = {
        "buyer_company_id": buyer.company_id,
        "seller_company_id": seller.company_id,
        "created_by_user_id": user.user_id,
        "fulfilment_method": FulfilmentMethod.PICKUP,
    }
    order = WholesaleOrder(**(values | overrides))
    db.add(order)
    db.flush()
    return order


def make_line(db: Session, order: WholesaleOrder, product: Product, **overrides) -> OrderLine:
    values = {
        "order_id": order.order_id,
        "product_id": product.product_id,
        "quantity": Decimal("10"),
        "unit": "carton",
    }
    line = OrderLine(**(values | overrides))
    db.add(line)
    db.flush()
    return line
