"""Risk rules and alerts (Phase 6): each rule on its own case, the cases that must never alert,
de-duplication, evidence that survives the scan purge, the consumer result, the alert workflow and
cross-company access."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import hash_password
from app.jobs.purge import purge_scans
from app.models import (
    AppUser,
    AuditLog,
    Carton,
    Company,
    CompanyMember,
    ProductBatch,
    ProductUnit,
    RiskAlert,
    ScanEvent,
    SupplierLocation,
)
from app.models.base import utc_now
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    CheckResult,
    CompanyReviewStatus,
    IdentifierType,
    LifecycleEventType,
    LifecycleStatus,
    MemberRole,
    ProductStatus,
    ReviewStatus,
    RiskRule,
)
from app.services import check as check_service
from app.services import identity, lifecycle, risk
from tests import factories as f

PASSWORD = "correct-horse-battery"
E = LifecycleEventType
S = LifecycleStatus
R = RiskRule
TH = risk.Thresholds(
    window_hours=6,
    different_area_km=50,
    travel_min_km=100,
    max_travel_kmh=120,
    scan_volume=10,
    invalid_burst=20,
    overage_pct=10,
)


@dataclass
class World:
    db: Session
    manufacturer: Company
    batch: ProductBatch
    owner: AppUser
    make_client: Callable[..., TestClient]

    def unit(self, status=S.RELEASED, carton: Carton | None = None, **overrides):
        token = identity.new_token()
        unit = f.make_unit(
            self.db,
            self.batch,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            current_holder_company_id=self.manufacturer.company_id,
            parent_carton_id=carton.carton_id if carton else None,
            **overrides,
        )
        return unit, token

    def carton(self, units: int = 2, status=S.RELEASED):
        token = identity.new_token()
        carton = f.make_carton(
            self.db,
            self.batch,
            self.manufacturer,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            current_holder_company_id=self.manufacturer.company_id,
        )
        packs = [self.unit(status=status, carton=carton) for _ in range(units)]
        return carton, token, packs

    def shop(self, name: str, city: str = "Lagos", **flags) -> CompanyMember:
        values = {"is_manufacturer": False, "is_retailer": True} | flags
        company = f.make_company(
            self.db, display_name=name, review_status=CompanyReviewStatus.APPROVED, **values
        )
        self.db.add(
            SupplierLocation(
                company_id=company.company_id,
                name=f"{name} shop",
                address="1 Demo Street",
                area=city,
                area_id=f.area(self.db, city).area_id,
                review_status=ReviewStatus.APPROVED,
            )
        )
        self.db.flush()
        return f.make_member(self.db, f.make_user(self.db), company)

    def event(self, member, token, event_type, at=None, **kw):
        return lifecycle.record_merchant_event(
            self.db, member, token, event_type, occurred_at=at, thresholds=TH, **kw
        )

    def check(self, token: str, city: str | None = "Lagos", at=None, th=TH):
        return check_service.check_code(
            self.db,
            token,
            IdentifierType.QR,
            area=f.area(self.db, city) if city else None,
            now=at or utc_now(),
            window_hours=th.window_hours,
            thresholds=th,
        )

    def alerts(self, rule: RiskRule | None = None, **where) -> list[RiskAlert]:
        self.db.expire_all()
        statement = select(RiskAlert)
        if rule:
            statement = statement.where(RiskAlert.rule == rule)
        for column, value in where.items():
            statement = statement.where(getattr(RiskAlert, column) == value)
        return list(self.db.exec(statement.order_by(RiskAlert.created_at)).all())

    def signed_in(self, user: AppUser) -> TestClient:
        client = self.make_client(settings=Settings(rate_limit_enabled=False))
        login = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
        assert login.status_code == 200
        return client


@pytest.fixture
def world(session: Session, make_client) -> World:
    manufacturer = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    product = f.make_product(session, manufacturer, status=ProductStatus.PUBLISHED)
    batch = f.make_batch(session, product, review_status=ReviewStatus.APPROVED)
    owner = f.make_user(session, password_hash=hash_password(PASSWORD))
    f.make_member(session, owner, manufacturer)
    return World(session, manufacturer, batch, owner, make_client)


def evidence_ok(alert: RiskAlert) -> None:
    assert alert.evidence["explanation"]
    assert alert.evidence["snapshot"]
    assert alert.evidence["snapshot"][-1]["explanation"] == alert.evidence["explanation"]


# --- Each rule on its own case ---------------------------------------------------------------


def test_rule_1_check_elsewhere_after_the_window_is_low_alone(world: World):
    shop = world.shop("Demo Lagos Shop")
    unit, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=8))

    result = world.check(token, "Abuja")

    (alert,) = world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE)
    assert alert.level == AlertLevel.LOW
    assert alert.unit_id == unit.unit_id
    assert alert.manufacturer_id == world.manufacturer.company_id
    assert alert.evidence["explanation"].startswith("Checked in Abuja at ")
    assert "8 hours after it was recorded as sold in Lagos." in alert.evidence["explanation"]
    evidence_ok(alert)
    # LOW is dashboard only.
    assert result.result == CheckResult.RECOGNISED_PREVIOUSLY_SOLD
    assert result.possible_patterns == []


def test_rule_1_is_medium_when_the_unit_has_another_open_alert(world: World):
    shop = world.shop("Demo Lagos Shop")
    unit, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=8))
    world.db.add(
        RiskAlert(
            rule=R.R5_POS_UNAVAILABLE_UNIT,
            level=AlertLevel.MEDIUM,
            manufacturer_id=world.manufacturer.company_id,
            unit_id=unit.unit_id,
            evidence={"explanation": "Earlier alert"},
        )
    )
    world.db.flush()

    world.check(token, "Abuja")

    (alert,) = world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE)
    assert alert.level == AlertLevel.MEDIUM


def test_rule_1_is_medium_when_another_rule_fires_on_the_same_check(world: World):
    shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=8))
    busy = risk.Thresholds(**{**TH.__dict__, "scan_volume": 1})
    world.check(token, "Lagos", th=busy)

    world.check(token, "Abuja", th=busy)

    assert world.alerts(R.R3_SCAN_VOLUME)
    (alert,) = world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE)
    assert alert.level == AlertLevel.MEDIUM


def test_rule_2_sold_in_lagos_then_checked_in_kano_three_hours_later(world: World):
    shop = world.shop("Demo Lagos Shop")
    unit, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=3))

    result = world.check(token, "Kano")

    (alert,) = world.alerts(R.R2_IMPOSSIBLE_TRAVEL)
    assert alert.level == AlertLevel.HIGH
    assert alert.evidence["explanation"].startswith("Seen in Lagos at ")
    assert " and in Kano at " in alert.evidence["explanation"]
    assert " km apart in 3 h 0 min (about " in alert.evidence["explanation"]
    assert alert.evidence["snapshot"][0]["from"]["what"] == "sale"
    assert len(alert.evidence["event_ids"]) == 1 and len(alert.evidence["scan_ids"]) == 1
    # Within the just-sold window, so not rule 1.
    assert world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE) == []
    # HIGH reaches the consumer at once, with the approved pattern line.
    assert result.result == CheckResult.SUSPICIOUS_ACTIVITY
    assert result.possible_patterns == [check_service.PATTERNS[R.R2_IMPOSSIBLE_TRAVEL]]


def test_rule_2_words_a_speed_above_1000_kmh(world: World):
    shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(minutes=5))

    world.check(token, "Kano")

    (alert,) = world.alerts(R.R2_IMPOSSIBLE_TRAVEL)
    assert alert.evidence["explanation"].endswith("(faster than 1,000 km/h).")


def test_rule_2_needs_an_implausible_speed(world: World):
    shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=10))

    world.check(token, "Kano")  # about 830 km in 10 hours: driveable

    assert world.alerts(R.R2_IMPOSSIBLE_TRAVEL) == []


def test_rule_3_more_than_ten_checks_in_24_hours(world: World):
    _, token = world.unit()
    now = utc_now()
    for minute in range(10):
        result = world.check(token, "Lagos", at=now + timedelta(minutes=minute))
    assert world.alerts(R.R3_SCAN_VOLUME) == []
    assert result.result == CheckResult.RECOGNISED_NOT_SOLD

    result = world.check(token, "Lagos", at=now + timedelta(minutes=11))

    (alert,) = world.alerts(R.R3_SCAN_VOLUME)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.evidence["explanation"] == (
        "Checked 11 times in 24 hours (alert threshold: 10 checks)."
    )
    assert result.result == CheckResult.SUSPICIOUS_ACTIVITY


def test_rule_4_burst_of_invalid_codes_is_admin_only(world: World):
    now = utc_now()
    for second in range(19):
        world.check(identity.new_token(), "Kano", at=now + timedelta(seconds=second))
    assert world.alerts(R.R4_INVALID_BURST) == []

    world.check(identity.new_token(), "Kano", at=now + timedelta(seconds=30))
    world.check(identity.new_token(), "Kano", at=now + timedelta(seconds=31))

    (alert,) = world.alerts(R.R4_INVALID_BURST)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.unit_id is None and alert.manufacturer_id is None
    assert alert.area_id == f.area(world.db, "Kano").area_id
    assert alert.evidence["occurrences"] == 2
    assert alert.evidence["explanation"] == (
        "21 unrecognised codes were checked from Kano within 10 minutes."
    )
    # Another area keeps its own count.
    world.check(identity.new_token(), "Lagos", at=now + timedelta(seconds=32))
    assert len(world.alerts(R.R4_INVALID_BURST)) == 1


def test_rule_6_unreleased_pack_checked(world: World):
    _, token = world.unit(status=S.ISSUED)

    result = world.check(token, "Lagos")

    (alert,) = world.alerts(R.R6_UNRELEASED_SCANNED)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.evidence["explanation"] == (
        "Checked by a consumer in Lagos before the manufacturer released it for sale."
    )
    assert result.result == CheckResult.SUSPICIOUS_ACTIVITY
    assert check_service.PATTERNS[R.R6_UNRELEASED_SCANNED] in result.possible_patterns


def test_rule_7_two_companies_receive_with_no_transfer(world: World):
    distributor = world.shop("Demo Distribution", is_retailer=False, is_distributor=True)
    shop = world.shop("Demo Kano Shop", city="Kano")
    unit, token = world.unit()
    world.event(distributor, token, E.RECEIVED, at=utc_now() - timedelta(days=2))

    world.event(shop, token, E.RECEIVED)

    (alert,) = world.alerts(R.R7_CUSTODY_CONFLICT)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.evidence["explanation"].startswith(
        "Demo Kano Shop recorded receiving this pack with no transfer from Demo Distribution, "
        "which recorded receiving it on "
    )
    assert len(alert.evidence["event_ids"]) == 2
    evidence_ok(alert)


def test_rule_7_not_raised_after_a_transfer(world: World):
    distributor = world.shop("Demo Distribution", is_retailer=False, is_distributor=True)
    shop = world.shop("Demo Kano Shop", city="Kano")
    _, token = world.unit()
    world.event(distributor, token, E.RECEIVED, at=utc_now() - timedelta(days=2))
    world.event(
        distributor,
        token,
        E.TRANSFERRED,
        at=utc_now() - timedelta(days=1),
        to_company_id=shop.company_id,
    )

    world.event(shop, token, E.RECEIVED)
    world.event(shop, token, E.SOLD)

    assert world.alerts(R.R7_CUSTODY_CONFLICT) == []


def test_rule_8_voided_pack_code_in_use(world: World):
    unit, token = world.unit(status=S.VOIDED)

    result = world.check(token, "Lagos")

    (alert,) = world.alerts(R.R8_VOIDED_CODE_IN_USE)
    assert alert.level == AlertLevel.HIGH
    assert alert.unit_id == unit.unit_id
    assert alert.evidence["explanation"] == (
        "A voided code was checked in Lagos: possible leaked label file."
    )
    assert result.result == CheckResult.INVALID_IDENTITY


def test_rule_8_voided_carton_code_in_use(world: World):
    carton, token, _ = world.carton(status=S.VOIDED)

    world.check(token, "Lagos")
    world.check(token, "Lagos")

    (alert,) = world.alerts(R.R8_VOIDED_CODE_IN_USE)
    assert alert.carton_id == carton.carton_id and alert.unit_id is None
    assert alert.level == AlertLevel.HIGH
    assert alert.evidence["occurrences"] == 2


def test_rule_9_unallocated_area_counts_as_zero_and_stays_off_the_consumer_result(world: World):
    f.make_allocation(world.db, world.batch, world.owner, quantity=5)  # Lagos
    _, token = world.unit()

    result = world.check(token, "Kano")

    (alert,) = world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.batch_id == world.batch.batch_id
    assert alert.area_id == f.area(world.db, "Kano").area_id
    assert alert.unit_id is None
    assert alert.evidence["explanation"] == (
        "More units seen in Kano than were allocated there: possible counterfeit or unauthorised "
        "supply. (1 seen, 0 allocated.)"
    )
    assert result.result == CheckResult.RECOGNISED_NOT_SOLD
    assert result.possible_patterns == []


def test_rule_9_allows_the_overage_and_counts_units_allocated_elsewhere(world: World):
    lagos = f.area(world.db, "Lagos").area_id
    kano = f.area(world.db, "Kano").area_id
    f.make_allocation(world.db, world.batch, world.owner, destination_area_id=lagos, quantity=10)
    f.make_allocation(world.db, world.batch, world.owner, destination_area_id=kano, quantity=5)
    tokens = [world.unit()[1] for _ in range(12)]

    for token in tokens[:11]:  # 11 seen, 10 allocated: within the 10% overage
        world.check(token, "Lagos")
    assert world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED) == []

    world.check(tokens[11], "Lagos")  # 12 > 11

    (alert,) = world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED)
    assert "(12 seen, 10 allocated.)" in alert.evidence["explanation"]
    # Rechecking a pack already counted adds nothing.
    world.check(tokens[0], "Lagos")
    assert world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED)[0].evidence["occurrences"] == 1


def test_rule_9_counts_sales_and_skips_a_batch_without_allocations(world: World):
    shop = world.shop("Demo Kano Shop", city="Kano")
    _, token = world.unit()
    world.event(shop, token, E.SOLD)
    assert world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED) == []  # no allocations at all

    f.make_allocation(world.db, world.batch, world.owner, quantity=5)  # Lagos only
    _, second = world.unit()
    world.event(shop, second, E.SOLD)

    (alert,) = world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED)
    assert "(2 seen, 0 allocated.)" in alert.evidence["explanation"]


def test_rule_9_never_reaches_the_consumer_even_when_open(world: World):
    f.make_allocation(world.db, world.batch, world.owner, quantity=5)
    unit, token = world.unit()
    world.check(token, "Kano")
    alert = world.alerts(R.R9_MORE_OBSERVED_THAN_ALLOCATED)[0]
    alert.unit_id = unit.unit_id  # even pointed at the pack, rule 9 never counts
    alert.level = AlertLevel.HIGH
    world.db.add(alert)
    world.db.flush()

    result = world.check(token, "Kano")

    assert result.result != CheckResult.SUSPICIOUS_ACTIVITY


# --- Never an alert --------------------------------------------------------------------------


def test_no_alert_for_a_buyer_rescanning_in_the_same_area_within_the_window(world: World):
    shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(shop, token, E.SOLD)

    for _ in range(3):
        result = world.check(token, "Lagos")

    assert world.alerts() == []
    assert result.result == CheckResult.RECOGNISED_JUST_SOLD


def test_a_returned_sale_is_ignored(world: World):
    lagos_shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(lagos_shop, token, E.SOLD, at=utc_now() - timedelta(hours=9))
    world.event(lagos_shop, token, E.RETURNED, at=utc_now() - timedelta(hours=8))

    result = world.check(token, "Abuja")  # no rule 1 and no rule 2 from the returned sale

    assert world.alerts() == []
    assert result.result == CheckResult.RECOGNISED_NOT_SOLD


def test_no_alert_for_a_returned_units_resale_and_checks(world: World):
    lagos_shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(lagos_shop, token, E.SOLD, at=utc_now() - timedelta(hours=9))
    world.event(lagos_shop, token, E.RETURNED, at=utc_now() - timedelta(hours=8))

    world.event(lagos_shop, token, E.SOLD)
    result = world.check(token, "Lagos")
    world.check(token, "Lagos")

    assert world.alerts() == []
    assert result.result == CheckResult.RECOGNISED_JUST_SOLD


def test_no_alert_for_a_sale_correction(world: World):
    shop = world.shop("Demo Lagos Shop")
    other = world.shop("Demo Abuja Shop", city="Abuja")
    _, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=9))
    world.event(shop, token, E.SALE_CORRECTED, at=utc_now() - timedelta(hours=8), reason="Typo")

    world.check(token, "Abuja")
    world.event(other, token, E.SOLD)  # the corrected sale no longer counts for custody

    assert world.alerts() == []


def test_no_alert_for_carton_moves(world: World):
    distributor = world.shop("Demo Distribution", is_retailer=False, is_distributor=True)
    shop = world.shop("Demo Kano Shop", city="Kano")
    _, token, _ = world.carton()

    world.event(distributor, token, E.RECEIVED)
    world.event(shop, token, E.RECEIVED)  # no transfer, but carton events run no rules

    assert world.alerts() == []


def test_no_alert_for_a_receipt_outside_its_allocation(world: World):
    f.make_allocation(world.db, world.batch, world.owner, quantity=1)  # Lagos
    shop = world.shop("Demo Kano Shop", city="Kano")
    _, token = world.unit()

    world.event(shop, token, E.RECEIVED)

    assert world.alerts() == []


# --- De-duplication and evidence -------------------------------------------------------------


def test_a_second_trigger_appends_to_the_open_alert(world: World):
    _, token = world.unit(status=S.ISSUED)
    world.check(token, "Lagos")

    world.check(token, "Kano")

    (alert,) = world.alerts(R.R6_UNRELEASED_SCANNED)
    assert alert.evidence["occurrences"] == 2
    assert len(alert.evidence["scan_ids"]) == 2
    assert len(alert.evidence["snapshot"]) == 2
    assert alert.evidence["explanation"].startswith("Checked by a consumer in Kano")


def test_a_second_trigger_can_raise_the_level(world: World):
    shop = world.shop("Demo Lagos Shop")
    unit, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=8))
    world.check(token, "Abuja")
    assert world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE)[0].level == AlertLevel.LOW
    world.db.add(
        RiskAlert(
            rule=R.R5_POS_UNAVAILABLE_UNIT,
            level=AlertLevel.MEDIUM,
            manufacturer_id=world.manufacturer.company_id,
            unit_id=unit.unit_id,
            evidence={"explanation": "Earlier alert"},
        )
    )
    world.db.flush()

    world.check(token, "Abuja")

    (alert,) = world.alerts(R.R1_SCAN_AFTER_SALE_ELSEWHERE)
    assert alert.level == AlertLevel.MEDIUM
    assert alert.evidence["occurrences"] == 2


def test_a_resolved_alert_does_not_absorb_new_evidence(world: World):
    _, token = world.unit(status=S.ISSUED)
    world.check(token, "Lagos")
    first = world.alerts(R.R6_UNRELEASED_SCANNED)[0]
    first.status = AlertStatus.RESOLVED_LEGITIMATE
    world.db.add(first)
    world.db.flush()

    world.check(token, "Lagos")

    assert len(world.alerts(R.R6_UNRELEASED_SCANNED)) == 2


def test_the_evidence_snapshot_survives_the_scan_purge(world: World):
    shop = world.shop("Demo Lagos Shop")
    _, token = world.unit()
    world.event(shop, token, E.SOLD, at=utc_now() - timedelta(hours=3))
    world.check(token, "Kano")
    alert = world.alerts(R.R2_IMPOSSIBLE_TRAVEL)[0]

    deleted = purge_scans(world.db, now=utc_now() + timedelta(days=366))

    assert deleted >= 1
    assert world.db.exec(select(ScanEvent)).all() == []
    world.db.expire_all()
    kept = world.db.get(RiskAlert, alert.alert_id)
    assert kept.evidence["snapshot"][0]["from"]["area"] == "Lagos"
    assert kept.evidence["snapshot"][0]["to"]["area"] == "Kano"
    assert "Seen in Lagos" in kept.evidence["explanation"]


def test_the_purge_keeps_recent_scans(world: World):
    _, token = world.unit()
    world.check(token, "Lagos")

    assert purge_scans(world.db) == 0
    assert len(world.db.exec(select(ScanEvent)).all()) == 1


# --- Consumer result -------------------------------------------------------------------------


def test_resolved_legitimate_clears_and_suspected_copy_keeps_the_consumer_result(world: World):
    _, token = world.unit(status=S.ISSUED)
    assert world.check(token, "Lagos").result == CheckResult.SUSPICIOUS_ACTIVITY
    alert = world.alerts(R.R6_UNRELEASED_SCANNED)[0]

    alert.status = AlertStatus.RESOLVED_SUSPECTED_COPY
    world.db.add(alert)
    world.db.flush()
    copy = world.check(token, "Lagos")
    assert copy.result == CheckResult.SUSPICIOUS_ACTIVITY
    assert check_service.SUSPECTED_COPY_REVIEW in copy.possible_patterns

    for row in world.alerts():
        row.status = AlertStatus.RESOLVED_LEGITIMATE
        world.db.add(row)
    world.db.flush()
    released = world.db.get(ProductUnit, alert.unit_id)
    released.lifecycle_status = S.RELEASED
    world.db.add(released)
    world.db.flush()
    assert world.check(token, "Lagos").result == CheckResult.RECOGNISED_NOT_SOLD


def test_a_consumer_check_never_changes_the_unit(world: World):
    unit, token = world.unit(status=S.ISSUED)

    world.check(token, "Lagos")

    world.db.expire_all()
    assert world.db.get(ProductUnit, unit.unit_id).lifecycle_status == S.ISSUED


# --- POS (rule 5) ----------------------------------------------------------------------------


def test_rule_5_pos_lookups_and_sale_attempts(session: Session, make_client):
    from tests.test_pos import build_world, pos_settings

    pos = build_world(session, make_client, pos_settings())
    other = f.make_company(
        session, is_manufacturer=False, is_retailer=True, review_status="APPROVED"
    )
    elsewhere, other_token = pos.unit(
        status=S.SOLD, last_sold_company_id=other.company_id, last_sold_at=utc_now()
    )

    pos.signed("units/lookup", pos.body(code=other_token))

    (alert,) = [a for a in _alerts(session) if a.unit_id == elsewhere.unit_id]
    assert alert.rule == R.R5_POS_UNAVAILABLE_UNIT and alert.level == AlertLevel.MEDIUM
    assert alert.evidence["explanation"] == (
        "A shop till (Demo Corner Shop, till TILL-1) looked up this pack while it was sold."
    )

    # Looking up its own standing sale is not a signal (D152).
    own, own_token = pos.unit()
    pos.sell(own_token)
    pos.signed("units/lookup", pos.body(code=own_token))
    assert [a for a in _alerts(session) if a.unit_id == own.unit_id] == []

    # Any sale attempt on an unavailable pack is, even from the same shop.
    pos.sell(own_token)
    (attempt,) = [a for a in _alerts(session) if a.unit_id == own.unit_id]
    assert attempt.rule == R.R5_POS_UNAVAILABLE_UNIT
    assert "tried to sell this pack while it was sold." in attempt.evidence["explanation"]

    # Unreleased, recalled and voided packs too.
    for status, word in (
        (S.ISSUED, "not released"),
        (S.RECALLED, "recalled"),
        (S.VOIDED, "voided"),
    ):
        unit, token = pos.unit(status=status)
        pos.signed("units/lookup", pos.body(code=token))
        (found,) = [a for a in _alerts(session) if a.unit_id == unit.unit_id]
        assert found.evidence["explanation"].endswith(f"while it was {word}.")


def test_a_pos_sale_runs_the_custody_rule(session: Session, make_client):
    from tests.test_pos import build_world, pos_settings

    pos = build_world(session, make_client, pos_settings())
    distributor = f.make_company(
        session, is_manufacturer=False, is_distributor=True, review_status="APPROVED"
    )
    unit, token = pos.unit()
    f.make_event(
        session,
        unit_id=unit.unit_id,
        event_type=E.RECEIVED,
        actor_company_id=distributor.company_id,
        occurred_at=utc_now() - timedelta(days=1),
    )

    pos.sell(token)

    (alert,) = [a for a in _alerts(session) if a.unit_id == unit.unit_id]
    assert alert.rule == R.R7_CUSTODY_CONFLICT


def _alerts(db: Session) -> list[RiskAlert]:
    db.expire_all()
    return list(db.exec(select(RiskAlert)).all())


# --- Workflow and access ---------------------------------------------------------------------


def _open_alert(world: World) -> RiskAlert:
    _, token = world.unit(status=S.ISSUED)
    world.check(token, "Lagos")
    return world.alerts(R.R6_UNRELEASED_SCANNED)[0]


def test_staff_change_status_and_add_notes_with_who_and_when(world: World):
    alert = _open_alert(world)
    staff = f.make_user(world.db, password_hash=hash_password(PASSWORD), display_name="Ada Staff")
    f.make_member(world.db, staff, world.manufacturer, role=MemberRole.STAFF)
    client = world.signed_in(staff)
    base = f"/api/companies/{world.manufacturer.company_id}/alerts"

    listed = client.get(base).json()
    assert [a["alert_id"] for a in listed] == [str(alert.alert_id)]
    assert listed[0]["rule_name"] == "Unreleased pack checked"

    investigating = client.post(f"{base}/{alert.alert_id}/status", json={"status": "INVESTIGATING"})
    assert investigating.status_code == 200
    assert investigating.json()["resolved_at"] is None

    noted = client.post(f"{base}/{alert.alert_id}/notes", json={"body": " Asked the depot. "})
    assert noted.status_code == 200
    (note,) = noted.json()["notes"]
    assert note["author_name"] == "Ada Staff" and note["body"] == "Asked the depot."

    resolved = client.post(
        f"{base}/{alert.alert_id}/status", json={"status": "RESOLVED_LEGITIMATE"}
    ).json()
    assert resolved["status"] == "RESOLVED_LEGITIMATE"
    assert resolved["resolved_by_name"] == "Ada Staff"
    assert resolved["resolved_at"] is not None

    reopened = client.post(f"{base}/{alert.alert_id}/status", json={"status": "OPEN"}).json()
    assert reopened["resolved_by_name"] is None and reopened["resolved_at"] is None

    changes = world.db.exec(
        select(AuditLog).where(
            AuditLog.entity_id == alert.alert_id, AuditLog.action == "change_status"
        )
    ).all()
    assert len(changes) == 3
    assert all(c.actor_user_id == staff.user_id for c in changes)

    detail = client.get(f"{base}/{alert.alert_id}").json()
    assert detail["snapshot"] and detail["explanation"]


def test_blank_notes_and_invalid_changes_are_refused(world: World):
    alert = _open_alert(world)
    client = world.signed_in(world.owner)
    base = f"/api/companies/{world.manufacturer.company_id}/alerts/{alert.alert_id}"

    blank = client.post(f"{base}/notes", json={"body": "   "})
    assert blank.status_code == 422
    assert blank.json()["detail"] == "Write a note first."

    same = client.post(f"{base}/status", json={"status": "OPEN"})
    assert same.status_code == 409
    assert same.json()["detail"] == "This status change isn't allowed."


def test_reopening_clashes_with_a_newer_open_alert(world: World):
    _, token = world.unit(status=S.ISSUED)
    world.check(token, "Lagos")
    old = world.alerts(R.R6_UNRELEASED_SCANNED)[0]
    client = world.signed_in(world.owner)
    base = f"/api/companies/{world.manufacturer.company_id}/alerts"
    client.post(f"{base}/{old.alert_id}/status", json={"status": "RESOLVED_LEGITIMATE"})
    world.check(token, "Lagos")  # opens a new rule 6 alert

    response = client.post(f"{base}/{old.alert_id}/status", json={"status": "OPEN"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Another open alert already covers this rule and pack."


def test_another_company_cannot_read_or_change_alerts(world: World):
    alert = _open_alert(world)
    rival = f.make_company(world.db, review_status=CompanyReviewStatus.APPROVED)
    user = f.make_user(world.db, password_hash=hash_password(PASSWORD))
    f.make_member(world.db, user, rival)
    client = world.signed_in(user)
    own = f"/api/companies/{rival.company_id}/alerts"
    theirs = f"/api/companies/{world.manufacturer.company_id}/alerts"

    assert client.get(own).json() == []
    assert client.get(f"{own}/{alert.alert_id}").status_code == 404
    assert (
        client.post(f"{own}/{alert.alert_id}/status", json={"status": "INVESTIGATING"}).status_code
        == 404
    )
    assert client.post(f"{own}/{alert.alert_id}/notes", json={"body": "x"}).status_code == 404
    assert client.get(theirs).status_code == 403
    assert client.get("/api/admin/alerts").status_code == 403
    world.db.expire_all()
    assert world.db.get(RiskAlert, alert.alert_id).status == AlertStatus.OPEN


def test_admins_see_every_alert_including_rule_4(world: World):
    alert = _open_alert(world)
    now = utc_now()
    for second in range(20):
        world.check(identity.new_token(), "Kano", at=now + timedelta(seconds=second))
    admin = f.make_user(world.db, is_admin=True, password_hash=hash_password(PASSWORD))
    client = world.signed_in(admin)

    listed = client.get("/api/admin/alerts").json()

    rules = {a["rule"] for a in listed}
    assert {"R6_UNRELEASED_SCANNED", "R4_INVALID_BURST"} <= rules
    burst = next(a for a in listed if a["rule"] == "R4_INVALID_BURST")
    assert burst["manufacturer_name"] is None and burst["area"] == "Kano"
    # The manufacturer never sees the admin-only burst.
    owner = world.signed_in(world.owner)
    mine = owner.get(f"/api/companies/{world.manufacturer.company_id}/alerts").json()
    assert [a["alert_id"] for a in mine] == [str(alert.alert_id)]

    changed = client.post(
        f"/api/admin/alerts/{burst['alert_id']}/status", json={"status": "INVESTIGATING"}
    )
    assert changed.status_code == 200


def test_status_filters(world: World):
    alert = _open_alert(world)
    client = world.signed_in(world.owner)
    base = f"/api/companies/{world.manufacturer.company_id}/alerts"
    client.post(f"{base}/{alert.alert_id}/status", json={"status": "RESOLVED_SUSPECTED_COPY"})

    assert client.get(base).json() == []
    assert len(client.get(f"{base}?status=RESOLVED").json()) == 1
    assert len(client.get(f"{base}?status=ALL").json()) == 1
    assert client.get(f"{base}?status=BOGUS").status_code == 422


def test_dashboard_wording_avoids_banned_words():
    import re

    banned = re.compile(
        r"\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac", re.I
    )
    from app.services import alerts

    texts = list(risk.RULE_NAMES.values())
    texts += [v for k, v in vars(alerts).items() if k.startswith("MSG_")]
    assert not [t for t in texts if banned.search(t)]


def test_unused_ids_are_not_found(world: World):
    client = world.signed_in(world.owner)
    response = client.get(f"/api/companies/{world.manufacturer.company_id}/alerts/{uuid.uuid4()}")
    assert response.status_code == 404
