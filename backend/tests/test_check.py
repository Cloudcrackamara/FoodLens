"""Consumer check and concern reports (D115, D116, D118-D120, D138, D140, D141, D144).

Units are built with factories, and `last_sold_*` and `lifecycle_status` are set directly to the
values services/lifecycle.py would derive (merchant and POS events arrive in Phases 4-5).
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import Settings
from app.models import (
    Area,
    Company,
    ConsumerReport,
    LifecycleEvent,
    Product,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    RateLimitDaily,
    RiskAlert,
    ScanEvent,
)
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    AnnouncementKind,
    CheckResult,
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    RateLimitBucket,
    RiskRule,
)
from app.routers.check import current_time
from app.schemas.check import COPY_HELP
from app.services import identity, location
from tests import factories as f

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
WINDOW = timedelta(hours=6)
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
BANNED = re.compile(
    r"\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac", re.I
)


@dataclass
class World:
    db: Session
    manufacturer: Company
    retailer: Company
    batch: ProductBatch
    user_id: object

    def unit(self, **overrides) -> tuple[ProductUnit, str]:
        token = identity.new_token()
        values = {"qr_token_hash": identity.token_hash(token), "lifecycle_status": "RELEASED"}
        return f.make_unit(self.db, self.batch, **(values | overrides)), token

    def sold(self, at: datetime, city: str = "Lagos", **overrides) -> tuple[ProductUnit, str]:
        return self.unit(
            lifecycle_status=LifecycleStatus.SOLD,
            current_holder_company_id=self.retailer.company_id,
            last_sold_at=at,
            last_sold_area_id=f.area(self.db, city).area_id,
            last_sold_company_id=self.retailer.company_id,
            **overrides,
        )

    def alert(self, unit: ProductUnit, **overrides) -> RiskAlert:
        values = {
            "rule": RiskRule.R2_IMPOSSIBLE_TRAVEL,
            "level": AlertLevel.HIGH,
            "manufacturer_id": self.manufacturer.company_id,
            "unit_id": unit.unit_id,
        }
        alert = RiskAlert(**(values | overrides))
        self.db.add(alert)
        self.db.flush()
        return alert

    def recall(self, batch_id=None) -> ProductAnnouncement:
        announcement = ProductAnnouncement(
            kind=AnnouncementKind.RECALL,
            product_id=self.batch.product_id,
            batch_id=batch_id,
            recall_reason="Labelling error on a demo batch",
            title="Recall of demo lot",
            message="Please return this demo lot to the shop where you bought it.",
            created_by_user_id=self.user_id,
        )
        self.db.add(announcement)
        self.db.flush()
        return announcement


@pytest.fixture
def world(session: Session) -> World:
    manufacturer = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    retailer = f.make_company(
        session,
        is_manufacturer=False,
        is_retailer=True,
        display_name="Demo Corner Shop",
        review_status=CompanyReviewStatus.APPROVED,
    )
    product = f.make_product(session, manufacturer, size="1 L", registration_number="DEMO-01-2345")
    batch = f.make_batch(session, product, expiry_date=date(2027, 6, 30))
    user = f.make_user(session)
    return World(session, manufacturer, retailer, batch, user.user_id)


@pytest.fixture
def api(make_client: Callable[..., TestClient]) -> Callable[..., TestClient]:
    def build(**settings_overrides) -> TestClient:
        ip = settings_overrides.pop("ip", "testclient")
        settings = Settings(rate_limit_enabled=False, **settings_overrides)
        client = make_client(settings=settings, client_ip=ip)
        client.app.dependency_overrides[current_time] = lambda: NOW
        return client

    return build


def check(client: TestClient, code: str, kind: str = "QR", **extra) -> dict:
    response = client.post("/api/check/qr", json={"code": code, "identifier_type": kind, **extra})
    assert response.status_code == 200, response.text
    return response.json()


# --- Results ---------------------------------------------------------------------------------


def test_never_sold_unit_is_in_circulation_with_the_pay_tip(world: World, api):
    _, token = world.unit()

    body = check(api(), token)

    assert body["result"] == CheckResult.RECOGNISED_NOT_SOLD
    assert body["title"] == "In circulation, not yet sold"
    assert body["message"] == "This code was issued by Demo Harvest Foods and is in circulation."
    assert body["tip"] == (
        "Scan again after you pay. It should show this item as just sold by the shop."
    )
    assert body["can_note_purchase"] is True
    assert body["sale"] is None
    assert body["subject"] == "PACK"
    assert body["code_last4"] == token[-4:]
    assert body["product"] == {
        "name": "Sample Palm Oil",
        "brand": "Demo Harvest",
        "size": "1 L",
        "manufacturer_name": "Demo Harvest Foods",
        "registration_number": "DEMO-01-2345",
    }
    assert body["batch"] == {
        "batch_number": "DEMO-LOT-001",
        "expiry_date": "2027-06-30",
        "expired": False,
    }
    assert body["copy_help"] == COPY_HELP


def test_sale_exactly_at_the_window_edge_is_just_sold(world: World, api):
    _, token = world.sold(NOW - WINDOW, city="Kano")

    body = check(api(), token)

    assert body["result"] == CheckResult.RECOGNISED_JUST_SOLD
    assert body["message"] == (
        "Just sold by Demo Corner Shop, Kano, at 07:00 on 26 Oct 2026 (Nigeria time). "
        "If that was your purchase, this matches."
    )
    assert body["just_sold_window_hours"] == 6
    assert body["tip"] == "Sales recorded in the last 6 hours show as just sold."
    assert body["sale"]["retailer_name"] == "Demo Corner Shop"
    assert body["can_note_purchase"] is False


def test_sale_one_second_older_than_the_window_is_previously_sold(world: World, api):
    _, token = world.sold(NOW - WINDOW - timedelta(seconds=1))

    body = check(api(), token)

    assert body["result"] == CheckResult.RECOGNISED_PREVIOUSLY_SOLD
    assert body["message"] == "This code was already recorded as sold on 26 Oct 2026 in Lagos."
    assert "ask the seller" in body["advice"]
    assert body["can_report"] is True


def test_window_follows_the_setting(world: World, api):
    _, token = world.sold(NOW - timedelta(hours=7))

    assert check(api(just_sold_window_hours=8), token)["result"] == "RECOGNISED_JUST_SOLD"


def test_returned_unit_shows_in_circulation_not_yet_sold(world: World, api):
    unit, token = world.unit(
        lifecycle_status=LifecycleStatus.IN_STOCK,
        current_holder_company_id=world.retailer.company_id,
    )
    common = {"unit_id": unit.unit_id, "actor_company_id": world.retailer.company_id}
    sold = f.make_event(
        world.db,
        event_type=LifecycleEventType.SOLD,
        source=EventSource.MERCHANT_APP,
        occurred_at=NOW - timedelta(days=2),
        **common,
    )
    f.make_event(
        world.db,
        event_type=LifecycleEventType.RETURNED,
        source=EventSource.MERCHANT_APP,
        occurred_at=NOW - timedelta(days=1),
        returns_event_id=sold.event_id,
        **common,
    )

    body = check(api(), token)

    assert body["result"] == CheckResult.RECOGNISED_NOT_SOLD
    assert body["title"] == "In circulation, not yet sold"
    # The sale stays in the record.
    assert any(
        fact.startswith("Recorded as sold by Demo Corner Shop") for fact in body["recorded_facts"]
    )
    assert any(fact.startswith("Recorded as returned") for fact in body["recorded_facts"])


def test_recall_for_the_product_or_batch_is_the_main_result(world: World, api):
    _, token = world.sold(NOW - timedelta(hours=1))
    world.recall(batch_id=world.batch.batch_id)

    body = check(api(), token)

    assert body["result"] == CheckResult.BATCH_OR_PRODUCT_WARNING
    assert body["title"] == "Recall posted for this product"
    assert body["notices"][0]["kind"] == "RECALL"
    assert body["notices"][0]["label"] == "Message from the company — not reviewed by FoodLens"


def test_recall_of_another_batch_does_not_apply(world: World, api):
    product = world.db.get(Product, world.batch.product_id)
    other_batch = f.make_batch(world.db, product, batch_number="DEMO-LOT-002")
    world.recall(batch_id=other_batch.batch_id)
    _, token = world.unit()

    assert check(api(), token)["result"] == CheckResult.RECOGNISED_NOT_SOLD


def test_recalled_unit_status_gives_the_warning(world: World, api):
    _, token = world.unit(lifecycle_status=LifecycleStatus.RECALLED)

    assert check(api(), token)["result"] == CheckResult.BATCH_OR_PRODUCT_WARNING


@pytest.mark.parametrize(
    ("level", "status", "rule", "suspicious"),
    [
        (AlertLevel.HIGH, AlertStatus.OPEN, RiskRule.R2_IMPOSSIBLE_TRAVEL, True),
        (AlertLevel.MEDIUM, AlertStatus.INVESTIGATING, RiskRule.R3_SCAN_VOLUME, True),
        (AlertLevel.LOW, AlertStatus.OPEN, RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE, False),
        (AlertLevel.HIGH, AlertStatus.RESOLVED_LEGITIMATE, RiskRule.R2_IMPOSSIBLE_TRAVEL, False),
        (
            AlertLevel.LOW,
            AlertStatus.RESOLVED_SUSPECTED_COPY,
            RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE,
            True,
        ),
    ],
)
def test_suspicious_activity_comes_from_alerts(world: World, api, level, status, rule, suspicious):
    unit, token = world.sold(NOW - timedelta(hours=1))
    world.alert(unit, level=level, status=status, rule=rule)

    body = check(api(), token)

    expected = "SUSPICIOUS_ACTIVITY" if suspicious else "RECOGNISED_JUST_SOLD"
    assert body["result"] == expected
    assert bool(body["possible_patterns"]) is suspicious


def test_rule_9_alert_is_never_consumer_facing(world: World, api):
    unit, token = world.unit()
    world.alert(
        unit,
        rule=RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
        level=AlertLevel.MEDIUM,
        batch_id=world.batch.batch_id,
        area_id=f.area(world.db).area_id,
    )

    assert check(api(), token)["result"] == CheckResult.RECOGNISED_NOT_SOLD


def test_suspicious_overrides_a_recall_and_keeps_it_as_a_warning(world: World, api):
    unit, token = world.unit()
    world.alert(unit)
    world.recall()

    body = check(api(), token)

    assert body["result"] == CheckResult.SUSPICIOUS_ACTIVITY
    assert body["title"] == "This code may have been copied"
    assert body["possible_patterns"] == [
        "Checked in places too far apart for the time between checks."
    ]
    assert "The manufacturer has posted a recall that covers this pack." in body["warnings"]


def test_unknown_scanned_code_is_invalid(api, world):
    body = check(api(), identity.new_token())

    assert body["result"] == CheckResult.INVALID_IDENTITY
    assert body["title"] == "Code not recognised"
    assert body["product"] is None
    assert body["can_report"] is True


def test_unknown_typed_code_gets_the_neutral_copy(api, world):
    body = check(api(), "ABCD EFGH JKMN PQRS TVWX YZ", kind="TYPED")

    assert body["result"] == CheckResult.INVALID_IDENTITY
    assert body["title"] == "We couldn't find that code"
    assert body["message"] == "Check you typed it correctly, or scan the QR."
    assert body["code_last4"] == "WXYZ"


def test_voided_code_is_invalid(world: World, api):
    _, token = world.unit(lifecycle_status=LifecycleStatus.VOIDED)

    assert check(api(), token)["result"] == CheckResult.INVALID_IDENTITY


@pytest.mark.parametrize(
    "status",
    [
        CompanyReviewStatus.PENDING_REVIEW,
        CompanyReviewStatus.SUSPENDED,
        CompanyReviewStatus.REJECTED,
    ],
)
def test_code_from_an_unapproved_manufacturer_is_invalid(world: World, api, status):
    _, token = world.unit()
    world.manufacturer.review_status = status
    world.db.add(world.manufacturer)
    world.db.flush()

    assert check(api(), token)["result"] == CheckResult.INVALID_IDENTITY


def test_carton_code_asks_for_the_individual_pack(world: World, api):
    token = identity.new_token()
    f.make_carton(
        world.db, world.batch, world.manufacturer, qr_token_hash=identity.token_hash(token)
    )

    body = check(api(), token)

    assert body["result"] == CheckResult.CARTON_CODE
    assert body["subject"] == "CARTON"
    assert body["title"] == "This is a carton code"
    assert body["message"] == "This is a carton code; check the individual pack."
    assert body["tip"] is None
    assert body["can_note_purchase"] is False


def test_carton_scans_are_logged_apart_from_pack_checks(world: World, api):
    """CARTON_CODE in the scan log, with the carton and no unit, even under a recall (D148)."""
    plain, recalled = identity.new_token(), identity.new_token()
    for token in (plain, recalled):
        f.make_carton(
            world.db, world.batch, world.manufacturer, qr_token_hash=identity.token_hash(token)
        )
    client = api()

    check(client, plain)
    world.recall()
    body = check(client, recalled)

    assert body["result"] == CheckResult.BATCH_OR_PRODUCT_WARNING
    assert "This is a carton code; check the individual pack." in body["warnings"]
    scans = world.db.exec(select(ScanEvent)).all()
    assert [(s.result, s.unit_id is None, s.carton_id is not None) for s in scans] == [
        (CheckResult.CARTON_CODE, True, True)
    ] * 2


def test_voided_carton_is_invalid_and_logged_as_invalid(world: World, api):
    token = identity.new_token()
    f.make_carton(
        world.db,
        world.batch,
        world.manufacturer,
        qr_token_hash=identity.token_hash(token),
        lifecycle_status=LifecycleStatus.VOIDED,
    )

    assert check(api(), token)["result"] == CheckResult.INVALID_IDENTITY
    assert world.db.exec(select(ScanEvent)).one().result == CheckResult.INVALID_IDENTITY


def test_typed_code_is_normalised(world: World, api):
    token = "7Q2M8KD3XH4N0P1R5S6T9V0W1Y"
    world.unit(qr_token_hash=identity.token_hash(token))
    typed = "7q2m-8kd3 xh4n oP1r 5s6t 9vOw ly"  # O for 0, l for 1, hyphens and spaces

    body = check(api(), typed, kind="TYPED")

    assert body["result"] == CheckResult.RECOGNISED_NOT_SOLD
    assert body["code_last4"] == "0W1Y"


def test_expired_batch_adds_a_warning(world: World, api):
    world.batch.expiry_date = date(2026, 10, 1)
    world.db.add(world.batch)
    world.db.flush()
    _, token = world.unit()

    body = check(api(), token)

    assert body["batch"]["expired"] is True
    assert body["warnings"] == ["The expiry date of this batch (1 Oct 2026) has passed."]


# --- A check changes nothing ------------------------------------------------------------------


def _unit_state(db: Session, unit: ProductUnit) -> tuple:
    db.expire_all()
    row = db.get(ProductUnit, unit.unit_id)
    events = db.exec(
        select(func.count())
        .select_from(LifecycleEvent)
        .where(LifecycleEvent.unit_id == unit.unit_id)
    ).one()
    return (
        row.lifecycle_status,
        row.current_holder_company_id,
        row.last_sold_at,
        row.last_sold_area_id,
        row.last_sold_company_id,
        row.updated_at,
        events,
    )


def test_a_check_never_changes_status_or_sale(world: World, api):
    client = api()
    cases = [
        world.unit(),
        world.sold(NOW - timedelta(hours=1)),
        world.sold(NOW - timedelta(days=3)),
        world.unit(lifecycle_status=LifecycleStatus.VOIDED),
        world.unit(lifecycle_status=LifecycleStatus.ISSUED),
    ]
    world.alert(cases[1][0])
    for unit, token in cases:
        before = _unit_state(world.db, unit)
        for kind in ("QR", "TYPED"):
            check(client, token, kind=kind)
        assert _unit_state(world.db, unit) == before

    scans = world.db.exec(select(func.count()).select_from(ScanEvent)).one()
    assert scans == 2 * len(cases)


def test_each_check_appends_one_anonymous_scan(world: World, api):
    unit, token = world.unit()

    check(api(), token, kind="TYPED")

    scan = world.db.exec(select(ScanEvent).where(ScanEvent.unit_id == unit.unit_id)).one()
    assert scan.identifier_type == "TYPED"
    assert scan.result == CheckResult.RECOGNISED_NOT_SOLD
    assert scan.carton_id is None


# --- Public fields only -----------------------------------------------------------------------


def _all_results(world: World, client: TestClient) -> list[dict]:
    """One response for every result and subject."""
    alerted, alerted_token = world.unit()
    world.alert(alerted)
    carton_token = identity.new_token()
    f.make_carton(
        world.db, world.batch, world.manufacturer, qr_token_hash=identity.token_hash(carton_token)
    )
    tokens = [
        world.unit()[1],
        world.sold(NOW - timedelta(hours=1))[1],
        world.sold(NOW - timedelta(days=5))[1],
        world.unit(lifecycle_status=LifecycleStatus.VOIDED)[1],
        world.unit(lifecycle_status=LifecycleStatus.RECALLED)[1],
        alerted_token,
        carton_token,
        identity.new_token(),
    ]
    responses = []
    for token in tokens:
        for kind in ("QR", "TYPED"):
            responses.append((token, check(client, token, kind=kind)))
    return responses


def test_every_result_is_reachable(world: World, api):
    results = {body["result"] for _, body in _all_results(world, api())}

    assert results == {r.value for r in CheckResult}


def test_no_internal_identifier_or_full_code_in_any_response(world: World, api):
    for token, body in _all_results(world, api()):
        text = json.dumps(body)
        assert not UUID_PATTERN.search(text), text
        assert token not in text
        assert token[:-4] not in text
        assert len(body["code_last4"]) <= 4
        assert not any(key.endswith("_id") for key in _keys(body))


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_banned_words_never_appear_and_demo_label_is_always_present(world: World, api):
    for _, body in _all_results(world, api()):
        # Company messages are the company's own words; the rest is FoodLens's wording.
        foodlens_wording = {k: v for k, v in body.items() if k != "notices"}
        assert not BANNED.search(json.dumps(foodlens_wording)), foodlens_wording
        assert body["data_mode"] == "DEMO"
        assert "demonstration database" in body["disclaimer"]
        assert "It is not NAFDAC's or SON's service" in body["disclaimer"]
        assert "No QR system catches every copied code." in body["disclaimer"]
        assert "No QR system catches every copied code." in body["copy_help"]


def test_validation_errors_do_not_echo_into_a_scan(api, world):
    response = api().post("/api/check/qr", json={"code": "", "identifier_type": "QR"})

    assert response.status_code == 422
    assert world.db.exec(select(func.count()).select_from(ScanEvent)).one() == 0


# --- Privacy ----------------------------------------------------------------------------------


def test_check_sets_no_cookie(world: World, api):
    _, token = world.unit()

    response = api().post("/api/check/qr", json={"code": token, "identifier_type": "QR"})

    assert "set-cookie" not in response.headers


def test_area_from_cloudflare_headers_through_a_trusted_proxy(world: World, api):
    unit, token = world.unit()
    client = api(ip="127.0.0.1")

    client.post(
        "/api/check/qr",
        json={"code": token, "identifier_type": "QR"},
        headers={"cf-ipcity": "Kano", "x-forwarded-for": "203.0.113.77"},
    )

    scan = world.db.exec(select(ScanEvent).where(ScanEvent.unit_id == unit.unit_id)).one()
    assert scan.area_id == f.area(world.db, "Kano").area_id


def test_cloudflare_region_maps_to_a_seeded_area(world: World, api):
    unit, token = world.unit()

    api(ip="127.0.0.1").post(
        "/api/check/qr",
        json={"code": token, "identifier_type": "QR"},
        headers={"cf-region": "Federal Capital Territory"},
    )

    scan = world.db.exec(select(ScanEvent).where(ScanEvent.unit_id == unit.unit_id)).one()
    assert scan.area_id == f.area(world.db, "Abuja").area_id


def test_cloudflare_headers_from_an_untrusted_client_are_ignored(world: World, api):
    unit, token = world.unit()

    api(ip="198.51.100.4").post(
        "/api/check/qr",
        json={"code": token, "identifier_type": "QR"},
        headers={"cf-ipcity": "Kano"},
    )

    scan = world.db.exec(select(ScanEvent).where(ScanEvent.unit_id == unit.unit_id)).one()
    assert scan.area_id is None


def _scan_city(world: World, client: TestClient, picked: str | None, **headers) -> str | None:
    unit, token = world.unit()
    client.post(
        "/api/check/qr",
        json={"code": token, "identifier_type": "QR", "simulated_city": picked},
        headers=headers,
    )
    scan = world.db.exec(select(ScanEvent).where(ScanEvent.unit_id == unit.unit_id)).one()
    return world.db.get(Area, scan.area_id).city if scan.area_id else None


def test_simulated_city_only_when_enabled(world: World, api):
    assert _scan_city(world, api(), "Kano") is None
    assert _scan_city(world, api(simulate_location_enabled=True), "Kano") == "Kano"


def test_with_simulation_on_the_picked_city_wins_over_cloudflare(world: World, api):
    client = api(ip="127.0.0.1", simulate_location_enabled=True)

    assert _scan_city(world, client, "Lagos", **{"cf-ipcity": "Kano"}) == "Lagos"
    # No city picked: the real area is used as usual.
    assert _scan_city(world, client, None, **{"cf-ipcity": "Kano"}) == "Kano"


def test_with_simulation_off_cloudflare_wins_and_the_pick_is_ignored(world: World, api):
    client = api(ip="127.0.0.1")

    assert _scan_city(world, client, "Lagos", **{"cf-ipcity": "Kano"}) == "Kano"


@pytest.mark.parametrize(("simulation", "expected"), [(True, "Lagos"), (False, "Abuja")])
def test_picked_city_and_ip_lookup_order(world: World, api, monkeypatch, simulation, expected):
    monkeypatch.setattr(location, "_geoip_place", lambda path, ip: ("Abuja", "FCT"))
    client = api(geoip_db_path="demo.mmdb", simulate_location_enabled=simulation)

    assert _scan_city(world, client, "Lagos") == expected


def test_demo_cities_only_when_enabled(api, world):
    assert api().get("/api/check/demo-cities").status_code == 404

    cities = api(simulate_location_enabled=True).get("/api/check/demo-cities").json()

    assert {"city": "Kano", "state": "Kano"} in cities
    assert all(set(c) == {"city", "state"} for c in cities)


def test_no_ip_is_stored_anywhere(world: World, api):
    ip = "203.0.113.77"
    _, token = world.unit()
    client = api(ip="127.0.0.1", simulate_location_enabled=True)

    check(client, token, simulated_city="Lagos")
    client.post(
        "/api/check/report",
        json={"code": token, "concern_type": "OTHER", "description": "Seal looked different."},
        headers={"x-forwarded-for": ip},
    )

    for model in (ScanEvent, ConsumerReport, RateLimitDaily):
        for row in world.db.exec(select(model)).all():
            assert ip not in json.dumps(row.model_dump(), default=str)
            assert "127.0.0.1" not in json.dumps(row.model_dump(), default=str)


# --- Rate limit -------------------------------------------------------------------------------


def test_rate_limit_gives_429_and_counts_the_hit_by_area(world: World, make_client):
    settings = Settings(
        rate_limit_check_burst=1,
        rate_limit_check_refill_per_second=0.001,
        simulate_location_enabled=True,
    )
    client = make_client(settings=settings)
    _, token = world.unit()
    body = {"code": token, "identifier_type": "QR", "simulated_city": "Kano"}

    assert client.post("/api/check/qr", json=body).status_code == 200
    blocked = client.post("/api/check/qr", json=body)
    client.post("/api/check/qr", json=body)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    row = world.db.exec(
        select(RateLimitDaily).where(RateLimitDaily.area_id == f.area(world.db, "Kano").area_id)
    ).one()
    assert (row.bucket, row.count) == (RateLimitBucket.CHECK, 2)
    # A blocked check is not a scan.
    assert world.db.exec(select(func.count()).select_from(ScanEvent)).one() == 1


def test_reports_are_limited_to_five_per_hour(world: World, make_client):
    client = make_client(settings=Settings())
    body = {"concern_type": "OTHER", "description": "Demo concern."}

    statuses = [client.post("/api/check/report", json=body).status_code for _ in range(6)]

    assert statuses == [201] * 5 + [429]


# --- Reports ----------------------------------------------------------------------------------


def test_report_routes_to_the_manufacturer_without_storing_the_code(world: World, api):
    unit, token = world.unit()

    response = api().post(
        "/api/check/report",
        json={"code": token, "concern_type": "PREVIOUSLY_SOLD", "description": "Shop said new."},
    )

    assert response.status_code == 201
    assert response.json()["data_mode"] == "DEMO"
    assert "set-cookie" not in response.headers
    report = world.db.exec(select(ConsumerReport)).one()
    assert report.unit_id == unit.unit_id
    assert report.manufacturer_id == world.manufacturer.company_id
    assert token not in json.dumps(report.model_dump(), default=str)
    assert not UUID_PATTERN.search(response.text)


def test_report_without_a_code_is_accepted(world: World, api):
    response = api().post(
        "/api/check/report", json={"concern_type": "PACKAGING", "description": "Torn seal."}
    )

    assert response.status_code == 201
    report = world.db.exec(select(ConsumerReport)).one()
    assert (report.unit_id, report.manufacturer_id) == (None, None)


def test_report_description_is_limited(world: World, api):
    response = api().post(
        "/api/check/report", json={"concern_type": "OTHER", "description": "x" * 1001}
    )

    assert response.status_code == 422


def test_report_has_no_contact_field(api, world):
    response = api().post(
        "/api/check/report",
        json={"concern_type": "OTHER", "description": "Demo.", "phone": "08000000000"},
    )

    assert response.status_code == 201
    assert "phone" not in ConsumerReport.model_fields
