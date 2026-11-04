"""Fictional demo dataset: companies, catalogue, partner locations, demo orders and the
unit-identity scenario (D145).

Every name is invented and labelled "(fictional)"; every reference number starts with DEMO-.
NAFDAC numbers are printed information only and are never checked (D107). Dates are set
relative to the seeding day.

Seeding is idempotent: rows are found by natural key and not overwritten, except that a seeded
product without a registration number gets one (for databases seeded before D81).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AppUser,
    Company,
    CompanyMember,
    OrderBatchAllocation,
    OrderLine,
    PosPartner,
    PosPartnerRetailer,
    PosTill,
    Product,
    ProductBatch,
    ProductUnit,
    SupplierLocation,
    WholesaleOrder,
)
from app.models.base import utc_now
from app.models.enums import (
    CompanyReviewStatus,
    FulfilmentMethod,
    IdentifierType,
    LifecycleEventType,
    MemberRole,
    OrderStatus,
    ProductStatus,
    ReviewStatus,
)
from app.schemas.pos import PosRefundRequest, PosSaleRequest
from app.services import (
    allocations,
    check,
    companies,
    identity,
    lifecycle,
    pos,
    pos_auth,
    risk,
    units,
)
from app.services.demo_pos import DEMO_PARTNER_NAME

SEED_NOTE = "Seeded fictional demo record"


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

    # --- Companies ------------------------------------------------------------------------
    def company(identifier: str, name: str, status=CompanyReviewStatus.APPROVED) -> Company:
        return _get_or_create(
            db,
            Company,
            {"claimed_business_identifier": identifier},
            {
                "is_manufacturer": True,
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
                "size": size,
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

    # --- Partner directory: only approved locations of approved companies are listed ------
    def location(company_row: Company, name: str, address: str, area: str,
                 status=ReviewStatus.APPROVED) -> None:  # fmt: skip
        area_row = companies.area_from_text(db, area)
        _get_or_create(
            db,
            SupplierLocation,
            {"company_id": company_row.company_id, "name": name},
            {
                "address": address,
                "area": area,
                "area_id": area_row.area_id if area_row else None,
                **_reviewed(status),
            },
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
    """A demo distributor, owner accounts for it and Demo Harvest Foods, and one order in each
    status. Requires seed_demo_data first. Idempotent (orders are found by their buyer note)."""
    harvest = db.exec(
        select(Company).where(Company.claimed_business_identifier == "DEMO-RC-0001")
    ).one()
    market = _get_or_create(
        db,
        Company,
        {"claimed_business_identifier": "DEMO-RC-0005"},
        {
            "is_distributor": True,
            "display_name": "Demo Market Traders (fictional)",
            "contact_email": "contact@demo-rc-0005.example",
            "claimed_legal_name": "Demo Market Traders (fictional) Ltd",
            "claimed_address": "Stall 7, Sample Market (fictional)",
            **_reviewed(CompanyReviewStatus.APPROVED),
        },
    )
    # A reviewed location gives the distributor's merchant events their area (D150).
    _get_or_create(
        db,
        SupplierLocation,
        {"company_id": market.company_id, "name": "Demo Market Traders stall (fictional)"},
        {
            "address": "Stall 7, Sample Market",
            "area": "Lagos",
            "area_id": companies.area_from_text(db, "Lagos").area_id,
            **_reviewed(ReviewStatus.APPROVED),
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


# --- Demo POS partner and shop (D123, Phase 5) -----------------------------------------------

DEMO_SHOP_EMAIL = "shop@demo.foodlens.invalid"
DEMO_TILL_REF = "DEMO-TILL-1"


def seed_demo_pos(
    db: Session, settings: Settings, admin: AppUser | None, password: str | None = None
) -> str:
    """A demo retailer with an owner account, and the demo POS partner linked to it with one
    till. The partner is created only when POS_SECRET_KEY is set and an admin account exists. Its
    signing secret is random and stored encrypted; no API key is issued (the demo till skips the
    key step, D151). Returns a line for the seed output."""
    shop = _get_or_create(
        db,
        Company,
        {"claimed_business_identifier": "DEMO-RC-0006"},
        {
            "is_manufacturer": False,
            "is_retailer": True,
            "display_name": "Demo Corner Shop (fictional)",
            "contact_email": "contact@demo-rc-0006.example",
            "claimed_legal_name": "Demo Corner Shop (fictional) Ltd",
            "claimed_address": "5 Sample Close, Ikeja (fictional)",
            **_reviewed(CompanyReviewStatus.APPROVED),
        },
    )
    location = _get_or_create(
        db,
        SupplierLocation,
        {"company_id": shop.company_id, "name": "Demo Corner Shop, Ikeja (fictional)"},
        {
            "address": "5 Sample Close",
            "area": "Lagos",
            "area_id": companies.area_from_text(db, "Lagos").area_id,
            **_reviewed(ReviewStatus.APPROVED),
        },
    )
    _demo_owner(db, DEMO_SHOP_EMAIL, "Demo Shopkeeper", shop, password)
    db.commit()

    if not settings.pos_secret_key:
        return "Demo POS partner skipped: set POS_SECRET_KEY in backend/.env."
    # The partner records which admin created it; any existing admin will do.
    admin = admin or db.exec(select(AppUser).where(AppUser.is_admin.is_(True))).first()
    if admin is None:
        return "Demo POS partner skipped: it needs an admin account (SEED_ADMIN_EMAIL)."
    partner = db.exec(select(PosPartner).where(PosPartner.name == DEMO_PARTNER_NAME)).first()
    if partner is None:
        partner = PosPartner(
            name=DEMO_PARTNER_NAME,
            signing_secret_encrypted=pos_auth.encrypt_secret(
                settings, pos_auth.new_signing_secret()
            ),
            created_by_user_id=admin.user_id,
        )
    else:
        try:
            pos_auth.decrypt_secret(settings, partner)
        except pos_auth.PosError:
            # POS_SECRET_KEY changed since the last seed: give the demo partner a new secret.
            partner.signing_secret_encrypted = pos_auth.encrypt_secret(
                settings, pos_auth.new_signing_secret()
            )
    db.add(partner)
    db.flush()
    _get_or_create(
        db,
        PosPartnerRetailer,
        {"partner_id": partner.partner_id, "retailer_company_id": shop.company_id},
        {"created_by_user_id": admin.user_id},
    )
    _get_or_create(
        db,
        PosTill,
        {
            "partner_id": partner.partner_id,
            "retailer_company_id": shop.company_id,
            "till_ref": DEMO_TILL_REF,
        },
        {"location_id": location.location_id},
    )
    db.commit()
    return f"Demo POS partner ready: {DEMO_PARTNER_NAME}, till {DEMO_TILL_REF} at {DEMO_SHOP_EMAIL}"


# --- Unit-identity scenario (D145, Phase 8) ---------------------------------------------------
#
# Built only through the services, so every alert below comes from the risk rules. Scenario codes
# are fixed so the README can print them (the D111 exception to random tokens). They are hashed
# like any other code. History is backdated from the seeding moment, so the seeded "just sold"
# pack keeps that result for JUST_SOLD_WINDOW_HOURS minus 30 minutes after a seed.

DEMO_KANO_EMAIL = "kano@demo.foodlens.invalid"
SCENARIO_BATCH = "DEMO-LOT-110"
EXPIRED_BATCH = "DEMO-LOT-501"
TEST_BATCH = "DEMO-LOT-TEST-UNRELEASED"
LIVE_BATCH = "DEMO-LOT-201"  # left without codes: the walkthrough generates them live

_CODE_PREFIX = "7DEMABCDEFGHJKMNPQRSTV"


def demo_code(tail: str) -> str:
    """A fixed 26-character demo code ending in the given four Crockford characters."""
    return f"{_CODE_PREFIX}{tail}"


@dataclass(frozen=True)
class DemoCodes:
    # Carton C001 (Lagos): received by the distributor, transferred to Demo Corner Shop.
    live_pack: str = demo_code("1001")  # never sold: the walkthrough sells this one
    rehearsal_pack: str = demo_code("1002")  # never sold: a second run without a reset
    pos_rescan: str = demo_code("1003")  # POS sale then buyer rescan: just sold, no alert
    sold_lagos_kano: str = demo_code("1004")  # sold in Lagos, checked in Kano 3 hours on: alert
    refund_resale: str = demo_code("1005")  # refund then resale: no alert
    never_sold: str = demo_code("1006")  # in stock, never checked
    carton_lagos: str = demo_code("C001")
    carton_kano: str = demo_code("C002")
    # Loose pack individually allocated to the Kano retailer and received there.
    kano_loose: str = demo_code("K001")
    # Checked in Abuja, which is allocated only 3 packs: rule 9.
    abuja_over: str = demo_code("A001")
    voided: str = demo_code("V001")  # voided before release, then checked: rule 8
    expired: str = demo_code("E001")  # batch past its expiry date
    unreleased_checked: str = demo_code("T001")  # labelled test carton, checked: rule 6
    unreleased_unchecked: str = demo_code("T002")  # same carton, not checked by the seed
    carton_unreleased: str = demo_code("TC01")
    unrecognised: str = demo_code("X001")  # part of the invalid-code burst; never issued


DEMO_CODES = DemoCodes()

_LAGOS_PACKS = [demo_code(f"10{n:02d}") for n in range(1, 11)]
_KANO_PACKS = [demo_code(f"20{n:02d}") for n in range(1, 11)]
_KANO_LOOSE = [demo_code(f"K00{n}") for n in range(1, 5)]
_ABUJA_PACKS = [demo_code(f"A00{n}") for n in range(1, 6)]
_INVALID_BURST = [demo_code(f"X{n:03d}") for n in range(1, 21)]
ABUJA_ALLOCATED = 3


def _fixed_tokens(*tokens: str):
    return iter(tokens).__next__


def seed_demo_scenario(db: Session, settings: Settings, now: datetime | None = None) -> str:
    """The D145 cases, through the services. Requires seed_demo_data, seed_demo_orders and
    seed_demo_pos first. A second run changes nothing. Returns a line for the seed output."""
    if db.exec(
        select(ProductUnit).where(
            ProductUnit.qr_token_hash == identity.token_hash(DEMO_CODES.live_pack)
        )
    ).first():
        return "Demo scenario already seeded; `uv run python -m app.seed --reset` starts it again."
    partner = db.exec(select(PosPartner).where(PosPartner.name == DEMO_PARTNER_NAME)).first()
    if partner is None:
        return (
            "Demo scenario skipped: it needs the demo POS partner (POS_SECRET_KEY and "
            "SEED_ADMIN_EMAIL in backend/.env)."
        )
    now = now or datetime.now(UTC)
    thresholds = risk.Thresholds.from_settings(settings)

    def ago(**delta) -> datetime:
        return now - timedelta(**delta)

    def company_by_ref(reference: str) -> Company:
        return db.exec(
            select(Company).where(Company.claimed_business_identifier == reference)
        ).one()

    def member_of(company: Company) -> CompanyMember:
        return db.exec(
            select(CompanyMember).where(
                CompanyMember.company_id == company.company_id,
                CompanyMember.role == MemberRole.OWNER,
            )
        ).first()

    def area_id(city: str):
        return companies.area_from_text(db, city).area_id

    harvest = company_by_ref("DEMO-RC-0001")
    market = company_by_ref("DEMO-RC-0005")
    shop = company_by_ref("DEMO-RC-0006")
    kano_shop = _get_or_create(
        db,
        Company,
        {"claimed_business_identifier": "DEMO-RC-0007"},
        {
            "is_manufacturer": False,
            "is_retailer": True,
            "display_name": "Demo Kano Stores (fictional)",
            "contact_email": "contact@demo-rc-0007.example",
            "claimed_legal_name": "Demo Kano Stores (fictional) Ltd",
            "claimed_address": "2 Example Road, Kano (fictional)",
            **_reviewed(CompanyReviewStatus.APPROVED),
        },
    )
    _get_or_create(
        db,
        SupplierLocation,
        {"company_id": kano_shop.company_id, "name": "Demo Kano Stores (fictional)"},
        {
            "address": "2 Example Road",
            "area": "Kano",
            "area_id": area_id("Kano"),
            **_reviewed(ReviewStatus.APPROVED),
        },
    )
    _demo_owner(db, DEMO_KANO_EMAIL, "Demo Kano Shopkeeper", kano_shop, settings.seed_demo_password)
    db.commit()

    maker = member_of(harvest)
    market_member = member_of(market)
    shop_member = member_of(shop)
    kano_member = member_of(kano_shop)

    def new_batch(code: str, number: str) -> ProductBatch:
        product_row = db.exec(select(Product).where(Product.product_code == code)).one()
        expiry = now.date() + timedelta(days=400)
        row = _get_or_create(
            db,
            ProductBatch,
            {"product_id": product_row.product_id, "batch_number": number},
            {
                "production_date": expiry - timedelta(days=540),
                "expiry_date": expiry,
                **_reviewed(ReviewStatus.APPROVED),
            },
        )
        db.commit()
        return row

    def generate(
        batch_id, tokens: Iterable[str], per_carton: int | None, at: datetime, cartons=()
    ) -> None:
        tokens = list(tokens)
        units.generate(
            db,
            maker,
            batch_id,
            quantity=len(tokens),
            units_per_carton=per_carton,
            qr_size_mm=20,
            base_url=settings.public_base_url,
            token_factory=_fixed_tokens(*cartons, *tokens),
            occurred_at=at,
        )

    # --- The main batch: cartons split between Lagos and Kano, plus loose packs ---------------
    main_id = new_batch("DEMO-PC-0001", SCENARIO_BATCH).batch_id
    generate(
        main_id,
        [*_LAGOS_PACKS, *_KANO_PACKS],
        10,
        ago(days=10),
        cartons=(DEMO_CODES.carton_lagos, DEMO_CODES.carton_kano),
    )
    generate(main_id, [*_KANO_LOOSE, *_ABUJA_PACKS, DEMO_CODES.voided], None, ago(days=10))
    units.void(
        db,
        maker,
        main_id,
        reason="Demo: misprinted label (fictional)",
        tokens=[DEMO_CODES.voided],
        occurred_at=ago(days=10) + timedelta(hours=1),
    )
    units.release(db, maker, main_id, occurred_at=ago(days=9))

    for allocation in (
        allocations.AllocationInput(destination_area_id=area_id("Lagos"), carton_refs=["C001"]),
        allocations.AllocationInput(
            destination_area_id=area_id("Kano"),
            destination_company_id=kano_shop.company_id,
            carton_refs=["C002"],
        ),
        allocations.AllocationInput(
            destination_area_id=area_id("Kano"),
            destination_company_id=kano_shop.company_id,
            unit_codes=_KANO_LOOSE,
        ),
        allocations.AllocationInput(destination_area_id=area_id("Abuja"), quantity=ABUJA_ALLOCATED),
    ):
        allocations.create(db, maker, main_id, allocation)

    # --- Stock moves: distributor to the Lagos shop; the Kano shop receives its own -----------
    received = LifecycleEventType.RECEIVED
    lifecycle.record_merchant_event(
        db, market_member, DEMO_CODES.carton_lagos, received, occurred_at=ago(days=8)
    )
    lifecycle.record_merchant_event(
        db,
        market_member,
        DEMO_CODES.carton_lagos,
        LifecycleEventType.TRANSFERRED,
        to_company_id=shop.company_id,
        occurred_at=ago(days=7),
    )
    lifecycle.record_merchant_event(
        db, shop_member, DEMO_CODES.carton_lagos, received, occurred_at=ago(days=6)
    )
    lifecycle.record_merchant_event(
        db, kano_member, DEMO_CODES.carton_kano, received, occurred_at=ago(days=6)
    )
    for code in _KANO_LOOSE:
        lifecycle.record_merchant_event(db, kano_member, code, received, occurred_at=ago(days=5))

    # --- POS cases, through the same service a signed till call reaches ------------------------
    def pos_sale(code: str, at: datetime, reference: str) -> None:
        pos.record(
            db,
            settings,
            partner,
            PosSaleRequest(
                retailer_id=shop.company_id,
                till_id=DEMO_TILL_REF,
                transaction_id=f"DEMO-TXN-{reference}",
                payment_reference=f"DEMO-PAY-{reference}",
                occurred_at=at,
                units=[code],
            ),
            LifecycleEventType.SOLD,
            at,
        )

    def pos_refund(code: str, at: datetime, reference: str) -> None:
        pos.record(
            db,
            settings,
            partner,
            PosRefundRequest(
                retailer_id=shop.company_id,
                till_id=DEMO_TILL_REF,
                transaction_id=f"DEMO-RFD-{reference}",
                occurred_at=at,
                units=[code],
            ),
            LifecycleEventType.RETURNED,
            at,
        )

    def consumer_check(code: str, city: str, at: datetime) -> None:
        check.check_code(
            db,
            code,
            IdentifierType.QR,
            area=companies.area_from_text(db, city),
            now=at,
            window_hours=settings.just_sold_window_hours,
            thresholds=thresholds,
        )

    # A POS sale, then the buyer rescans in the same city: just sold, no alert.
    pos_sale(DEMO_CODES.pos_rescan, ago(minutes=30), "0001")
    consumer_check(DEMO_CODES.pos_rescan, "Lagos", ago(minutes=25))

    # Sold in Lagos, then checked in Kano 3 hours later: rule 2.
    pos_sale(DEMO_CODES.sold_lagos_kano, ago(hours=4), "0002")
    consumer_check(DEMO_CODES.sold_lagos_kano, "Kano", ago(hours=1))

    # A refund, then a resale: the undone sale is ignored, so no alert.
    pos_sale(DEMO_CODES.refund_resale, ago(days=3), "0003")
    pos_refund(DEMO_CODES.refund_resale, ago(days=2), "0003")
    pos_sale(DEMO_CODES.refund_resale, ago(hours=2), "0004")
    consumer_check(DEMO_CODES.refund_resale, "Lagos", ago(hours=1, minutes=45))

    # One area exceeding its allocation: rule 9, on the dashboard only.
    for index, code in enumerate(_ABUJA_PACKS):
        consumer_check(code, "Abuja", ago(days=3) + timedelta(hours=index))

    # A voided code in use: rule 8.
    consumer_check(DEMO_CODES.voided, "Ibadan", ago(days=1))

    # A burst of unrecognised codes from one city: rule 4, admin only.
    for index, code in enumerate(_INVALID_BURST):
        consumer_check(code, "Port Harcourt", ago(minutes=40) + timedelta(seconds=15 * index))

    # --- An expired batch: a warning on the recognised result; no recalls (D155) --------------
    expired_id = db.exec(
        select(ProductBatch.batch_id)
        .join(Product, Product.product_id == ProductBatch.product_id)
        .where(Product.product_code == "DEMO-PC-0005", ProductBatch.batch_number == EXPIRED_BATCH)
    ).one()
    generate(expired_id, [DEMO_CODES.expired, demo_code("E002")], None, ago(days=20))
    units.release(db, maker, expired_id, occurred_at=ago(days=19))
    consumer_check(DEMO_CODES.expired, "Lagos", ago(days=2))

    # --- The one deliberately unreleased carton, labelled as a test case in its batch number ---
    generate(
        new_batch("DEMO-PC-0006", TEST_BATCH).batch_id,
        [DEMO_CODES.unreleased_checked, DEMO_CODES.unreleased_unchecked, demo_code("T003")],
        3,
        ago(days=4),
        cartons=(DEMO_CODES.carton_unreleased,),
    )
    consumer_check(DEMO_CODES.unreleased_checked, "Lagos", ago(hours=6))

    return f"Demo scenario ready: codes and logins are in README.md (batch {SCENARIO_BATCH})."
