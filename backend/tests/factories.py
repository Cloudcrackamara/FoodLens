"""Minimal builders for valid rows. All values are obviously fictional."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.models import (
    AppUser,
    Area,
    BatchAllocation,
    Carton,
    ChangeNotice,
    Company,
    CompanyMember,
    LifecycleEvent,
    OrderLine,
    PosPartner,
    Product,
    ProductBatch,
    ProductUnit,
    WholesaleOrder,
)
from app.models.enums import (
    ChangeType,
    EventSource,
    FulfilmentMethod,
    LifecycleEventType,
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
        "is_manufacturer": True,
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


# --- Unit identity ---------------------------------------------------------------------------


def token_hash() -> str:
    """A random sha256 hex, standing in for the hash of a normalised QR token."""
    return hashlib.sha256(secrets.token_bytes(16)).hexdigest()


def area(db: Session, city: str = "Lagos") -> Area:
    """A seeded reference area (migration 0006)."""
    return db.exec(select(Area).where(Area.city == city)).one()


def make_carton(db: Session, batch: ProductBatch, manufacturer: Company, **overrides) -> Carton:
    values = {
        "batch_id": batch.batch_id,
        "manufacturer_id": manufacturer.company_id,
        "carton_ref": f"C{_suffix()[:4].upper()}",
        "qr_token_hash": token_hash(),
    }
    carton = Carton(**(values | overrides))
    db.add(carton)
    db.flush()
    return carton


def make_unit(db: Session, batch: ProductBatch, **overrides) -> ProductUnit:
    product = db.get(Product, batch.product_id)
    values = {
        "batch_id": batch.batch_id,
        "product_id": product.product_id,
        "manufacturer_id": product.company_id,
        "qr_token_hash": token_hash(),
    }
    unit = ProductUnit(**(values | overrides))
    db.add(unit)
    db.flush()
    return unit


def make_event(db: Session, **overrides) -> LifecycleEvent:
    values = {
        "event_type": LifecycleEventType.ISSUED,
        "source": EventSource.MANUFACTURER,
        "occurred_at": datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    }
    event = LifecycleEvent(**(values | overrides))
    db.add(event)
    db.flush()
    return event


def make_allocation(
    db: Session, batch: ProductBatch, user: AppUser, **overrides
) -> BatchAllocation:
    values = {
        "batch_id": batch.batch_id,
        "destination_area_id": area(db).area_id,
        "quantity": 10,
        "created_by_user_id": user.user_id,
    }
    allocation = BatchAllocation(**(values | overrides))
    db.add(allocation)
    db.flush()
    return allocation


def make_pos_partner(db: Session, admin: AppUser, **overrides) -> PosPartner:
    values = {
        "name": "Demo Till Systems (fictional)",
        "signing_secret_encrypted": "not-a-real-ciphertext",
        "created_by_user_id": admin.user_id,
    }
    partner = PosPartner(**(values | overrides))
    db.add(partner)
    db.flush()
    return partner
