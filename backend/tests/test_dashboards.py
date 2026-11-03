"""Phase 7 backend: inventory per destination, the pack timeline, partners, consumer
reports, manufacturer and platform stats on fixed datasets, the automated-scanning panel, and
cross-company access."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AppUser,
    AuditLog,
    Company,
    ConsumerReport,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    RateLimitDaily,
    RiskAlert,
    ScanEvent,
    SupplierLocation,
)
from app.models.base import utc_now
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    AnnouncementKind,
    CheckResult,
    CompanyReviewStatus,
    ConcernType,
    EventSource,
    IdentifierType,
    LifecycleEventType,
    LifecycleStatus,
    MemberRole,
    PosLinkStatus,
    ProductStatus,
    RateLimitBucket,
    ReportStatus,
    ReviewStatus,
    RiskRule,
)
from app.services import identity, lifecycle, pos_admin, stats
from app.services.check import WAT
from tests import factories as f

PASSWORD = "correct-horse-battery"
E = LifecycleEventType
S = LifecycleStatus
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
# A Wednesday, Nigeria time. Its week starts on Monday 26 Oct 2026.
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=WAT)


@dataclass
class World:
    db: Session
    manufacturer: Company
    product: object
    batch: ProductBatch
    owner: AppUser
    make_client: object

    @property
    def cid(self):
        return self.manufacturer.company_id

    def unit(self, status=S.RELEASED, released=True, batch=None, carton=None, **overrides):
        token = identity.new_token()
        unit = f.make_unit(
            self.db,
            batch or self.batch,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            current_holder_company_id=self.cid,
            parent_carton_id=carton.carton_id if carton else None,
            **overrides,
        )
        if released:
            f.make_event(
                self.db,
                unit_id=unit.unit_id,
                event_type=E.RELEASED,
                actor_company_id=self.cid,
                occurred_at=NOW - timedelta(days=60),
            )
        return unit, token

    def carton(self, status=S.RELEASED):
        token = identity.new_token()
        carton = f.make_carton(
            self.db,
            self.batch,
            self.manufacturer,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            current_holder_company_id=self.cid,
        )
        return carton, token

    def shop(self, name="Demo Shop", city="Lagos", **flags):
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

    def event(self, member, token, event_type, **kw):
        return lifecycle.record_merchant_event(self.db, member, token, event_type, **kw)

    def scan(self, unit=None, city="Lagos", at=NOW, result=CheckResult.RECOGNISED_NOT_SOLD):
        self.db.add(
            ScanEvent(
                identifier_type=IdentifierType.QR,
                unit_id=unit.unit_id if unit else None,
                area_id=f.area(self.db, city).area_id if city else None,
                result=result,
                created_at=at,
            )
        )
        self.db.flush()

    def alert(self, rule=RiskRule.R3_SCAN_VOLUME, level=AlertLevel.MEDIUM, **values):
        values = {"manufacturer_id": self.cid, "evidence": {"explanation": "Demo"}} | values
        alert = RiskAlert(rule=rule, level=level, **values)
        self.db.add(alert)
        self.db.flush()
        return alert

    def client(self, user: AppUser) -> TestClient:
        client = self.make_client(settings=Settings(rate_limit_enabled=False))
        login = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
        assert login.status_code == 200
        return client

    def member_of(self, company, role=MemberRole.OWNER) -> AppUser:
        user = f.make_user(self.db, password_hash=hash_password(PASSWORD))
        f.make_member(self.db, user, company, role=role)
        return user

    def admin(self) -> TestClient:
        return self.client(
            f.make_user(self.db, is_admin=True, password_hash=hash_password(PASSWORD))
        )

    def rival(self) -> tuple[Company, TestClient]:
        company = f.make_company(
            self.db, display_name="Rival Foods", review_status=CompanyReviewStatus.APPROVED
        )
        return company, self.client(self.member_of(company))


@pytest.fixture
def world(session: Session, make_client) -> World:
    manufacturer = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    product = f.make_product(session, manufacturer, status=ProductStatus.PUBLISHED)
    batch = f.make_batch(session, product, review_status=ReviewStatus.APPROVED)
    owner = f.make_user(session, password_hash=hash_password(PASSWORD))
    f.make_member(session, owner, manufacturer)
    return World(session, manufacturer, product, batch, owner, make_client)


def refreshed(world: World, row):
    world.db.expire(row)
    return world.db.get(type(row), row.unit_id if isinstance(row, ProductUnit) else row.carton_id)


# --- Recalls are gone (D155) -----------------------------------------------------------------


def test_no_route_can_create_a_recall(world: World):
    client = world.client(world.owner)
    base = f"/api/companies/{world.cid}/products/{world.product.product_id}"

    assert client.post(f"{base}/recalls", json={"title": "x"}).status_code == 404
    assert client.get(f"{base}/recalls/preview").status_code == 404
    # A company notice cannot become one: the client does not set the kind.
    notice = client.post(
        f"{base}/announcements",
        json={"title": "New pack", "message": "New packaging.", "kind": "RECALL"},
    )
    assert notice.status_code == 201
    row = world.db.exec(select(ProductAnnouncement)).one()
    assert row.kind == AnnouncementKind.NOTICE


# --- Inventory (D142) ------------------------------------------------------------------------


def test_inventory_per_destination(world: World):
    lagos_shop = world.shop("Demo Lagos Shop")
    kano_shop = world.shop("Demo Kano Shop", city="Kano")
    abuja_shop = world.shop("Demo Abuja Shop", city="Abuja")
    lagos = f.area(world.db, "Lagos").area_id
    kano = f.area(world.db, "Kano").area_id
    f.make_allocation(
        world.db, world.batch, world.owner,
        destination_area_id=lagos, destination_company_id=lagos_shop.company_id, quantity=3,
    )  # fmt: skip
    f.make_allocation(
        world.db, world.batch, world.owner,
        destination_area_id=lagos, destination_company_id=lagos_shop.company_id, quantity=2,
    )  # fmt: skip
    f.make_allocation(world.db, world.batch, world.owner, destination_area_id=kano, quantity=4)

    # Lagos shop: one in stock, one sold, one returned (back in stock).
    _, stocked = world.unit()
    world.event(lagos_shop, stocked, E.RECEIVED)
    _, sold = world.unit()
    world.event(lagos_shop, sold, E.RECEIVED)
    world.event(lagos_shop, sold, E.SOLD)
    _, returned = world.unit()
    world.event(lagos_shop, returned, E.RECEIVED)
    world.event(lagos_shop, returned, E.SOLD)
    world.event(lagos_shop, returned, E.RETURNED)
    # Kano, allocated by area only: any company there counts; a transfer leaves stock.
    _, moved = world.unit()
    world.event(kano_shop, moved, E.RECEIVED)
    world.event(kano_shop, moved, E.TRANSFERRED, to_company_id=lagos_shop.company_id)
    # Abuja has no allocation.
    _, outside = world.unit()
    world.event(abuja_shop, outside, E.SOLD)
    _, outside_stock = world.unit()
    world.event(abuja_shop, outside_stock, E.RECEIVED)

    client = world.client(world.owner)
    response = client.get(f"/api/companies/{world.cid}/batches/{world.batch.batch_id}/inventory")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "company_name": None,
            "area": "Kano",
            "not_allocated": False,
            "allocated": 4,
            "received": 1,
            "in_stock": 0,
            "sold": 0,
            "returned": 0,
        },
        {
            "company_name": "Demo Lagos Shop",
            "area": "Lagos",
            "not_allocated": False,
            "allocated": 5,
            "received": 3,
            "in_stock": 2,
            "sold": 1,
            "returned": 1,
        },
        {
            "company_name": None,
            "area": None,
            "not_allocated": True,
            "allocated": 0,
            "received": 1,
            "in_stock": 1,
            "sold": 1,
            "returned": 0,
        },
    ]


def test_inventory_of_a_batch_with_no_activity_is_empty(world: World):
    client = world.client(world.owner)

    response = client.get(f"/api/companies/{world.cid}/batches/{world.batch.batch_id}/inventory")

    assert response.json() == []


def test_inventory_of_another_companys_batch_is_not_found(world: World):
    company, rival = world.rival()
    theirs = f"/api/companies/{company.company_id}/batches/{world.batch.batch_id}/inventory"
    mine = f"/api/companies/{world.cid}/batches/{world.batch.batch_id}/inventory"

    assert rival.get(theirs).status_code == 404
    assert rival.get(mine).status_code == 403


# --- Pack timeline ---------------------------------------------------------------------------


def test_the_timeline_tells_a_packs_history_in_plain_words(world: World):
    f.make_allocation(world.db, world.batch, world.owner, quantity=1)  # Lagos
    shop = world.shop("Demo Kano Shop", city="Kano")
    unit, token = world.unit()
    world.event(shop, token, E.RECEIVED)
    world.event(shop, token, E.SOLD)
    world.event(shop, token, E.RETURNED)
    alert = world.alert(unit_id=unit.unit_id)
    client = world.client(world.owner)

    response = client.post(f"/api/companies/{world.cid}/units/timeline", json={"code": token})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject"] == "PACK" and body["code_last4"] == token[-4:]
    assert body["status"] == "IN_STOCK"
    assert [e["event_type"] for e in body["entries"]] == [
        "RELEASED",
        "RECEIVED",
        "SOLD",
        "RETURNED",
    ]
    assert "Received by Demo Kano Shop in Kano" in body["entries"][1]["text"]
    assert body["entries"][1]["note"] == "Received outside its allocation."
    assert "Recorded as sold by Demo Kano Shop" in body["entries"][2]["text"]
    assert body["open_alerts"] == [
        {
            "alert_id": str(alert.alert_id),
            "rule_name": "Many checks in 24 hours",
            "level": "MEDIUM",
        }
    ]
    assert token not in response.text
    assert str(unit.unit_id) not in response.text
    assert unit.qr_token_hash not in response.text


def test_the_timeline_shows_voids_and_cartons(world: World):
    voided, token = world.unit(status=S.VOIDED, released=False)
    f.make_event(
        world.db,
        unit_id=voided.unit_id,
        event_type=E.VOIDED,
        actor_company_id=world.cid,
        reason="Label file lost",
        occurred_at=NOW,
    )
    carton, carton_token = world.carton()
    f.make_event(
        world.db,
        carton_id=carton.carton_id,
        event_type=E.RELEASED,
        actor_company_id=world.cid,
        occurred_at=NOW,
    )
    client = world.client(world.owner)
    path = f"/api/companies/{world.cid}/units/timeline"

    body = client.post(path, json={"code": token}).json()
    assert body["entries"][0]["text"].startswith("Code voided by ")

    box = client.post(path, json={"code": carton_token}).json()
    assert box["subject"] == "CARTON"
    assert box["entries"][0]["event_type"] == "RELEASED"


def test_another_companys_code_looks_unknown(world: World):
    _, token = world.unit()
    company, rival = world.rival()
    path = f"/api/companies/{company.company_id}/units/timeline"

    for code in (token, identity.new_token()):
        response = rival.post(path, json={"code": code})
        assert response.status_code == 404
        assert response.json()["detail"] == "We couldn't find that code among your packs."
    assert (
        rival.post(f"/api/companies/{world.cid}/units/timeline", json={"code": token}).status_code
        == 403
    )


def test_the_timeline_from_an_alert(world: World):
    unit, _ = world.unit()
    alert = world.alert(unit_id=unit.unit_id)
    batch_alert = world.alert(
        rule=RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
        batch_id=world.batch.batch_id,
        area_id=f.area(world.db, "Kano").area_id,
    )
    client = world.client(world.owner)
    base = f"/api/companies/{world.cid}/alerts"

    body = client.get(f"{base}/{alert.alert_id}/timeline").json()
    assert body["subject"] == "PACK" and body["code_last4"] is None
    assert client.get(f"{base}/{batch_alert.alert_id}/timeline").status_code == 404

    company, rival = world.rival()
    theirs = f"/api/companies/{company.company_id}/alerts/{alert.alert_id}/timeline"
    assert rival.get(theirs).status_code == 404


# --- Partners --------------------------------------------------------------------------------


def test_partners_are_derived_from_events_with_pos_links(world: World):
    admin = f.make_user(world.db, is_admin=True)
    distributor = world.shop("Demo Distribution", is_retailer=False, is_distributor=True)
    shop = world.shop("Demo Corner Shop", city="Kano")
    named = world.shop("Demo Named Only", city="Abuja")
    _, first = world.unit()
    world.event(distributor, first, E.RECEIVED)
    world.event(distributor, first, E.TRANSFERRED, to_company_id=shop.company_id)
    world.event(shop, first, E.RECEIVED)
    world.event(shop, first, E.SOLD)
    _, undone = world.unit()
    world.event(shop, undone, E.SOLD)
    world.event(shop, undone, E.RETURNED)
    _, sent = world.unit()
    world.event(distributor, sent, E.RECEIVED)
    world.event(distributor, sent, E.TRANSFERRED, to_company_id=named.company_id)
    partner = pos_admin.PosPartner(
        name="Demo Till Systems (fictional)",
        signing_secret_encrypted="not-a-real-ciphertext",
        created_by_user_id=admin.user_id,
    )
    world.db.add(partner)
    world.db.flush()
    link = pos_admin.PosPartnerRetailer(
        partner_id=partner.partner_id,
        retailer_company_id=shop.company_id,
        created_by_user_id=admin.user_id,
        status=PosLinkStatus.ACTIVE,
    )
    world.db.add(link)
    world.db.flush()
    # Another manufacturer's pack is not this manufacturer's partner data.
    rival, _ = world.rival()
    rival_product = f.make_product(world.db, rival, status=ProductStatus.PUBLISHED)
    rival_batch = f.make_batch(world.db, rival_product, review_status=ReviewStatus.APPROVED)
    token = identity.new_token()
    f.make_unit(
        world.db,
        rival_batch,
        qr_token_hash=identity.token_hash(token),
        lifecycle_status=S.RELEASED,
    )
    outsider = world.shop("Rival Only Shop", city="Enugu")
    world.event(outsider, token, E.RECEIVED)

    body = world.client(world.owner).get(f"/api/companies/{world.cid}/partners").json()

    assert [p["display_name"] for p in body] == [
        "Demo Corner Shop",
        "Demo Distribution",
        "Demo Named Only",
    ]
    corner, distribution, only_named = body
    assert corner["places"] == ["Kano"]
    assert (corner["received"], corner["sold"]) == (1, 1)  # the returned sale does not count
    assert corner["pos_partners"] == ["Demo Till Systems (fictional)"]
    assert corner["is_retailer"] is True
    assert (distribution["received"], distribution["sold"]) == (2, 0)
    assert distribution["pos_partners"] == []
    assert (only_named["received"], only_named["sold"], only_named["places"]) == (0, 0, [])


# --- Consumer reports (D120) -----------------------------------------------------------------


def _report(world: World, company=None, unit=None, **values) -> ConsumerReport:
    report = ConsumerReport(
        unit_id=unit.unit_id if unit else None,
        manufacturer_id=company.company_id if company else None,
        concern_type=ConcernType.PACKAGING,
        description="The seal looked broken.",
        area_id=f.area(world.db, "Lagos").area_id,
        **values,
    )
    world.db.add(report)
    world.db.flush()
    return report


def test_reports_are_private_to_the_manufacturer_and_admins(world: World):
    unit, _ = world.unit()
    mine = _report(world, world.manufacturer, unit)
    rival, rival_client = world.rival()
    theirs = _report(world, rival)
    unrouted = _report(world)
    staff = world.client(world.member_of(world.manufacturer, MemberRole.STAFF))

    listed = staff.get(f"/api/companies/{world.cid}/reports").json()
    assert [r["report_id"] for r in listed] == [str(mine.report_id)]
    assert listed[0]["product_name"] == "Sample Palm Oil"
    assert listed[0]["batch_number"] == "DEMO-LOT-001"
    assert listed[0]["area"] == "Lagos"
    assert str(unit.unit_id) not in json.dumps(listed)

    assert rival_client.get(f"/api/companies/{world.cid}/reports").status_code == 403
    refused = rival_client.post(
        f"/api/companies/{rival.company_id}/reports/{mine.report_id}/status",
        json={"status": "CLOSED"},
    )
    assert refused.status_code == 404

    admin = world.admin()
    ids = {r["report_id"] for r in admin.get("/api/admin/reports").json()}
    assert ids == {str(mine.report_id), str(theirs.report_id), str(unrouted.report_id)}
    assert staff.get("/api/admin/reports").status_code == 403


def test_report_status_changes_are_audited_for_both_sides(world: World):
    report = _report(world, world.manufacturer)
    staff_user = world.member_of(world.manufacturer, MemberRole.STAFF)
    staff = world.client(staff_user)
    base = f"/api/companies/{world.cid}/reports"

    reviewed = staff.post(f"{base}/{report.report_id}/status", json={"status": "REVIEWED"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "REVIEWED"
    assert staff.get(f"{base}?status=NEW").json() == []
    assert len(staff.get(f"{base}?status=REVIEWED").json()) == 1

    admin_user = f.make_user(world.db, is_admin=True, password_hash=hash_password(PASSWORD))
    closed = world.client(admin_user).post(
        f"/api/admin/reports/{report.report_id}/status", json={"status": "CLOSED"}
    )
    assert closed.status_code == 200

    entries = world.db.exec(
        select(AuditLog).where(AuditLog.entity_id == report.report_id).order_by(AuditLog.created_at)
    ).all()
    assert [e.actor_user_id for e in entries] == [staff_user.user_id, admin_user.user_id]
    assert [e.new_values["status"] for e in entries] == ["REVIEWED", "CLOSED"]

    back = staff.post(f"{base}/{report.report_id}/status", json={"status": "NEW"})
    assert back.status_code == 409
    assert back.json()["detail"] == "This status change isn't allowed."


# --- Manufacturer stats (fixed datasets) -----------------------------------------------------


def _stats(world: World) -> stats.ManufacturerStats:
    return stats.manufacturer_stats(world.db, world.cid, NOW)


def test_stats_are_empty_for_a_new_manufacturer(world: World):
    result = _stats(world)

    assert (result.issued, result.released) == (0, 0)
    assert result.sale_coverage_pct is None
    assert result.pos_share_pct is None and result.merchant_share_pct is None
    assert result.median_hours_to_resolve is None
    assert result.checks_by_city_week == [] and result.hot_spots == []
    assert result.alerts == []


def test_issued_released_coverage_and_channel_share(world: World):
    shop = world.shop()
    _, merchant_sale = world.unit()
    world.event(shop, merchant_sale, E.SOLD)
    pos_unit, _ = world.unit()
    f.make_event(
        world.db,
        unit_id=pos_unit.unit_id,
        event_type=E.SOLD,
        source=EventSource.POS_API,
        retailer_company_id=shop.company_id,
        occurred_at=NOW,
    )
    _, returned = world.unit()
    world.event(shop, returned, E.SOLD)
    world.event(shop, returned, E.RETURNED)
    world.unit()  # released, never sold
    world.unit(status=S.ISSUED, released=False)  # issued only
    world.unit(status=S.VOIDED, released=False)  # not counted at all

    result = _stats(world)

    assert result.issued == 5
    assert result.released == 4
    assert result.sale_coverage_pct == 50.0  # 2 of 4; the returned pack does not count
    assert (result.pos_sales, result.merchant_sales) == (1, 1)
    assert (result.pos_share_pct, result.merchant_share_pct) == (50.0, 50.0)


def test_coverage_counts_only_this_manufacturers_packs(world: World):
    world.unit()
    rival, _ = world.rival()

    assert stats.manufacturer_stats(world.db, rival.company_id, NOW).released == 0
    assert _stats(world).released == 1


def test_checks_by_city_and_week(world: World):
    unit, _ = world.unit()
    # Sunday 23:30 Nigeria time is still last week; Monday 00:30 is this week, though both are
    # the same day in UTC.
    world.scan(unit, "Lagos", datetime(2026, 10, 25, 23, 30, tzinfo=WAT))
    world.scan(unit, "Lagos", datetime(2026, 10, 26, 0, 30, tzinfo=WAT))
    world.scan(unit, "Lagos", datetime(2026, 10, 27, 9, 0, tzinfo=WAT))
    world.scan(unit, "Kano", datetime(2026, 10, 27, 9, 0, tzinfo=WAT))
    world.scan(unit, None, datetime(2026, 10, 27, 9, 0, tzinfo=WAT))
    # The oldest of the 12 weeks counts; the one before it does not.
    world.scan(unit, "Abuja", datetime(2026, 8, 10, 0, 0, tzinfo=WAT))
    world.scan(unit, "Abuja", datetime(2026, 8, 9, 23, 59, tzinfo=WAT))
    # Carton scans have no pack, and another company's packs are not counted.
    carton, _ = world.carton()
    world.db.add(
        ScanEvent(
            identifier_type=IdentifierType.QR,
            carton_id=carton.carton_id,
            area_id=f.area(world.db, "Lagos").area_id,
            result=CheckResult.CARTON_CODE,
            created_at=NOW,
        )
    )
    world.db.flush()

    rows = [(r.week_start, r.city, r.checks) for r in _stats(world).checks_by_city_week]

    assert rows == [
        (date(2026, 8, 10), "Abuja", 1),
        (date(2026, 10, 19), "Lagos", 1),
        (date(2026, 10, 26), "Kano", 1),
        (date(2026, 10, 26), "Lagos", 2),
        (date(2026, 10, 26), "Unknown area", 1),
    ]


def test_hot_spots_rank_by_open_alerts_then_checks(world: World):
    unit, _ = world.unit()
    kano = f.area(world.db, "Kano").area_id
    world.alert(rule=RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE, unit_id=unit.unit_id, area_id=kano)
    enugu = f.area(world.db, "Enugu").area_id
    world.alert(
        rule=RiskRule.R6_UNRELEASED_SCANNED,
        unit_id=unit.unit_id,
        area_id=enugu,
        status=AlertStatus.RESOLVED_LEGITIMATE,
    )
    for city, checks in (("Lagos", 3), ("Abuja", 2), ("Ibadan", 1), ("Jos", 4), ("Aba", 1)):
        for _ in range(checks):
            world.scan(unit, city, NOW - timedelta(days=1))
    world.scan(unit, "Warri", NOW - timedelta(days=31))  # too old

    spots = [(s.city, s.open_alerts, s.checks) for s in _stats(world).hot_spots]

    assert spots == [
        ("Kano", 1, 0),
        ("Jos", 0, 4),
        ("Lagos", 0, 3),
        ("Abuja", 0, 2),
        ("Aba", 0, 1),
    ]


def test_alerts_raised_resolved_and_median_time_to_resolve(world: World):
    unit, _ = world.unit()
    for number, hours in enumerate((2, 4, 9)):
        created = NOW - timedelta(days=3)
        world.db.add(
            RiskAlert(
                rule=RiskRule.R8_VOIDED_CODE_IN_USE,
                level=AlertLevel.HIGH,
                manufacturer_id=world.cid,
                unit_id=f.make_unit(world.db, world.batch).unit_id,
                evidence={"explanation": f"Demo {number}"},
                status=AlertStatus.RESOLVED_LEGITIMATE,
                created_at=created,
                resolved_at=created + timedelta(hours=hours),
            )
        )
    # Open: raised, not resolved.
    world.db.add(
        RiskAlert(
            rule=RiskRule.R3_SCAN_VOLUME,
            level=AlertLevel.MEDIUM,
            manufacturer_id=world.cid,
            unit_id=unit.unit_id,
            evidence={"explanation": "Open"},
            created_at=NOW - timedelta(days=1),
        )
    )
    # Outside the 12 weeks: not counted, and not in the median.
    long_ago = NOW - timedelta(weeks=20)
    world.db.add(
        RiskAlert(
            rule=RiskRule.R6_UNRELEASED_SCANNED,
            level=AlertLevel.MEDIUM,
            manufacturer_id=world.cid,
            unit_id=unit.unit_id,
            evidence={"explanation": "Old"},
            status=AlertStatus.RESOLVED_LEGITIMATE,
            created_at=long_ago,
            resolved_at=long_ago + timedelta(hours=500),
        )
    )
    world.db.flush()

    result = _stats(world)

    assert (result.alerts_raised, result.alerts_resolved) == (4, 3)
    assert result.median_hours_to_resolve == 4.0
    rows = {(a.rule, a.level): (a.raised, a.resolved) for a in result.alerts}
    assert rows[(RiskRule.R8_VOIDED_CODE_IN_USE, AlertLevel.HIGH)] == (3, 3)
    assert rows[(RiskRule.R3_SCAN_VOLUME, AlertLevel.MEDIUM)] == (1, 0)
    assert (RiskRule.R6_UNRELEASED_SCANNED, AlertLevel.MEDIUM) not in rows


def test_stats_route_is_limited_to_the_company(world: World):
    world.unit()
    company, rival = world.rival()

    assert rival.get(f"/api/companies/{world.cid}/stats").status_code == 403
    own = rival.get(f"/api/companies/{company.company_id}/stats")
    assert own.status_code == 200
    assert own.json()["released"] == 0
    assert (
        world.client(world.owner).get(f"/api/companies/{world.cid}/stats").json()["released"] == 1
    )


# --- Admin -----------------------------------------------------------------------------------


def test_platform_stats(world: World):
    world.unit()
    world.unit(status=S.VOIDED, released=False)
    world.scan(None, "Lagos", utc_now() - timedelta(days=1), CheckResult.INVALID_IDENTITY)
    world.scan(None, "Lagos", utc_now() - timedelta(days=31), CheckResult.INVALID_IDENTITY)
    f.make_company(world.db, review_status=CompanyReviewStatus.PENDING_REVIEW)
    world.alert(rule=RiskRule.R4_INVALID_BURST, manufacturer_id=None)
    world.alert(
        rule=RiskRule.R4_INVALID_BURST,
        manufacturer_id=None,
        area_id=f.area(world.db, "Kano").area_id,
        status=AlertStatus.RESOLVED_LEGITIMATE,
    )
    _report(world, status=ReportStatus.NEW)
    _report(world, status=ReportStatus.CLOSED)
    admin_user = f.make_user(world.db, is_admin=True, password_hash=hash_password(PASSWORD))
    f.make_pos_partner(world.db, admin_user)
    world.db.add(
        RateLimitDaily(
            area_id=None,
            day=utc_now().astimezone(WAT).date(),
            bucket=RateLimitBucket.POS,
            count=7,
        )
    )
    world.db.flush()

    assert world.client(admin_user).get("/api/admin/stats").json() == {
        "companies": 2,
        "approved_companies": 1,
        "packs_issued": 1,
        "checks_last_30_days": 1,
        "pos_partners": 1,
        "open_alerts": 1,
        "new_reports": 1,
        "pos_rate_limit_hits_last_30_days": 7,
    }


def test_the_scanning_panel_counts_per_area_and_day_and_holds_no_ip(world: World):
    now = datetime.now(UTC)
    today = now.astimezone(WAT).date()
    yesterday = today - timedelta(days=1)
    lagos = f.area(world.db, "Lagos").area_id
    kano = f.area(world.db, "Kano").area_id
    rows = [
        (lagos, today, RateLimitBucket.CHECK, 5),
        (lagos, today, RateLimitBucket.REPORT, 2),
        (kano, yesterday, RateLimitBucket.CHECK, 3),
        (None, today, RateLimitBucket.CHECK, 1),
        # POS hits come from partners, so they stay in platform stats.
        (None, today, RateLimitBucket.POS, 9),
        (lagos, today - timedelta(days=31), RateLimitBucket.CHECK, 50),
    ]
    for area_id, day, bucket, count in rows:
        world.db.add(RateLimitDaily(area_id=area_id, day=day, bucket=bucket, count=count))
    world.db.flush()
    invalid = CheckResult.INVALID_IDENTITY
    noon = datetime.combine(today, datetime.min.time(), tzinfo=WAT)
    world.scan(None, "Lagos", noon, invalid)
    world.scan(None, "Lagos", noon, invalid)
    world.scan(None, "Lagos", noon, CheckResult.RECOGNISED_NOT_SOLD)
    world.scan(None, "Kano", noon - timedelta(days=1), invalid)
    world.db.add(
        RiskAlert(
            rule=RiskRule.R4_INVALID_BURST,
            level=AlertLevel.MEDIUM,
            area_id=lagos,
            evidence={"explanation": "Burst"},
            created_at=noon,
        )
    )
    world.db.flush()
    admin = world.admin()

    response = admin.get("/api/admin/scanning")

    assert response.status_code == 200
    assert response.json() == [
        {
            "day": today.isoformat(),
            "area": "Lagos",
            "rate_limit_hits": 7,
            "invalid_codes": 2,
            "burst_alerts": 1,
        },
        {
            "day": today.isoformat(),
            "area": "Unknown area",
            "rate_limit_hits": 1,
            "invalid_codes": 0,
            "burst_alerts": 0,
        },
        {
            "day": yesterday.isoformat(),
            "area": "Kano",
            "rate_limit_hits": 3,
            "invalid_codes": 1,
            "burst_alerts": 0,
        },
    ]
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", response.text)
    assert "ip" not in {key for row in response.json() for key in row}
    assert not UUID_PATTERN.search(response.text)


def test_admin_dashboards_need_an_admin(world: World):
    owner = world.client(world.owner)
    anonymous = world.make_client(settings=Settings(rate_limit_enabled=False))

    for path in ("/api/admin/stats", "/api/admin/scanning", "/api/admin/reports"):
        assert owner.get(path).status_code == 403
        assert anonymous.get(path).status_code == 401


def test_dashboard_wording_avoids_banned_words():
    banned = re.compile(
        r"\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac", re.I
    )
    from app.services import reports, timeline

    texts = [timeline.MSG_NOT_FOUND, stats.UNKNOWN_AREA]
    texts += [reports.MSG_BAD_CHANGE]
    assert not [t for t in texts if banned.search(t)]
