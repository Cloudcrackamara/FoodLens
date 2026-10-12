"""Fictional demo dataset: simulated NAFDAC/SON register, catalogue, and supplier locations.

Every name is invented and labelled "(fictional)"; every number starts with DEMO-; every agency
is "(simulated)"; every register record has data_mode DEMO. Dates are set relative to the
seeding day so each lookup result stays reproducible. SEED_CASES lists one lookup per result and
is used by the tests and the README.

Seeding is idempotent: rows are found by natural key and not overwritten, except that a seeded
product without a registration number gets one (for databases seeded before D81).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import (
    AppUser,
    Company,
    CompanyMember,
    OrderBatchAllocation,
    OrderLine,
    Product,
    ProductBatch,
    RegulatorRegister,
    RegulatoryAgency,
    SupplierLocation,
    WholesaleOrder,
)
from app.models.base import utc_now
from app.models.enums import (
    CompanyReviewStatus,
    CompanyType,
    FulfilmentMethod,
    LookupResult,
    MemberRole,
    OrderStatus,
    ProductStatus,
    RegisterStatus,
    ReviewStatus,
)

SEED_NOTE = "Seeded fictional demo record"
REGISTER_PROVENANCE = (
    "Fictional record in the FoodLens simulated register for the capstone demo. "
    "Not from NAFDAC or SON."
)


@dataclass(frozen=True)
class SeedCase:
    description: str
    registration_number: str | None
    batch_number: str | None
    expected: LookupResult
    warnings: tuple[str, ...] = field(default_factory=tuple)


SEED_CASES: list[SeedCase] = [
    SeedCase("Active record, batch belongs to that product", "DEMO-NAFDAC-0001", "DEMO-LOT-101", LookupResult.REGISTERED_ACTIVE),
    SeedCase("Active record, number only", "DEMO-NAFDAC-0002", None, LookupResult.REGISTERED_ACTIVE),
    SeedCase("Scanned text with a label", "NAFDAC Reg No: demo-nafdac-0001", None, LookupResult.REGISTERED_ACTIVE),
    SeedCase("Lot number shared by two products, resolved by the number", "DEMO-NAFDAC-0002", "DEMO-LOT-001", LookupResult.REGISTERED_ACTIVE),
    SeedCase("Batch not in the FoodLens catalogue", "DEMO-NAFDAC-0001", "DEMO-LOT-999", LookupResult.REGISTERED_ACTIVE, ("BATCH_NOT_IN_CATALOGUE",)),
    SeedCase("Batch expiry date has passed", "DEMO-NAFDAC-0005", "DEMO-LOT-501", LookupResult.REGISTERED_ACTIVE, ("BATCH_EXPIRED",)),
    SeedCase("Number not in the simulated register", "DEMO-NAFDAC-9999", None, LookupResult.REGISTRATION_NOT_FOUND),
    SeedCase("Registration expired", "DEMO-NAFDAC-0003", "DEMO-LOT-301", LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE),
    SeedCase("SON registration inactive", "DEMO-MANCAP-0004", "DEMO-LOT-401", LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE),
    SeedCase("Batch belongs to a product with a different number", "DEMO-NAFDAC-0001", "DEMO-LOT-201", LookupResult.REGISTRATION_MISMATCH),
    SeedCase("Number registered to another product and company", "DEMO-NAFDAC-0009", "DEMO-LOT-601", LookupResult.REGISTRATION_MISMATCH),
    SeedCase("Nothing entered", None, None, LookupResult.INSUFFICIENT_OR_AMBIGUOUS),
    SeedCase("Batch number without a registration number", None, "DEMO-LOT-101", LookupResult.INSUFFICIENT_OR_AMBIGUOUS),
]  # fmt: skip


def _get_or_create(db: Session, model, lookup: dict, values: dict):
    row = db.exec(select(model).filter_by(**lookup)).first()
    if row is None:
        row = model(**lookup, **values)
        db.add(row)
        db.flush()
    return row


def _reviewed(status) -> dict:
    return {"review_status": status, "reviewed_at": utc_now(), "review_note": SEED_NOTE}


def seed_demo_data(db: Session, today: date | None = None) -> None:
    today = today or date.today()
    future = today + timedelta(days=400)
    past = today - timedelta(days=60)

    # --- Simulated register (the only source of registration status) ----------------------
    nafdac = _get_or_create(
        db,
        RegulatoryAgency,
        {"name": "NAFDAC (simulated)", "scheme": "Food product registration (demo)"},
        {},
    )
    son = _get_or_create(
        db,
        RegulatoryAgency,
        {
            "name": "SON MANCAP (simulated)",
            "scheme": "Mandatory Conformity Assessment Programme (demo)",
        },
        {},
    )

    def registered(agency: RegulatoryAgency, number: str, product_name: str, company_name: str,
                   expires: date, status=RegisterStatus.ACTIVE) -> None:  # fmt: skip
        _get_or_create(
            db,
            RegulatorRegister,
            {"registration_number": number},
            {
                "agency_id": agency.agency_id,
                "registered_product_name": product_name,
                "registered_company_name": company_name,
                "status": status,
                "expires_on": expires,
                "provenance": REGISTER_PROVENANCE,
                "last_checked_on": today,
            },
        )

    harvest_ltd = "Demo Harvest Foods (fictional) Ltd"
    registered(nafdac, "DEMO-NAFDAC-0001", "Sample Palm Oil", harvest_ltd, future)
    registered(nafdac, "DEMO-NAFDAC-0002", "Sample Groundnut Oil", harvest_ltd, future)
    registered(nafdac, "DEMO-NAFDAC-0003", "Sample Table Water",
               "Sample Springs Beverages (fictional) Ltd", past)  # fmt: skip
    registered(son, "DEMO-MANCAP-0004", "Sample Maize Flour",
               "Example Grain Mills (fictional) Ltd", future, RegisterStatus.INACTIVE)  # fmt: skip
    registered(nafdac, "DEMO-NAFDAC-0005", "Sample Tomato Paste", harvest_ltd, future)
    registered(nafdac, "DEMO-NAFDAC-0008", "Sample Plantain Chips",
               "Pending Demo Snacks (fictional) Ltd", future)  # fmt: skip
    # Registered to a company that is not in FoodLens; "Sample Honey" below copies the number.
    registered(nafdac, "DEMO-NAFDAC-0009", "Sample Chin Chin",
               "Northern Snacks (fictional) Ltd", future)  # fmt: skip

    # --- Companies ------------------------------------------------------------------------
    def company(identifier: str, name: str, status=CompanyReviewStatus.APPROVED) -> Company:
        return _get_or_create(
            db,
            Company,
            {"claimed_business_identifier": identifier},
            {
                "company_type": CompanyType.MANUFACTURER,
                "display_name": name,
                "contact_email": f"contact@{identifier.lower()}.example",
                "claimed_legal_name": f"{name} Ltd",
                "claimed_address": "1 Example Street, Demo Industrial Estate (fictional)",
                **_reviewed(status),
            },
        )

    harvest = company("DEMO-RC-0001", "Demo Harvest Foods (fictional)")
    springs = company("DEMO-RC-0002", "Sample Springs Beverages (fictional)")
    mills = company("DEMO-RC-0003", "Example Grain Mills (fictional)")
    pending = company(
        "DEMO-RC-0004", "Pending Demo Snacks (fictional)", CompanyReviewStatus.PENDING_REVIEW
    )

    # --- Catalogue: products carry the number printed on the pack -------------------------
    def product(company_row: Company, code: str, name: str, category: str, size: str,
                registration_number: str | None,
                status=ProductStatus.PUBLISHED) -> Product:  # fmt: skip
        row = _get_or_create(
            db,
            Product,
            {"product_code": code},
            {
                "company_id": company_row.company_id,
                "name": name,
                "brand": company_row.display_name.replace(" (fictional)", ""),
                "category": category,
                "package_size": size,
                "manufacturer_name": company_row.claimed_legal_name,
                "registration_number": registration_number,
                "status": status,
                "reviewed_at": utc_now(),
                "review_note": SEED_NOTE,
            },
        )
        if row.registration_number is None and registration_number is not None:
            row.registration_number = registration_number
            db.add(row)
        return row

    palm_oil = product(
        harvest, "DEMO-PC-0001", "Sample Palm Oil", "Oils", "1 L", "DEMO-NAFDAC-0001"
    )
    groundnut_oil = product(
        harvest, "DEMO-PC-0002", "Sample Groundnut Oil", "Oils", "1 L", "DEMO-NAFDAC-0002"
    )
    water = product(
        springs, "DEMO-PC-0003", "Sample Table Water", "Beverages", "75 cl", "DEMO-NAFDAC-0003"
    )
    flour = product(
        mills, "DEMO-PC-0004", "Sample Maize Flour", "Flour", "2 kg", "DEMO-MANCAP-0004"
    )
    paste = product(
        harvest, "DEMO-PC-0005", "Sample Tomato Paste", "Canned foods", "400 g", "DEMO-NAFDAC-0005"
    )
    honey = product(harvest, "DEMO-PC-0006", "Sample Honey", "Spreads", "500 g", "DEMO-NAFDAC-0009")
    draft = product(mills, "DEMO-PC-0007", "Sample Semolina (draft)", "Flour", "1 kg", None,
                    ProductStatus.DRAFT)  # fmt: skip
    snack = product(
        pending, "DEMO-PC-0008", "Sample Plantain Chips", "Snacks", "100 g", "DEMO-NAFDAC-0008"
    )

    def batch(product_row: Product, number: str, expiry: date,
              status=ReviewStatus.APPROVED) -> ProductBatch:  # fmt: skip
        return _get_or_create(
            db,
            ProductBatch,
            {"product_id": product_row.product_id, "batch_number": number},
            {
                "production_date": expiry - timedelta(days=540),
                "expiry_date": expiry,
                **_reviewed(status),
            },
        )

    batch(palm_oil, "DEMO-LOT-101", future)
    batch(palm_oil, "DEMO-LOT-102", future, ReviewStatus.PENDING_REVIEW)
    batch(palm_oil, "DEMO-LOT-001", future)  # lot number shared with groundnut oil
    batch(groundnut_oil, "DEMO-LOT-201", future)
    batch(groundnut_oil, "DEMO-LOT-001", future)
    batch(water, "DEMO-LOT-301", future)
    batch(flour, "DEMO-LOT-401", future)
    batch(paste, "DEMO-LOT-501", past)
    batch(honey, "DEMO-LOT-601", future)
    batch(draft, "DEMO-LOT-701", future)
    batch(snack, "DEMO-LOT-801", future)

    # --- Supplier directory: only approved locations of approved companies are listed -----
    def location(company_row: Company, name: str, address: str, area: str,
                 status=ReviewStatus.APPROVED) -> None:  # fmt: skip
        _get_or_create(
            db,
            SupplierLocation,
            {"company_id": company_row.company_id, "name": name},
            {"address": address, "area": area, **_reviewed(status)},
        )

    location(harvest, "Demo Harvest Ikeja depot (fictional)", "12 Sample Road", "Ikeja, Lagos")
    location(harvest, "Demo Harvest Ibadan warehouse (fictional)", "4 Example Close", "Ibadan, Oyo")
    location(springs, "Sample Springs Kano depot (fictional)", "8 Demo Avenue", "Kano")
    location(mills, "Example Grain Mills Aba yard (fictional)", "3 Placeholder Lane", "Aba, Abia",
             ReviewStatus.PENDING_REVIEW)  # fmt: skip
    location(pending, "Pending Demo Snacks store (fictional)", "9 Test Street", "Abuja",
             ReviewStatus.PENDING_REVIEW)  # fmt: skip

    db.commit()


# --- Demo wholesale orders (D101) -------------------------------------------------------------

DEMO_BUYER_EMAIL = "buyer@demo.foodlens.invalid"
DEMO_SELLER_EMAIL = "seller@demo.foodlens.invalid"
# Not a bcrypt hash, so no password matches it: the account cannot sign in.
UNUSABLE_PASSWORD_HASH = "!login-disabled-set-SEED_DEMO_PASSWORD"


def _demo_owner(
    db: Session, email: str, name: str, company: Company, password: str | None
) -> AppUser:
    """Owner account for a demo company. Can sign in only when SEED_DEMO_PASSWORD is set."""
    user = db.exec(select(AppUser).where(AppUser.email == email)).first()
    if user is None:
        user = AppUser(email=email, display_name=name, password_hash=UNUSABLE_PASSWORD_HASH)
    if password:
        user.password_hash = hash_password(password)
    db.add(user)
    db.flush()
    _get_or_create(
        db,
        CompanyMember,
        {"user_id": user.user_id},
        {
            "company_id": company.company_id,
            "role": MemberRole.OWNER,
            "is_public_contact": True,
            "public_title": "Owner",
            "public_email": company.contact_email,
        },
    )
    return user


def seed_demo_orders(db: Session, password: str | None = None) -> None:
    """A demo wholesaler, owner accounts for it and Demo Harvest Foods, and one order in each
    status. Requires seed_demo_data first. Idempotent (orders are found by their buyer note)."""
    harvest = db.exec(
        select(Company).where(Company.claimed_business_identifier == "DEMO-RC-0001")
    ).one()
    market = _get_or_create(
        db,
        Company,
        {"claimed_business_identifier": "DEMO-RC-0005"},
        {
            "company_type": CompanyType.WHOLESALER,
            "display_name": "Demo Market Traders (fictional)",
            "contact_email": "contact@demo-rc-0005.example",
            "claimed_legal_name": "Demo Market Traders (fictional) Ltd",
            "claimed_address": "Stall 7, Sample Market (fictional)",
            **_reviewed(CompanyReviewStatus.APPROVED),
        },
    )
    buyer = _demo_owner(db, DEMO_BUYER_EMAIL, "Demo Buyer", market, password)
    _demo_owner(db, DEMO_SELLER_EMAIL, "Demo Seller", harvest, password)

    products = {
        p.product_code: p
        for p in db.exec(select(Product).where(Product.company_id == harvest.company_id))
    }
    depot = db.exec(
        select(SupplierLocation)
        .where(
            SupplierLocation.company_id == harvest.company_id,
            SupplierLocation.review_status == ReviewStatus.APPROVED,
        )
        .order_by(SupplierLocation.name)
    ).first()

    def order(note: str, status: OrderStatus, lines: list[tuple[str, str, str]], *,
              delivery: str | None = None, seller_note: str | None = None,
              batches: dict[str, str] | None = None) -> None:  # fmt: skip
        existing = db.exec(
            select(WholesaleOrder).where(
                WholesaleOrder.buyer_company_id == market.company_id,
                WholesaleOrder.buyer_note == note,
            )
        ).first()
        if existing is not None:
            return
        row = WholesaleOrder(
            buyer_company_id=market.company_id,
            seller_company_id=harvest.company_id,
            created_by_user_id=buyer.user_id,
            fulfilment_method=FulfilmentMethod.DELIVERY if delivery else FulfilmentMethod.PICKUP,
            pickup_location_id=None if delivery else depot.location_id,
            delivery_details=delivery,
            status=status,
            buyer_note=note,
            seller_note=seller_note,
        )
        db.add(row)
        db.flush()
        for code, quantity, unit in lines:
            line = OrderLine(
                order_id=row.order_id,
                product_id=products[code].product_id,
                quantity=Decimal(quantity),
                unit=unit,
            )
            db.add(line)
            db.flush()
            batch_number = (batches or {}).get(code)
            if batch_number:
                batch_row = db.exec(
                    select(ProductBatch).where(
                        ProductBatch.product_id == products[code].product_id,
                        ProductBatch.batch_number == batch_number,
                    )
                ).one()
                db.add(OrderBatchAllocation(line_id=line.line_id, batch_id=batch_row.batch_id))

    order(
        "Demo order: weekly palm oil restock",
        OrderStatus.REQUESTED,
        [("DEMO-PC-0001", "20", "carton")],
    )
    order(
        "Demo order: groundnut oil for the shop",
        OrderStatus.ACCEPTED,
        [("DEMO-PC-0002", "10", "carton")],
        delivery="Stall 7, Sample Market (fictional)",
        seller_note="Accepted. Delivery on Friday morning.",
    )
    order(
        "Demo order: tomato paste",
        OrderStatus.DECLINED,
        [("DEMO-PC-0005", "50", "carton")],
        seller_note="Not available this month.",
    )
    order("Demo order: palm oil and honey", OrderStatus.FULFILLED,
          [("DEMO-PC-0001", "5", "carton"), ("DEMO-PC-0006", "12", "jar")],
          batches={"DEMO-PC-0001": "DEMO-LOT-101"})  # fmt: skip
    db.commit()
