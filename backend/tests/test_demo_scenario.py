"""The D145 demo scenario: each case gives its expected result and alert, through the services."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, select

from app.core.config import Settings
from app.demo_data import (
    ABUJA_ALLOCATED,
    DEMO_CODES,
    DEMO_KANO_EMAIL,
    EXPIRED_BATCH,
    LIVE_BATCH,
    SCENARIO_BATCH,
    TEST_BATCH,
    demo_code,
    seed_demo_data,
    seed_demo_orders,
    seed_demo_pos,
    seed_demo_scenario,
)
from app.models import (
    AllocationCarton,
    AllocationUnit,
    AppUser,
    Area,
    BatchAllocation,
    LifecycleEvent,
    ProductBatch,
    ProductUnit,
    RiskAlert,
    ScanEvent,
)
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    CheckResult,
    IdentifierType,
    LifecycleEventType,
    LifecycleStatus,
    RiskRule,
)
from app.seed import SeedConfigError, check_can_reset, reset_database, seed_admin
from app.services import check, companies, identity, risk

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def demo_settings(**overrides) -> Settings:
    values = {
        "seed_admin_email": "admin@demo.foodlens.invalid",
        "seed_admin_password": "demo-admin-password",
        "seed_demo_password": "demo-account-password",
        "pos_secret_key": Fernet.generate_key().decode(),
    } | overrides
    return Settings(**values)


def seed(db: Session, settings: Settings | None = None) -> Settings:
    settings = settings or demo_settings()
    admin = seed_admin(db, settings)
    seed_demo_data(db, NOW.date())
    seed_demo_orders(db, settings.seed_demo_password)
    seed_demo_pos(db, settings, admin, settings.seed_demo_password)
    seed_demo_scenario(db, settings, NOW)
    return settings


@pytest.fixture
def seeded(session: Session) -> Settings:
    return seed(session)


def unit_of(db: Session, code: str) -> ProductUnit:
    return db.exec(
        select(ProductUnit).where(ProductUnit.qr_token_hash == identity.token_hash(code))
    ).one()


def alerts_of(db: Session, code: str) -> list[RiskAlert]:
    return list(db.exec(select(RiskAlert).where(RiskAlert.unit_id == unit_of(db, code).unit_id)))


def consumer(db: Session, settings: Settings, code: str, city: str = "Lagos", at: datetime = NOW):
    return check.check_code(
        db,
        code,
        IdentifierType.QR,
        area=companies.area_from_text(db, city),
        now=at,
        window_hours=settings.just_sold_window_hours,
        thresholds=risk.Thresholds.from_settings(settings),
    )


def area_id(db: Session, city: str):
    return db.exec(select(Area.area_id).where(Area.city == city)).one()


def batch(db: Session, number: str) -> ProductBatch:
    return db.exec(select(ProductBatch).where(ProductBatch.batch_number == number)).one()


# --- Whole scenario ------------------------------------------------------------------------------


def test_the_scenario_raises_exactly_the_expected_alerts(
    session: Session, seeded: Settings
) -> None:
    alerts = {(a.rule, a.level) for a in session.exec(select(RiskAlert))}

    assert alerts == {
        (RiskRule.R2_IMPOSSIBLE_TRAVEL, AlertLevel.HIGH),
        (RiskRule.R4_INVALID_BURST, AlertLevel.MEDIUM),
        (RiskRule.R6_UNRELEASED_SCANNED, AlertLevel.MEDIUM),
        (RiskRule.R8_VOIDED_CODE_IN_USE, AlertLevel.HIGH),
        (RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED, AlertLevel.MEDIUM),
    }
    assert len(session.exec(select(RiskAlert)).all()) == 5


def test_the_seed_runs_twice_without_changing_anything(session: Session, seeded: Settings) -> None:
    scans = len(session.exec(select(ScanEvent)).all())
    events = len(session.exec(select(LifecycleEvent)).all())

    line = seed_demo_scenario(session, seeded, NOW)

    assert "already seeded" in line
    assert len(session.exec(select(ScanEvent)).all()) == scans
    assert len(session.exec(select(LifecycleEvent)).all()) == events


def test_the_scenario_is_skipped_without_the_pos_partner(session: Session) -> None:
    settings = demo_settings(pos_secret_key="")
    seed_demo_data(session, NOW.date())
    seed_demo_orders(session)
    seed_demo_pos(session, settings, None)

    line = seed_demo_scenario(session, settings, NOW)

    assert "skipped" in line
    assert session.exec(select(ProductUnit)).all() == []


def test_demo_codes_are_valid_tokens_stored_only_as_hashes(
    session: Session, seeded: Settings
) -> None:
    code = DEMO_CODES.live_pack
    assert len(code) == identity.TOKEN_LENGTH
    assert set(code) <= set(identity.ALPHABET)
    assert unit_of(session, code).qr_token_hash == identity.token_hash(code)
    hashes = session.exec(select(ProductUnit.qr_token_hash)).all()
    assert code not in hashes and all(len(h) == 64 for h in hashes)


def test_kano_retailer_can_sign_in(session: Session, seeded: Settings) -> None:
    from app.core.security import verify_password

    user = session.exec(select(AppUser).where(AppUser.email == DEMO_KANO_EMAIL)).one()
    assert verify_password("demo-account-password", user.password_hash)


# --- Allocations ---------------------------------------------------------------------------------


def test_the_batch_is_allocated_between_lagos_and_kano(session: Session, seeded: Settings) -> None:
    main = batch(session, SCENARIO_BATCH)
    rows = session.exec(
        select(BatchAllocation).where(BatchAllocation.batch_id == main.batch_id)
    ).all()
    by_area: dict = {}
    for row in rows:
        by_area[row.destination_area_id] = by_area.get(row.destination_area_id, 0) + row.quantity

    assert by_area[area_id(session, "Lagos")] == 10
    assert by_area[area_id(session, "Kano")] == 14
    assert by_area[area_id(session, "Abuja")] == ABUJA_ALLOCATED
    assert len(session.exec(select(AllocationCarton)).all()) == 2


def test_loose_units_are_allocated_individually_to_the_kano_retailer(
    session: Session, seeded: Settings
) -> None:
    unit = unit_of(session, DEMO_CODES.kano_loose)
    link = session.exec(select(AllocationUnit).where(AllocationUnit.unit_id == unit.unit_id)).one()
    allocation = session.get(BatchAllocation, link.allocation_id)

    assert unit.parent_carton_id is None
    assert allocation.destination_area_id == area_id(session, "Kano")
    assert allocation.destination_company_id == unit.current_holder_company_id
    assert unit.lifecycle_status == LifecycleStatus.IN_STOCK
    received = session.exec(
        select(LifecycleEvent).where(
            LifecycleEvent.unit_id == unit.unit_id,
            LifecycleEvent.event_type == LifecycleEventType.RECEIVED,
        )
    ).one()
    assert received.outside_allocation is False


def test_stock_received_inside_its_allocation_is_not_flagged(
    session: Session, seeded: Settings
) -> None:
    flagged = session.exec(
        select(LifecycleEvent).where(LifecycleEvent.outside_allocation.is_(True))
    ).all()
    assert flagged == []


def test_one_area_exceeding_its_allocation_raises_rule_9_on_the_dashboard_only(
    session: Session, seeded: Settings
) -> None:
    alert = session.exec(
        select(RiskAlert).where(RiskAlert.rule == RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED)
    ).one()

    assert alert.area_id == area_id(session, "Abuja")
    assert alert.batch_id == batch(session, SCENARIO_BATCH).batch_id
    assert alert.evidence["seen"] == 5
    assert alert.unit_id is None
    result = consumer(session, seeded, DEMO_CODES.abuja_over, "Abuja", NOW)
    assert result.result == CheckResult.RECOGNISED_NOT_SOLD


# --- The buyer cases -----------------------------------------------------------------------------


def test_pos_sale_then_buyer_rescan_is_just_sold_with_no_alert(
    session: Session, seeded: Settings
) -> None:
    result = consumer(session, seeded, DEMO_CODES.pos_rescan)

    assert result.result == CheckResult.RECOGNISED_JUST_SOLD
    assert "Demo Corner Shop (fictional)" in result.message
    assert alerts_of(session, DEMO_CODES.pos_rescan) == []
    assert session.exec(
        select(ScanEvent).where(
            ScanEvent.unit_id == unit_of(session, DEMO_CODES.pos_rescan).unit_id
        )
    ).all()


def test_sold_in_lagos_then_checked_in_kano_three_hours_later_raises_an_alert(
    session: Session, seeded: Settings
) -> None:
    alerts = alerts_of(session, DEMO_CODES.sold_lagos_kano)

    assert [(a.rule, a.level) for a in alerts] == [(RiskRule.R2_IMPOSSIBLE_TRAVEL, AlertLevel.HIGH)]
    snapshot = alerts[0].evidence["snapshot"][0]
    assert snapshot["from"]["area"] == "Lagos" and snapshot["to"]["area"] == "Kano"
    assert snapshot["hours"] == pytest.approx(3.0)
    result = consumer(session, seeded, DEMO_CODES.sold_lagos_kano, "Kano")
    assert result.result == CheckResult.SUSPICIOUS_ACTIVITY
    assert result.possible_patterns


def test_refund_then_resale_gives_no_alert_and_keeps_both_sales(
    session: Session, seeded: Settings
) -> None:
    unit = unit_of(session, DEMO_CODES.refund_resale)
    types = [
        e.event_type
        for e in session.exec(
            select(LifecycleEvent)
            .where(
                LifecycleEvent.unit_id == unit.unit_id,
                LifecycleEvent.event_type.in_(
                    [LifecycleEventType.SOLD, LifecycleEventType.RETURNED]
                ),
            )
            .order_by(LifecycleEvent.occurred_at)
        )
    ]

    assert types == [
        LifecycleEventType.SOLD,
        LifecycleEventType.RETURNED,
        LifecycleEventType.SOLD,
    ]
    assert alerts_of(session, DEMO_CODES.refund_resale) == []
    assert consumer(session, seeded, DEMO_CODES.refund_resale).result == (
        CheckResult.RECOGNISED_JUST_SOLD
    )


def test_the_live_pack_shows_the_whole_walkthrough(session: Session, seeded: Settings) -> None:
    """The walkthrough sells this pack, so the seed must leave it unsold and unchecked."""
    result = consumer(session, seeded, DEMO_CODES.live_pack)

    assert result.result == CheckResult.RECOGNISED_NOT_SOLD
    assert alerts_of(session, DEMO_CODES.live_pack) == []


# --- The other results ---------------------------------------------------------------------------


def test_invalid_code_burst_raises_rule_4_for_admins_only(
    session: Session, seeded: Settings
) -> None:
    alert = session.exec(select(RiskAlert).where(RiskAlert.rule == RiskRule.R4_INVALID_BURST)).one()

    assert alert.area_id == area_id(session, "Port Harcourt")
    assert alert.manufacturer_id is None
    assert alert.evidence["snapshot"][-1]["count"] == 20
    assert consumer(session, seeded, DEMO_CODES.unrecognised).result == CheckResult.INVALID_IDENTITY


def test_voided_code_scan_raises_rule_8(session: Session, seeded: Settings) -> None:
    alerts = alerts_of(session, DEMO_CODES.voided)

    assert unit_of(session, DEMO_CODES.voided).lifecycle_status == LifecycleStatus.VOIDED
    assert [(a.rule, a.level) for a in alerts] == [
        (RiskRule.R8_VOIDED_CODE_IN_USE, AlertLevel.HIGH)
    ]
    assert consumer(session, seeded, DEMO_CODES.voided, "Ibadan").result == (
        CheckResult.INVALID_IDENTITY
    )


def test_expired_batch_adds_a_warning_to_a_recognised_result(
    session: Session, seeded: Settings
) -> None:
    result = consumer(session, seeded, DEMO_CODES.expired)

    assert result.result == CheckResult.RECOGNISED_NOT_SOLD
    assert result.batch.batch_number == EXPIRED_BATCH and result.batch.expired is True
    assert any("has passed" in w for w in result.warnings)
    assert alerts_of(session, DEMO_CODES.expired) == []


def test_never_sold_units_stay_in_stock_and_check_clean(session: Session, seeded: Settings) -> None:
    for code in (DEMO_CODES.never_sold, DEMO_CODES.rehearsal_pack, demo_code("2005")):
        unit = unit_of(session, code)
        assert unit.lifecycle_status == LifecycleStatus.IN_STOCK
        assert unit.last_sold_at is None
    assert consumer(session, seeded, DEMO_CODES.never_sold).result == (
        CheckResult.RECOGNISED_NOT_SOLD
    )
    assert alerts_of(session, DEMO_CODES.never_sold) == []


def test_only_the_test_carton_stays_unreleased(session: Session, seeded: Settings) -> None:
    test_batch = batch(session, TEST_BATCH)
    unreleased = session.exec(
        select(ProductUnit).where(ProductUnit.lifecycle_status == LifecycleStatus.ISSUED)
    ).all()

    assert len(unreleased) == 3
    assert {u.batch_id for u in unreleased} == {test_batch.batch_id}
    assert batch(session, SCENARIO_BATCH).released_at is not None
    assert batch(session, EXPIRED_BATCH).released_at is not None


def test_only_the_test_carton_gives_suspicious_activity_for_being_unreleased(
    session: Session, seeded: Settings
) -> None:
    test_batch = batch(session, TEST_BATCH)
    rule_6 = session.exec(
        select(RiskAlert).where(RiskAlert.rule == RiskRule.R6_UNRELEASED_SCANNED)
    ).all()

    assert [a.batch_id for a in rule_6] == [test_batch.batch_id]
    assert consumer(session, seeded, DEMO_CODES.unreleased_checked).result == (
        CheckResult.SUSPICIOUS_ACTIVITY
    )
    for code in (DEMO_CODES.live_pack, DEMO_CODES.never_sold, demo_code("K002"), demo_code("E002")):
        assert consumer(session, seeded, code).result != CheckResult.SUSPICIOUS_ACTIVITY


def test_the_live_batch_is_left_without_codes_to_generate(
    session: Session, seeded: Settings
) -> None:
    live = batch(session, LIVE_BATCH)
    assert (
        session.exec(select(ProductUnit).where(ProductUnit.batch_id == live.batch_id)).all() == []
    )


def test_alerts_stay_open_and_history_is_backdated_in_order(
    session: Session, seeded: Settings
) -> None:
    assert all(a.status == AlertStatus.OPEN for a in session.exec(select(RiskAlert)))
    unit = unit_of(session, DEMO_CODES.sold_lagos_kano)
    events = session.exec(
        select(LifecycleEvent)
        .where(LifecycleEvent.unit_id == unit.unit_id)
        .order_by(LifecycleEvent.occurred_at)
    ).all()
    assert [e.event_type for e in events] == [
        LifecycleEventType.ISSUED,
        LifecycleEventType.RELEASED,
        LifecycleEventType.RECEIVED,
        LifecycleEventType.TRANSFERRED,
        LifecycleEventType.RECEIVED,
        LifecycleEventType.SOLD,
    ]
    assert events[-1].occurred_at == NOW - timedelta(hours=4)
    assert unit.last_sold_at == NOW - timedelta(hours=4)


# --- Reset ---------------------------------------------------------------------------------------


def test_reset_empties_the_data_and_keeps_the_areas(session: Session, seeded: Settings) -> None:
    areas = len(session.exec(select(Area)).all())

    reset_database(session)

    assert session.exec(select(ProductUnit)).all() == []
    assert session.exec(select(AppUser)).all() == []
    assert len(session.exec(select(Area)).all()) == areas
    seed(session)
    assert unit_of(session, DEMO_CODES.live_pack) is not None


def test_reset_is_refused_outside_development() -> None:
    with pytest.raises(SeedConfigError, match="APP_ENV=development"):
        check_can_reset(demo_settings(app_env="production"))


def test_reset_is_refused_when_the_seed_could_not_rebuild_the_demo() -> None:
    with pytest.raises(SeedConfigError, match="POS_SECRET_KEY") as error:
        check_can_reset(demo_settings(pos_secret_key=""))
    assert "deleted nothing" in str(error.value)
    check_can_reset(demo_settings())


def test_a_backdated_alert_is_raised_when_its_trigger_happened(
    session: Session, seeded: Settings
) -> None:
    alert = alerts_of(session, DEMO_CODES.sold_lagos_kano)[0]
    assert alert.created_at == NOW - timedelta(hours=1)
