"""Database-level rules from docs/SCHEMA.md. Each test runs in a rolled-back transaction."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlmodel import Session, SQLModel, select

from alembic import command
from app.models import (
    AllocationCarton,
    AllocationUnit,
    Area,
    ConsumerReport,
    LifecycleEvent,
    NoticeAttachment,
    OrderBatchAllocation,
    PosPartnerKey,
    PosPartnerRetailer,
    PosTill,
    ProductAnnouncement,
    RateLimitDaily,
    RiskAlert,
    ScanEvent,
    SupplierLocation,
)
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    AnnouncementKind,
    AttachmentMimeType,
    ChangeNoticeStatus,
    CheckResult,
    CompanyReviewStatus,
    ConcernType,
    EventSource,
    IdentifierType,
    LifecycleEventType,
    LifecycleStatus,
    MembershipStatus,
    ProductStatus,
    RateLimitBucket,
    ReviewStatus,
    RiskRule,
)
from tests import factories as f


def _columns(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


# --- Conventions -------------------------------------------------------------------------------


def test_migrations_match_models(alembic_config: Config, engine) -> None:
    # Raises if the models have changes no migration covers.
    command.check(alembic_config)


def test_every_table_has_uuid_pk_and_created_at(engine) -> None:
    inspector = inspect(engine)
    for table in SQLModel.metadata.sorted_tables:
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        pk = inspector.get_pk_constraint(table.name)["constrained_columns"]
        assert len(pk) == 1, table.name
        assert str(columns[pk[0]]["type"]) == "UUID", table.name
        assert "created_at" in columns, table.name


@pytest.mark.parametrize(
    "table",
    [
        "audit_log",
        "change_notice_field",
        "notice_attachment",
        "lifecycle_event",
        "scan_event",
        "allocation_carton",
        "allocation_unit",
    ],
)
def test_append_only_tables_have_no_updated_at(engine, table: str) -> None:
    assert "updated_at" not in _columns(engine, table)


# Opaque payment_reference is the one allowed payment field (D122).
PAYMENT_WORDS = ("payment", "price", "amount", "currency", "total", "card", "checkout", "customer")
ALLOWED_PAYMENT_COLUMNS = {("lifecycle_event", "payment_reference")}


def test_no_payment_or_customer_columns_anywhere(engine) -> None:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            if (table, column["name"]) in ALLOWED_PAYMENT_COLUMNS:
                continue
            for word in PAYMENT_WORDS:
                assert word not in column["name"], f"{table}.{column['name']}"


def test_payment_reference_is_short_and_opaque(engine) -> None:
    columns = {c["name"]: c for c in inspect(engine).get_columns("lifecycle_event")}
    assert columns["payment_reference"]["type"].length == 100
    assert columns["transaction_ref"]["type"].length == 100


def test_new_records_default_to_unreviewed_states(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    member = f.make_member(session, user, company)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)
    notice = f.make_notice(session, company, user, product_id=product.product_id)

    assert user.is_admin is False
    assert user.is_active is True
    assert company.review_status == CompanyReviewStatus.PENDING_REVIEW
    assert company.reviewed_by_user_id is None
    assert member.membership_status == MembershipStatus.ACTIVE
    assert member.is_public_contact is False
    assert product.status == ProductStatus.DRAFT
    assert product.attributes == {}
    assert batch.review_status == ReviewStatus.PENDING_REVIEW
    assert batch.released_at is None
    assert product.registration_number is None
    assert notice.review_status == ChangeNoticeStatus.PENDING_REVIEW
    assert isinstance(product.product_id, uuid.UUID)
    assert product.created_at is not None


def test_new_units_start_issued_with_no_holder_or_sale(session: Session) -> None:
    batch = f.make_batch(session, f.make_product(session, f.make_company(session)))
    unit = f.make_unit(session, batch)
    session.refresh(unit)

    assert unit.lifecycle_status == LifecycleStatus.ISSUED
    assert unit.current_holder_company_id is None
    assert unit.last_sold_at is None
    assert unit.last_sold_area_id is None
    assert unit.last_sold_company_id is None


# --- Removed design: register, lookup, hidden code, withdrawn returns (D104, D138, D140) ----------


@pytest.mark.parametrize(
    "table", ["regulator_register", "regulatory_agency", "batch_scan", "credential_record"]
)
def test_register_and_lookup_tables_are_gone(engine, table: str) -> None:
    assert table not in inspect(engine).get_table_names()


def test_batch_qr_token_and_company_type_are_gone(engine) -> None:
    assert "qr_token" not in _columns(engine, "product_batch")
    assert "released_at" in _columns(engine, "product_batch")
    assert "company_type" not in _columns(engine, "company")
    assert "package_size" not in _columns(engine, "product")


FORBIDDEN_COLUMN_PARTS = ("secret_code", "secret_claimed", "return_disposition", "disposition")


def test_no_hidden_code_or_disposition_columns_anywhere(engine) -> None:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            for part in FORBIDDEN_COLUMN_PARTS:
                assert part not in column["name"], f"{table}.{column['name']}"


def test_no_withdrawn_or_claimed_value_anywhere(engine) -> None:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        for check in inspector.get_check_constraints(table):
            for word in ("WITHDRAWN", "CLAIMED", "RESTOCK", "NOT_FOR_RESALE"):
                assert word not in check["sqltext"], f"{table}: {check['name']}"
    assert "WITHDRAWN" not in set(LifecycleStatus)
    assert "WITHDRAWN" not in set(ProductStatus)
    assert "CLAIMED" not in set(LifecycleEventType)
    assert "RECOGNISED_WITHDRAWN" not in set(CheckResult)


# --- Enums -----------------------------------------------------------------------------------

# An unknown enum value fails the CHECK, or the column length first when it is longer.
REJECTED = (IntegrityError, DataError)


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("company", "review_status", "SAFE"),
        ("product", "status", "SAFE"),
        ("product", "status", "WITHDRAWN"),
        ("product_batch", "review_status", "SAFE"),
        ("product_unit", "lifecycle_status", "WITHDRAWN"),
        ("product_unit", "lifecycle_status", "GENUINE"),
        ("carton", "lifecycle_status", "WITHDRAWN"),
        ("company_member", "role", "ADMIN"),
        ("product_announcement", "kind", "GENUINE"),
    ],
)
def test_enum_columns_reject_unknown_values(
    session: Session, table: str, column: str, value: str
) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    member = f.make_member(session, user, company)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)
    announcement = ProductAnnouncement(
        product_id=product.product_id,
        title="Notice",
        message="Hello",
        created_by_user_id=user.user_id,
    )
    session.add(announcement)
    session.flush()
    ids = {
        "company": ("company_id", company.company_id),
        "company_member": ("member_id", member.member_id),
        "product": ("product_id", product.product_id),
        "product_batch": ("batch_id", batch.batch_id),
        "product_unit": ("unit_id", f.make_unit(session, batch).unit_id),
        "carton": ("carton_id", f.make_carton(session, batch, company).carton_id),
        "product_announcement": ("announcement_id", announcement.announcement_id),
    }
    pk_name, pk_value = ids[table]

    with pytest.raises(REJECTED):
        session.execute(
            text(f"UPDATE {table} SET {column} = :value WHERE {pk_name} = :id"),
            {"value": value, "id": pk_value},
        )


@pytest.mark.parametrize("event_type", ["CLAIMED", "GENUINE"])
def test_lifecycle_event_type_rejects_unknown_values(session: Session, event_type: str) -> None:
    batch = f.make_batch(session, f.make_product(session, f.make_company(session)))
    unit = f.make_unit(session, batch)

    with pytest.raises(REJECTED):
        session.execute(
            text(
                "INSERT INTO lifecycle_event (event_id, unit_id, event_type, source, occurred_at, "
                "received_without_transfer, outside_allocation) "
                "VALUES (:id, :unit, :type, 'MANUFACTURER', now(), false, false)"
            ),
            {"id": uuid.uuid4(), "unit": unit.unit_id, "type": event_type},
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [("identifier_type", "SECRET"), ("identifier_type", "NFC"), ("result", "GENUINE")],
)
def test_scan_event_enums_reject_unknown_values(session: Session, column: str, value: str) -> None:
    values = {"identifier_type": "QR", "result": "INVALID_IDENTITY"} | {column: value}

    with pytest.raises(REJECTED):
        session.execute(
            text(
                "INSERT INTO scan_event (scan_id, identifier_type, result) "
                "VALUES (:id, :identifier_type, :result)"
            ),
            {"id": uuid.uuid4(), **values},
        )


@pytest.mark.parametrize("identifier_type", list(IdentifierType))
def test_scan_event_accepts_qr_and_typed(session: Session, identifier_type: IdentifierType) -> None:
    session.add(ScanEvent(identifier_type=identifier_type, result=CheckResult.INVALID_IDENTITY))
    session.flush()

    assert set(IdentifierType) == {"QR", "TYPED"}


# --- Companies (D105, D106) -------------------------------------------------------------------


def test_company_needs_at_least_one_type_flag(session: Session) -> None:
    with pytest.raises(IntegrityError):
        f.make_company(session, is_manufacturer=False)


@pytest.mark.parametrize(
    "flags",
    [
        {"is_manufacturer": True},
        {"is_manufacturer": False, "is_distributor": True},
        {"is_manufacturer": False, "is_retailer": True},
        {"is_manufacturer": True, "is_distributor": True, "is_retailer": True},
    ],
)
def test_company_may_hold_any_combination_of_types(session: Session, flags: dict) -> None:
    company = f.make_company(session, **flags)

    assert company.is_manufacturer or company.is_distributor or company.is_retailer


def test_user_belongs_to_at_most_one_company(session: Session) -> None:
    user = f.make_user(session)
    f.make_member(session, user, f.make_company(session))

    with pytest.raises(IntegrityError):
        f.make_member(session, user, f.make_company(session))


def test_user_email_is_unique(session: Session) -> None:
    f.make_user(session, email="same@example.test")

    with pytest.raises(IntegrityError):
        f.make_user(session, email="same@example.test")


# --- Areas (D118) ----------------------------------------------------------------------------


def test_reference_areas_are_seeded_by_the_migration(session: Session) -> None:
    cities = {a.city for a in session.exec(select(Area)).all()}

    assert {"Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt"} <= cities
    lagos = f.area(session, "Lagos")
    assert Decimal("6") < lagos.latitude < Decimal("7")


def test_area_city_and_state_are_unique_together(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.add(Area(city="Lagos", state="Lagos", latitude=Decimal(1), longitude=Decimal(1)))
        session.flush()


def test_location_area_must_exist(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.add(
            SupplierLocation(
                company_id=f.make_company(session).company_id,
                name="Depot",
                address="1 Sample Road",
                area="Nowhere",
                area_id=uuid.uuid4(),
            )
        )
        session.flush()


# --- Catalogue -------------------------------------------------------------------------------


def test_batch_number_unique_per_product(session: Session) -> None:
    product = f.make_product(session, f.make_company(session))
    f.make_batch(session, product, batch_number="DEMO-LOT-001")

    with pytest.raises(IntegrityError):
        f.make_batch(session, product, batch_number="DEMO-LOT-001")


def test_same_batch_number_allowed_on_different_products(session: Session) -> None:
    company = f.make_company(session)
    first = f.make_batch(session, f.make_product(session, company), batch_number="DEMO-LOT-001")
    second = f.make_batch(session, f.make_product(session, company), batch_number="DEMO-LOT-001")

    assert first.batch_id != second.batch_id


def test_product_code_is_unique(session: Session) -> None:
    company = f.make_company(session)
    f.make_product(session, company, product_code="DEMO-PC-1")

    with pytest.raises(IntegrityError):
        f.make_product(session, company, product_code="DEMO-PC-1")


def test_batch_expiry_cannot_precede_production(session: Session) -> None:
    product = f.make_product(session, f.make_company(session))

    with pytest.raises(IntegrityError):
        f.make_batch(
            session,
            product,
            production_date=date(2026, 5, 1),
            expiry_date=date(2026, 4, 1),
        )


def test_products_may_share_a_registration_number(session: Session) -> None:
    company = f.make_company(session)
    first = f.make_product(session, company, registration_number="DEMO-NAFDAC-0001")
    copy = f.make_product(session, company, registration_number="DEMO-NAFDAC-0001")

    assert first.product_id != copy.product_id


def test_gtin_is_unique_per_company_when_set(session: Session) -> None:
    company = f.make_company(session)
    f.make_product(session, company, gtin="96385074")
    # Unset GTINs never clash, and another company may use the same number.
    f.make_product(session, company)
    f.make_product(session, company)
    f.make_product(session, f.make_company(session), gtin="96385074")

    with pytest.raises(IntegrityError):
        f.make_product(session, company, gtin="96385074")


def test_product_size_and_attributes_are_stored(session: Session) -> None:
    product = f.make_product(
        session, f.make_company(session), size="500 ml", attributes={"flavour": "Plain"}
    )
    session.refresh(product)

    assert product.size == "500 ml"
    assert product.attributes == {"flavour": "Plain"}


# --- Unit identity (D138, D139) -----------------------------------------------------------------


def test_unit_qr_token_hash_is_unique(session: Session) -> None:
    batch = f.make_batch(session, f.make_product(session, f.make_company(session)))
    hashed = f.token_hash()
    f.make_unit(session, batch, qr_token_hash=hashed)

    with pytest.raises(IntegrityError):
        f.make_unit(session, batch, qr_token_hash=hashed)


def test_carton_qr_token_hash_is_unique(session: Session) -> None:
    company = f.make_company(session)
    batch = f.make_batch(session, f.make_product(session, company))
    hashed = f.token_hash()
    f.make_carton(session, batch, company, qr_token_hash=hashed)

    with pytest.raises(IntegrityError):
        f.make_carton(session, batch, company, qr_token_hash=hashed)


@pytest.mark.parametrize(
    "value",
    [
        "7Q2M8KD3XH4N9VBT6C1RZJ5WAE",  # a raw 26-character token
        "A" * 64,  # upper-case hex
        "0" * 63,  # too short
    ],
)
def test_qr_token_hash_must_be_lowercase_sha256_hex(session: Session, value: str) -> None:
    company = f.make_company(session)
    batch = f.make_batch(session, f.make_product(session, company))

    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_unit(session, batch, qr_token_hash=value)
    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_carton(session, batch, company, qr_token_hash=value)


def test_carton_ref_is_unique_per_batch(session: Session) -> None:
    company = f.make_company(session)
    product = f.make_product(session, company)
    first_batch = f.make_batch(session, product, batch_number="DEMO-LOT-001")
    second_batch = f.make_batch(session, product, batch_number="DEMO-LOT-002")
    f.make_carton(session, first_batch, company, carton_ref="C001")
    f.make_carton(session, second_batch, company, carton_ref="C001")

    with pytest.raises(IntegrityError):
        f.make_carton(session, first_batch, company, carton_ref="C001")


# --- Lifecycle events (D112, D121, D140) -------------------------------------------------------


@pytest.fixture
def unit_and_carton(session: Session):
    company = f.make_company(session)
    batch = f.make_batch(session, f.make_product(session, company))
    return f.make_unit(session, batch), f.make_carton(session, batch, company)


def test_lifecycle_event_has_exactly_one_of_unit_or_carton(
    session: Session, unit_and_carton
) -> None:
    unit, carton = unit_and_carton
    f.make_event(session, unit_id=unit.unit_id)
    f.make_event(session, carton_id=carton.carton_id)

    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_event(session)
    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_event(session, unit_id=unit.unit_id, carton_id=carton.carton_id)


def test_lifecycle_events_are_append_only(session: Session, unit_and_carton) -> None:
    unit, _ = unit_and_carton
    event = f.make_event(session, unit_id=unit.unit_id)
    params = {"id": event.event_id}

    with pytest.raises(IntegrityError, match="append-only"), session.begin_nested():
        session.execute(
            text("UPDATE lifecycle_event SET event_type = 'SOLD' WHERE event_id = :id"), params
        )
    with pytest.raises(IntegrityError, match="append-only"), session.begin_nested():
        session.execute(text("DELETE FROM lifecycle_event WHERE event_id = :id"), params)

    assert session.get(LifecycleEvent, event.event_id).event_type == LifecycleEventType.ISSUED


@pytest.mark.parametrize(
    "event_type", [LifecycleEventType.SALE_CORRECTED, LifecycleEventType.VOIDED]
)
def test_correction_and_void_need_a_reason(
    session: Session, unit_and_carton, event_type: LifecycleEventType
) -> None:
    unit, _ = unit_and_carton
    f.make_event(session, unit_id=unit.unit_id, event_type=event_type, reason="Wrong item scanned")

    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_event(session, unit_id=unit.unit_id, event_type=event_type)
    with pytest.raises(IntegrityError), session.begin_nested():
        f.make_event(session, unit_id=unit.unit_id, event_type=event_type, reason="   ")


def test_sale_correction_keeps_and_points_to_the_original_sale(
    session: Session, unit_and_carton
) -> None:
    unit, _ = unit_and_carton
    sold = f.make_event(session, unit_id=unit.unit_id, event_type=LifecycleEventType.SOLD)
    f.make_event(
        session,
        unit_id=unit.unit_id,
        event_type=LifecycleEventType.SALE_CORRECTED,
        reason="Rang up the wrong pack",
        corrects_event_id=sold.event_id,
    )
    f.make_event(
        session,
        unit_id=unit.unit_id,
        event_type=LifecycleEventType.RETURNED,
        returns_event_id=sold.event_id,
    )

    assert session.get(LifecycleEvent, sold.event_id).event_type == LifecycleEventType.SOLD


def test_transfer_needs_a_target_company(session: Session, unit_and_carton) -> None:
    unit, _ = unit_and_carton
    target = f.make_company(session, is_manufacturer=False, is_retailer=True)
    f.make_event(
        session,
        unit_id=unit.unit_id,
        event_type=LifecycleEventType.TRANSFERRED,
        to_company_id=target.company_id,
    )

    with pytest.raises(IntegrityError):
        f.make_event(session, unit_id=unit.unit_id, event_type=LifecycleEventType.TRANSFERRED)


def _pos_sale(session: Session, partner, unit, transaction: str = "DEMO-TX-1", **overrides):
    values = {
        "unit_id": unit.unit_id,
        "event_type": LifecycleEventType.SOLD,
        "source": EventSource.POS_API,
        "pos_partner_id": partner.partner_id,
        "transaction_ref": transaction,
        "payment_reference": "DEMO-PAY-1",
    }
    return f.make_event(session, **(values | overrides))


def test_pos_idempotency_key_is_unique(session: Session, unit_and_carton) -> None:
    unit, _ = unit_and_carton
    partner = f.make_pos_partner(session, f.make_user(session, is_admin=True))
    _pos_sale(session, partner, unit)
    # Same transaction, another event type or another transaction: allowed.
    _pos_sale(session, partner, unit, event_type=LifecycleEventType.RETURNED)
    _pos_sale(session, partner, unit, transaction="DEMO-TX-2")
    # Non-POS events never collide on the key.
    f.make_event(session, unit_id=unit.unit_id, event_type=LifecycleEventType.SOLD)
    f.make_event(session, unit_id=unit.unit_id, event_type=LifecycleEventType.SOLD)

    with pytest.raises(IntegrityError):
        _pos_sale(session, partner, unit)


def test_pos_events_carry_a_unit_and_a_transaction(session: Session, unit_and_carton) -> None:
    unit, carton = unit_and_carton
    partner = f.make_pos_partner(session, f.make_user(session, is_admin=True))

    with pytest.raises(IntegrityError), session.begin_nested():
        _pos_sale(session, partner, unit, transaction=None)
    with pytest.raises(IntegrityError), session.begin_nested():
        _pos_sale(session, partner, unit, unit_id=None, carton_id=carton.carton_id)


# --- Consumer scans and rate-limit counts (D118, D144) -----------------------------------------


def test_scan_event_columns_are_exact(engine) -> None:
    assert _columns(engine, "scan_event") == {
        "scan_id",
        "identifier_type",
        "unit_id",
        "carton_id",
        "area_id",
        "result",
        "created_at",
    }


def test_scan_events_cannot_be_edited_but_can_be_purged(session: Session) -> None:
    scan = ScanEvent(identifier_type=IdentifierType.TYPED, result=CheckResult.INVALID_IDENTITY)
    session.add(scan)
    session.flush()
    params = {"id": scan.scan_id}

    with pytest.raises(IntegrityError, match="append-only"), session.begin_nested():
        session.execute(
            text("UPDATE scan_event SET result = 'RECOGNISED_NOT_SOLD' WHERE scan_id = :id"), params
        )

    session.execute(text("DELETE FROM scan_event WHERE scan_id = :id"), params)
    assert session.exec(select(ScanEvent).where(ScanEvent.scan_id == scan.scan_id)).first() is None


def test_rate_limit_daily_columns_are_exact(engine) -> None:
    assert _columns(engine, "rate_limit_daily") == {
        "rate_limit_id",
        "area_id",
        "day",
        "bucket",
        "count",
        "created_at",
        "updated_at",
    }


def test_rate_limit_daily_is_one_row_per_area_day_and_bucket(session: Session) -> None:
    lagos = f.area(session).area_id
    day = date(2026, 10, 22)
    session.add(RateLimitDaily(area_id=lagos, day=day, bucket=RateLimitBucket.CHECK, count=3))
    session.add(RateLimitDaily(area_id=lagos, day=day, bucket=RateLimitBucket.LOGIN, count=1))
    session.add(RateLimitDaily(area_id=None, day=day, bucket=RateLimitBucket.CHECK, count=1))
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(RateLimitDaily(area_id=lagos, day=day, bucket=RateLimitBucket.CHECK))
        session.flush()
    # An unknown area is a single bucket too.
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(RateLimitDaily(area_id=None, day=day, bucket=RateLimitBucket.CHECK))
        session.flush()


PERSONAL_DATA_PARTS = ("ip", "user_agent", "cookie", "device", "gps", "user_id", "session", "phone")


@pytest.mark.parametrize("table", ["scan_event", "rate_limit_daily", "consumer_report"])
def test_anonymous_tables_hold_no_personal_data(engine, table: str) -> None:
    for column in _columns(engine, table):
        for part in PERSONAL_DATA_PARTS:
            assert not column.startswith(part) and f"_{part}" not in column, f"{table}.{column}"


def test_consumer_report_description_is_limited(session: Session) -> None:
    session.add(ConsumerReport(concern_type=ConcernType.OTHER, description="x" * 1000))
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(ConsumerReport(concern_type=ConcernType.OTHER, description="x" * 1001))
        session.flush()


# --- Risk alerts (D125, D143) ------------------------------------------------------------------


def test_one_open_alert_per_rule_and_unit(session: Session, unit_and_carton) -> None:
    unit, _ = unit_and_carton

    def alert(status=AlertStatus.OPEN, rule=RiskRule.R3_SCAN_VOLUME) -> None:
        session.add(
            RiskAlert(rule=rule, level=AlertLevel.MEDIUM, unit_id=unit.unit_id, status=status)
        )
        session.flush()

    alert(AlertStatus.RESOLVED_LEGITIMATE)
    alert()
    alert(rule=RiskRule.R2_IMPOSSIBLE_TRAVEL)  # another rule may be open on the same unit

    with pytest.raises(IntegrityError), session.begin_nested():
        alert(AlertStatus.INVESTIGATING)


def test_rule_9_alert_is_per_batch_and_area(session: Session) -> None:
    batch = f.make_batch(session, f.make_product(session, f.make_company(session)))
    lagos, kano = f.area(session, "Lagos").area_id, f.area(session, "Kano").area_id

    def alert(area_id) -> None:
        session.add(
            RiskAlert(
                rule=RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
                level=AlertLevel.MEDIUM,
                batch_id=batch.batch_id,
                area_id=area_id,
            )
        )
        session.flush()

    alert(lagos)
    alert(kano)
    with pytest.raises(IntegrityError), session.begin_nested():
        alert(lagos)
    with pytest.raises(IntegrityError), session.begin_nested():
        alert(None)  # rule 9 always names its batch and area


# --- Allocations (D131, D142) -----------------------------------------------------------------


@pytest.fixture
def allocation_setup(session: Session):
    company = f.make_company(session)
    batch = f.make_batch(session, f.make_product(session, company))
    user = f.make_user(session)
    return company, batch, user


@pytest.mark.parametrize("quantity", [0, -5])
def test_allocation_quantity_must_be_positive(
    session: Session, allocation_setup, quantity: int
) -> None:
    _, batch, user = allocation_setup

    with pytest.raises(IntegrityError):
        f.make_allocation(session, batch, user, quantity=quantity)


def test_carton_sits_in_at_most_one_allocation(session: Session, allocation_setup) -> None:
    company, batch, user = allocation_setup
    carton = f.make_carton(session, batch, company)
    lagos = f.make_allocation(session, batch, user)
    kano = f.make_allocation(
        session, batch, user, destination_area_id=f.area(session, "Kano").area_id
    )
    session.add(AllocationCarton(allocation_id=lagos.allocation_id, carton_id=carton.carton_id))
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(AllocationCarton(allocation_id=kano.allocation_id, carton_id=carton.carton_id))
        session.flush()


def test_unit_sits_in_at_most_one_allocation(session: Session, allocation_setup) -> None:
    _, batch, user = allocation_setup
    unit = f.make_unit(session, batch)
    first = f.make_allocation(session, batch, user)
    second = f.make_allocation(session, batch, user)
    session.add(AllocationUnit(allocation_id=first.allocation_id, unit_id=unit.unit_id))
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(AllocationUnit(allocation_id=second.allocation_id, unit_id=unit.unit_id))
        session.flush()


# --- POS partners (D121) -----------------------------------------------------------------------


def test_pos_key_hash_is_unique_sha256(session: Session) -> None:
    partner = f.make_pos_partner(session, f.make_user(session, is_admin=True))
    hashed = f.token_hash()
    session.add(
        PosPartnerKey(partner_id=partner.partner_id, key_prefix="fl_live_", key_hash=hashed)
    )
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            PosPartnerKey(partner_id=partner.partner_id, key_prefix="fl_live_", key_hash=hashed)
        )
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            PosPartnerKey(partner_id=partner.partner_id, key_prefix="fl_live_", key_hash="raw-key")
        )
        session.flush()


def test_pos_retailer_link_and_till_are_unique(session: Session) -> None:
    admin = f.make_user(session, is_admin=True)
    partner = f.make_pos_partner(session, admin)
    retailer = f.make_company(session, is_manufacturer=False, is_retailer=True)
    location = SupplierLocation(
        company_id=retailer.company_id, name="Shop", address="2 Sample Road", area="Lagos"
    )
    session.add(location)
    link = {"partner_id": partner.partner_id, "retailer_company_id": retailer.company_id}
    till = link | {"till_ref": "TILL-1", "location_id": location.location_id}
    session.add(PosPartnerRetailer(**link, created_by_user_id=admin.user_id))
    session.add(PosTill(**till))
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(PosPartnerRetailer(**link, created_by_user_id=admin.user_id))
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(PosTill(**till))
        session.flush()


# --- Announcements and recalls (D126) ----------------------------------------------------------


def test_recall_needs_a_reason(session: Session) -> None:
    user = f.make_user(session)
    product = f.make_product(session, f.make_company(session))
    batch = f.make_batch(session, product)

    def announce(**values) -> ProductAnnouncement:
        row = ProductAnnouncement(
            product_id=product.product_id,
            title="Recall",
            message="Return this batch to the shop.",
            created_by_user_id=user.user_id,
            **values,
        )
        session.add(row)
        session.flush()
        return row

    assert announce().kind == AnnouncementKind.NOTICE
    announce(kind=AnnouncementKind.RECALL, batch_id=batch.batch_id, recall_reason="Seal defect")

    with pytest.raises(IntegrityError), session.begin_nested():
        announce(kind=AnnouncementKind.RECALL)
    with pytest.raises(IntegrityError), session.begin_nested():
        announce(kind=AnnouncementKind.RECALL, recall_reason=" ")


# --- Change notices, attachments, orders (kept) -------------------------------------------------


def test_change_notice_requires_exactly_one_target(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)

    with pytest.raises(IntegrityError):
        with session.begin_nested():
            f.make_notice(session, company, user)

    with pytest.raises(IntegrityError):
        f.make_notice(
            session, company, user, product_id=product.product_id, batch_id=batch.batch_id
        )


def test_change_notice_target_must_exist(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)

    with pytest.raises(IntegrityError):
        f.make_notice(session, company, user, product_id=uuid.uuid4())


def test_attachment_size_limited_to_5_mb(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    notice = f.make_notice(
        session, company, user, product_id=f.make_product(session, company).product_id
    )

    session.add(
        NoticeAttachment(
            notice_id=notice.notice_id,
            storage_key="private/ok.pdf",
            original_filename="ok.pdf",
            mime_type=AttachmentMimeType.PDF,
            size_bytes=5 * 1024 * 1024,
        )
    )
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(
            NoticeAttachment(
                notice_id=notice.notice_id,
                storage_key="private/too-big.pdf",
                original_filename="too-big.pdf",
                mime_type=AttachmentMimeType.PDF,
                size_bytes=5 * 1024 * 1024 + 1,
            )
        )
        session.flush()


def test_order_buyer_and_seller_must_differ(session: Session) -> None:
    company = f.make_company(session)

    with pytest.raises(IntegrityError):
        f.make_order(session, company, company, f.make_user(session))


def test_order_quantities_must_be_positive(session: Session) -> None:
    seller = f.make_company(session)
    product = f.make_product(session, seller)
    order = f.make_order(session, f.make_company(session), seller, f.make_user(session))
    line = f.make_line(session, order, product)
    batch = f.make_batch(session, product)

    with pytest.raises(IntegrityError):
        with session.begin_nested():
            f.make_line(session, order, product, quantity=Decimal("0"))

    # Allocations carry no quantity (no stock, D99), and a line links a batch only once.
    session.add(OrderBatchAllocation(line_id=line.line_id, batch_id=batch.batch_id))
    session.flush()
    with pytest.raises(IntegrityError):
        session.add(OrderBatchAllocation(line_id=line.line_id, batch_id=batch.batch_id))
        session.flush()
