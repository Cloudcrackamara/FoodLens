"""POS API (Phase 5): signing, stale and replayed requests, revoked keys, idempotent retries, late
offline events, refund and void history, read-only lookups, no payment data, retailer and till
checks, the per-partner rate limit, admin management and the simulated till."""

import hashlib
import hmac
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session, func, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AppUser,
    AuditLog,
    Company,
    LifecycleEvent,
    PosPartner,
    PosPartnerKey,
    PosTill,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    RateLimitDaily,
    SupplierLocation,
)
from app.models.base import utc_now
from app.models.enums import (
    AnnouncementKind,
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    MemberRole,
    PosPartnerStatus,
    ProductStatus,
    RateLimitBucket,
    ReviewStatus,
)
from app.services import demo_pos, identity, lifecycle, pos_admin
from tests import factories as f

PASSWORD = "correct-horse-battery"
E = LifecycleEventType
S = LifecycleStatus
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def pos_settings(**overrides) -> Settings:
    values = {
        "rate_limit_enabled": False,
        "pos_secret_key": Fernet.generate_key().decode(),
        "demo_pos_enabled": True,
    }
    return Settings(**(values | overrides))


def signature(secret: str, timestamp: str, raw: bytes) -> str:
    """Written out here, not taken from the app, so the test pins the documented scheme."""
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256).hexdigest()


@dataclass
class World:
    db: Session
    settings: Settings
    client: TestClient
    admin: AppUser
    manufacturer: Company
    batch: ProductBatch
    retailer: Company
    location: SupplierLocation
    partner: PosPartner
    key: str
    secret: str
    make_client: Callable[..., TestClient]

    till = "TILL-1"

    def unit(self, status=S.RELEASED, **overrides) -> tuple[ProductUnit, str]:
        token = identity.new_token()
        unit = f.make_unit(
            self.db,
            self.batch,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            **({"current_holder_company_id": self.manufacturer.company_id} | overrides),
        )
        return unit, token

    def body(self, **fields) -> dict:
        return {"retailer_id": str(self.retailer.company_id), "till_id": self.till} | fields

    def sale_body(self, *tokens: str, **fields) -> dict:
        return self.body(
            transaction_id=fields.pop("transaction_id", f"DEMO-TXN-{uuid.uuid4().hex[:8]}"),
            payment_reference=fields.pop("payment_reference", "DEMO-PAY-0001"),
            occurred_at=fields.pop("occurred_at", utc_now()).isoformat(),
            units=list(tokens),
            **fields,
        )

    def signed(
        self,
        path: str,
        payload: dict | None = None,
        *,
        raw: bytes | None = None,
        key: str | None = None,
        secret: str | None = None,
        timestamp: int | None = None,
        client: TestClient | None = None,
    ):
        raw = raw if raw is not None else json.dumps(payload).encode()
        ts = str(timestamp if timestamp is not None else int(utc_now().timestamp()))
        headers = {
            "Content-Type": "application/json",
            "X-FoodLens-Key": key or self.key,
            "X-FoodLens-Timestamp": ts,
            "X-FoodLens-Signature": signature(secret or self.secret, ts, raw),
        }
        return (client or self.client).post(f"/api/pos/v1/{path}", content=raw, headers=headers)

    def sell(self, *tokens: str, **fields):
        return self.signed("sales", self.sale_body(*tokens, **fields))

    def event_body(self, *tokens: str, **fields) -> dict:
        return self.body(
            transaction_id=fields.pop("transaction_id", f"DEMO-RFD-{uuid.uuid4().hex[:8]}"),
            occurred_at=fields.pop("occurred_at", utc_now()).isoformat(),
            units=list(tokens),
            **fields,
        )

    def refresh(self, unit: ProductUnit) -> ProductUnit:
        self.db.expire(unit)
        return self.db.get(ProductUnit, unit.unit_id)

    def events(self, unit: ProductUnit, event_type: E | None = None) -> list[LifecycleEvent]:
        statement = select(LifecycleEvent).where(LifecycleEvent.unit_id == unit.unit_id)
        if event_type:
            statement = statement.where(LifecycleEvent.event_type == event_type)
        return list(self.db.exec(statement.order_by(LifecycleEvent.occurred_at)).all())

    def count_events(self) -> int:
        return self.db.exec(select(func.count()).select_from(LifecycleEvent)).one()

    def check(self, token: str) -> dict:
        consumer = self.make_client(settings=self.settings)
        return consumer.post("/api/check/qr", json={"code": token, "identifier_type": "QR"}).json()

    def make_retailer(self, name: str = "Demo Second Shop (fictional)", city: str = "Kano", **kw):
        values = {
            "is_manufacturer": False,
            "is_retailer": True,
            "review_status": CompanyReviewStatus.APPROVED,
        } | kw
        company = f.make_company(self.db, display_name=name, **values)
        location = SupplierLocation(
            company_id=company.company_id,
            name=f"{name} shop",
            address="2 Demo Street",
            area=city,
            area_id=f.area(self.db, city).area_id,
            review_status=ReviewStatus.APPROVED,
        )
        self.db.add(location)
        self.db.flush()
        return company, location


def _retailer(db: Session) -> tuple[Company, SupplierLocation]:
    company = f.make_company(
        db,
        display_name="Demo Corner Shop",
        is_manufacturer=False,
        is_retailer=True,
        review_status=CompanyReviewStatus.APPROVED,
    )
    location = SupplierLocation(
        company_id=company.company_id,
        name="Main shop",
        address="1 Demo Street",
        area="Lagos",
        area_id=f.area(db, "Lagos").area_id,
        review_status=ReviewStatus.APPROVED,
    )
    db.add(location)
    db.flush()
    return company, location


def build_world(session: Session, make_client, settings: Settings) -> World:
    admin = f.make_user(session, is_admin=True, password_hash=hash_password(PASSWORD))
    manufacturer = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    product = f.make_product(
        session, manufacturer, status=ProductStatus.PUBLISHED, gtin="96385074", size="1 L"
    )
    batch = f.make_batch(session, product, review_status=ReviewStatus.APPROVED)
    retailer, location = _retailer(session)
    found, key, secret = pos_admin.create_partner(
        session, settings, admin, demo_pos.DEMO_PARTNER_NAME
    )
    pos_admin.link_retailer(session, admin, found.partner.partner_id, retailer.company_id)
    pos_admin.add_till(
        session,
        admin,
        found.partner.partner_id,
        retailer.company_id,
        "TILL-1",
        location.location_id,
    )
    return World(
        session,
        settings,
        make_client(settings=settings),
        admin,
        manufacturer,
        batch,
        retailer,
        location,
        found.partner,
        key,
        secret,
        make_client,
    )


@pytest.fixture
def world(session: Session, make_client) -> World:
    return build_world(session, make_client, pos_settings())


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- Signing (D121) --------------------------------------------------------------------------


def test_a_signed_sale_is_recorded(world: World):
    unit, token = world.unit()

    response = world.sell(token)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recorded"] == 1 and body["errors"] == 0
    assert body["units"] == [
        {"index": 0, "code_last4": token[-4:], "result": "RECORDED", "error": None}
    ]
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.SOLD
    assert unit.current_holder_company_id == world.retailer.company_id
    assert unit.last_sold_company_id == world.retailer.company_id
    assert unit.last_sold_area_id == world.location.area_id
    (event,) = world.events(unit, E.SOLD)
    assert event.source == EventSource.POS_API
    assert event.pos_partner_id == world.partner.partner_id
    assert event.retailer_company_id == world.retailer.company_id
    assert event.actor_user_id is None and event.actor_company_id is None
    assert event.till_ref == "TILL-1"
    assert event.payment_reference == "DEMO-PAY-0001"
    assert event.area_id == world.location.area_id


def test_an_unsigned_request_is_rejected(world: World):
    unit, token = world.unit()

    response = world.client.post("/api/pos/v1/sales", json=world.sale_body(token))

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "MISSING_SIGNATURE",
            "message": (
                "Missing X-FoodLens-Key, X-FoodLens-Timestamp or X-FoodLens-Signature header."
            ),
        }
    }
    assert world.refresh(unit).lifecycle_status == S.RELEASED
    assert world.events(unit, E.SOLD) == []


def test_a_bad_signature_is_rejected(world: World):
    unit, token = world.unit()

    response = world.signed("sales", world.sale_body(token), secret="fls_not-the-secret")

    assert response.status_code == 401
    assert error_code(response) == "INVALID_SIGNATURE"
    assert world.events(unit, E.SOLD) == []


def test_a_body_changed_after_signing_is_rejected(world: World):
    unit, token = world.unit()
    other, other_token = world.unit()
    ts = str(int(utc_now().timestamp()))
    signed_raw = json.dumps(world.sale_body(token)).encode()
    sent_raw = json.dumps(world.sale_body(other_token)).encode()

    response = world.client.post(
        "/api/pos/v1/sales",
        content=sent_raw,
        headers={
            "X-FoodLens-Key": world.key,
            "X-FoodLens-Timestamp": ts,
            "X-FoodLens-Signature": signature(world.secret, ts, signed_raw),
        },
    )

    assert error_code(response) == "INVALID_SIGNATURE"
    assert world.events(other, E.SOLD) == []


def test_a_signature_for_another_timestamp_is_rejected(world: World):
    """The timestamp is signed with the body, so a captured body can't get a fresh timestamp."""
    _, token = world.unit()
    raw = json.dumps(world.sale_body(token)).encode()
    old = str(int(utc_now().timestamp()) - 10)
    now = str(int(utc_now().timestamp()))

    response = world.client.post(
        "/api/pos/v1/sales",
        content=raw,
        headers={
            "X-FoodLens-Key": world.key,
            "X-FoodLens-Timestamp": now,
            "X-FoodLens-Signature": signature(world.secret, old, raw),
        },
    )

    assert error_code(response) == "INVALID_SIGNATURE"


def test_a_wrong_key_is_rejected(world: World):
    _, token = world.unit()

    response = world.signed("sales", world.sale_body(token), key="flk_unknown-key")

    assert response.status_code == 401
    assert response.json()["error"] == {"code": "INVALID_KEY", "message": "API key not recognised."}


def test_a_revoked_key_is_rejected_and_a_new_key_works(world: World):
    admin = signed_in(world, world.admin)
    key = world.db.exec(
        select(PosPartnerKey).where(PosPartnerKey.partner_id == world.partner.partner_id)
    ).one()
    revoked = admin.post(
        f"/api/admin/pos/partners/{world.partner.partner_id}/keys/{key.key_id}/revoke"
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    _, token = world.unit()

    response = world.sell(token)

    assert response.status_code == 401
    assert error_code(response) == "INVALID_KEY"

    created = admin.post(f"/api/admin/pos/partners/{world.partner.partner_id}/keys")
    assert created.status_code == 201
    new_key = created.json()["credentials"]["api_key"]
    assert world.signed("sales", world.sale_body(token), key=new_key).status_code == 200


def test_a_suspended_partner_is_rejected_like_a_wrong_key(world: World):
    pos_admin.set_status(
        world.db, world.admin, world.partner.partner_id, PosPartnerStatus.SUSPENDED
    )
    _, token = world.unit()

    response = world.sell(token)

    assert response.status_code == 401
    assert error_code(response) == "INVALID_KEY"


@pytest.mark.parametrize("offset", [-301, 301, -3600])
def test_a_timestamp_more_than_300_seconds_off_is_rejected(world: World, offset: int):
    unit, token = world.unit()

    response = world.signed(
        "sales", world.sale_body(token), timestamp=int(utc_now().timestamp()) + offset
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "STALE_TIMESTAMP",
        "message": "Request timestamp is too far from the server time. Check the till clock.",
    }
    assert world.events(unit, E.SOLD) == []


@pytest.mark.parametrize("offset", [-295, 295])
def test_a_timestamp_within_300_seconds_is_accepted(world: World, offset: int):
    _, token = world.unit()

    response = world.signed(
        "sales", world.sale_body(token), timestamp=int(utc_now().timestamp()) + offset
    )

    assert response.status_code == 200


def test_the_skew_is_configurable(session: Session, make_client):
    world = build_world(session, make_client, pos_settings(pos_max_skew_seconds=30))
    _, token = world.unit()

    response = world.signed(
        "sales", world.sale_body(token), timestamp=int(utc_now().timestamp()) - 60
    )

    assert error_code(response) == "STALE_TIMESTAMP"


def test_without_pos_secret_key_the_api_is_off(session: Session, make_client):
    world = build_world(session, make_client, pos_settings())
    client = make_client(settings=pos_settings(pos_secret_key=""))
    _, token = world.unit()

    response = world.signed("sales", world.sale_body(token), client=client)

    assert response.status_code == 503
    assert error_code(response) == "POS_NOT_CONFIGURED"


# --- Idempotency and replay ------------------------------------------------------------------


def test_replaying_a_signed_sale_gives_the_same_response_and_no_new_events(world: World):
    unit, token = world.unit()
    raw = json.dumps(world.sale_body(token, transaction_id="DEMO-TXN-REPLAY")).encode()
    ts = str(int(utc_now().timestamp()))
    headers = {
        "X-FoodLens-Key": world.key,
        "X-FoodLens-Timestamp": ts,
        "X-FoodLens-Signature": signature(world.secret, ts, raw),
    }

    first = world.client.post("/api/pos/v1/sales", content=raw, headers=headers)
    count = world.count_events()
    again = world.client.post("/api/pos/v1/sales", content=raw, headers=headers)

    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert world.count_events() == count
    assert len(world.events(unit, E.SOLD)) == 1


def test_a_retry_with_a_new_timestamp_is_idempotent(world: World):
    unit, token = world.unit()
    good, good_token = world.unit()
    sold, sold_token = world.unit(status=S.SOLD)
    body = world.sale_body(token, good_token, sold_token, transaction_id="DEMO-TXN-RETRY")

    first = world.signed("sales", body)
    count = world.count_events()
    retry = world.signed("sales", body, timestamp=int(utc_now().timestamp()) + 5)

    assert retry.json() == first.json()
    assert first.json()["recorded"] == 2
    assert world.count_events() == count


def test_the_same_pack_in_a_new_transaction_is_already_sold(world: World):
    _, token = world.unit()
    world.sell(token, transaction_id="DEMO-TXN-A")

    response = world.sell(token, transaction_id="DEMO-TXN-B")

    assert response.status_code == 200
    (result,) = response.json()["units"]
    assert result["result"] == "ERROR"
    assert result["error"] == {
        "code": "ALREADY_SOLD",
        "message": (
            "This pack is already recorded as sold. Don't complete the sale; set the pack aside "
            "and check it."
        ),
    }


def test_the_idempotency_key_includes_the_event_type(world: World):
    """A refund may reuse the sale's transaction ID; it is a different event."""
    unit, token = world.unit()
    world.sell(token, transaction_id="DEMO-TXN-SAME")

    refund = world.signed("refunds", world.event_body(token, transaction_id="DEMO-TXN-SAME"))

    assert refund.json()["recorded"] == 1
    assert world.refresh(unit).lifecycle_status == S.IN_STOCK


# --- Late offline events and time limits -----------------------------------------------------


def test_a_late_offline_sale_is_accepted_with_its_own_time(world: World):
    unit, token = world.unit()
    occurred = utc_now() - timedelta(days=3)

    response = world.sell(token, occurred_at=occurred)

    assert response.json()["recorded"] == 1
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.SOLD
    assert unit.last_sold_at == occurred
    (event,) = world.events(unit, E.SOLD)
    assert event.occurred_at == occurred
    assert event.recorded_at > occurred
    # Three days ago is outside the just-sold window.
    assert world.check(token)["result"] == "RECOGNISED_PREVIOUSLY_SOLD"


def test_late_offline_sale_and_refund_replay_in_occurred_at_order(world: World):
    unit, token = world.unit()
    sold_at = utc_now() - timedelta(days=2)
    world.sell(token, occurred_at=sold_at)
    world.signed("refunds", world.event_body(token, occurred_at=sold_at + timedelta(hours=1)))

    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.last_sold_at is None
    assert [e.event_type for e in world.events(unit)] == [E.SOLD, E.RETURNED]


def test_a_late_event_older_than_a_later_one_takes_its_place_in_the_history(world: World):
    """D151: validated against the current status, then replayed in occurred_at order."""
    unit, token = world.unit()
    received_at = utc_now() - timedelta(hours=1)
    f.make_event(
        world.db,
        unit_id=unit.unit_id,
        event_type=E.RECEIVED,
        source=EventSource.MERCHANT_APP,
        actor_company_id=world.retailer.company_id,
        occurred_at=received_at,
    )
    lifecycle.replay_unit(world.db, unit)

    world.sell(token, occurred_at=received_at - timedelta(hours=1))

    unit = world.refresh(unit)
    assert [e.event_type for e in world.events(unit)] == [E.SOLD, E.RECEIVED]
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.current_holder_company_id == world.retailer.company_id


def test_an_event_older_than_the_maximum_age_is_rejected(world: World):
    unit, token = world.unit()

    response = world.sell(token, occurred_at=utc_now() - timedelta(days=7, minutes=1))

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "EVENT_TOO_OLD",
        "message": "This event is older than 7 days and can't be recorded.",
    }
    assert world.events(unit) == []


def test_the_maximum_event_age_is_configurable(session: Session, make_client):
    world = build_world(session, make_client, pos_settings(pos_max_event_age_days=2))
    _, token = world.unit()

    response = world.sell(token, occurred_at=utc_now() - timedelta(days=3))

    assert response.json()["error"]["message"] == (
        "This event is older than 2 days and can't be recorded."
    )


def test_an_event_more_than_5_minutes_in_the_future_is_rejected(world: World):
    unit, token = world.unit()

    response = world.sell(token, occurred_at=utc_now() + timedelta(minutes=6))

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "EVENT_IN_FUTURE",
        "message": "This event's time is in the future. Check the till clock.",
    }
    assert world.events(unit) == []


def test_an_event_a_little_in_the_future_is_accepted(world: World):
    _, token = world.unit()

    response = world.sell(token, occurred_at=utc_now() + timedelta(minutes=4))

    assert response.json()["recorded"] == 1


def test_occurred_at_needs_a_time_zone(world: World):
    _, token = world.unit()
    body = world.sale_body(token)
    body["occurred_at"] = "2026-10-30T10:00:00"

    response = world.signed("sales", body)

    assert response.status_code == 422
    assert error_code(response) == "INVALID_BODY"


# --- Per-pack results ------------------------------------------------------------------------


def test_a_sale_returns_a_per_pack_error_list(world: World):
    _, good = world.unit()
    _, sold = world.unit(status=S.SOLD)
    _, recalled = world.unit(status=S.RECALLED)
    _, voided = world.unit(status=S.VOIDED)
    _, unreleased = world.unit(status=S.ISSUED)
    carton_token = identity.new_token()
    f.make_carton(
        world.db,
        world.batch,
        world.manufacturer,
        qr_token_hash=identity.token_hash(carton_token),
        lifecycle_status=S.RELEASED,
    )
    unknown = identity.new_token()

    response = world.sell(good, sold, recalled, voided, unreleased, carton_token, unknown, good)

    body = response.json()
    assert body["recorded"] == 1 and body["errors"] == 7
    codes = [(u["index"], u["result"], u["error"] and u["error"]["code"]) for u in body["units"]]
    assert codes == [
        (0, "RECORDED", None),
        (1, "ERROR", "ALREADY_SOLD"),
        (2, "ERROR", "RECALLED"),
        (3, "ERROR", "VOIDED"),
        (4, "ERROR", "UNRELEASED"),
        (5, "ERROR", "CARTON_CODE"),
        (6, "ERROR", "UNKNOWN_CODE"),
        (7, "ERROR", "DUPLICATE_IN_REQUEST"),
    ]
    messages = {u["error"]["code"]: u["error"]["message"] for u in body["units"] if u["error"]}
    assert (
        messages["VOIDED"] == "This code was voided by the manufacturer, so it can't be recorded."
    )
    assert messages["CARTON_CODE"] == "This is a carton code. Scan the individual pack."
    assert messages["DUPLICATE_IN_REQUEST"] == "This pack appears more than once in the sale."
    assert messages["UNKNOWN_CODE"] == "No FoodLens code found. Check the code and try again."


def test_a_pack_under_a_live_recall_is_refused(world: World):
    unit, token = world.unit()
    world.db.add(
        ProductAnnouncement(
            product_id=world.batch.product_id,
            created_by_user_id=world.admin.user_id,
            kind=AnnouncementKind.RECALL,
            recall_reason="Demo recall reason",
            title="Demo recall",
            message="Demo recall notice for a fictional batch.",
        )
    )
    world.db.flush()

    response = world.sell(token)

    assert response.json()["units"][0]["error"]["code"] == "RECALLED"
    assert world.refresh(unit).lifecycle_status == S.RELEASED


def test_too_many_packs_in_one_request_is_rejected(session: Session, make_client):
    world = build_world(session, make_client, pos_settings(pos_max_units_per_request=2))
    units = [world.unit() for _ in range(3)]

    response = world.sell(*(token for _, token in units))

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "TOO_MANY_UNITS",
        "message": "A request can carry at most 2 packs.",
    }
    assert all(world.events(unit) == [] for unit, _ in units)


# --- Refunds and voids (D140) ----------------------------------------------------------------


def test_a_refund_puts_the_pack_back_in_stock_and_keeps_the_sale(world: World):
    unit, token = world.unit()
    world.sell(token)
    (sale,) = world.events(unit, E.SOLD)

    response = world.signed("refunds", world.event_body(token))

    assert response.status_code == 200
    assert response.json()["event_type"] == "RETURNED"
    assert response.json()["recorded"] == 1
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.current_holder_company_id == world.retailer.company_id
    assert (unit.last_sold_at, unit.last_sold_area_id, unit.last_sold_company_id) == (
        None,
        None,
        None,
    )
    (refund,) = world.events(unit, E.RETURNED)
    assert refund.returns_event_id == sale.event_id
    assert refund.source == EventSource.POS_API
    assert refund.payment_reference is None
    assert world.events(unit, E.SOLD) == [sale]

    check = world.check(token)
    assert check["result"] == "RECOGNISED_NOT_SOLD"
    assert check["title"] == "In circulation, not yet sold"
    # It can be sold again.
    assert world.sell(token).json()["recorded"] == 1


def test_a_refund_of_another_retailers_sale_is_refused(world: World):
    other, _ = world.make_retailer()
    unit, token = world.unit(
        status=S.SOLD,
        last_sold_company_id=other.company_id,
        current_holder_company_id=other.company_id,
        last_sold_at=utc_now(),
    )

    response = world.signed("refunds", world.event_body(token))

    error = response.json()["units"][0]["error"]
    assert error == {
        "code": "NOT_SELLER",
        "message": "Only the company that recorded the sale can do this.",
    }
    assert world.refresh(unit).lifecycle_status == S.SOLD
    assert world.events(unit, E.RETURNED) == []


def test_a_refund_of_this_retailers_merchant_page_sale_is_accepted(world: World):
    """Decision 2(a): any standing sale by this retailer, however it was recorded (D140)."""
    unit, token = world.unit()
    sale = f.make_event(
        world.db,
        unit_id=unit.unit_id,
        event_type=E.SOLD,
        source=EventSource.MERCHANT_APP,
        actor_company_id=world.retailer.company_id,
        area_id=world.location.area_id,
        occurred_at=utc_now() - timedelta(hours=2),
    )
    lifecycle.replay_unit(world.db, unit)

    response = world.signed("refunds", world.event_body(token))

    assert response.json()["recorded"] == 1
    (refund,) = world.events(unit, E.RETURNED)
    assert refund.returns_event_id == sale.event_id
    assert world.refresh(unit).lifecycle_status == S.IN_STOCK


def test_a_refund_of_an_unsold_pack_is_refused(world: World):
    _, token = world.unit()

    response = world.signed("refunds", world.event_body(token))

    assert response.json()["units"][0]["error"] == {
        "code": "NOT_SOLD",
        "message": "This pack is not recorded as sold.",
    }


def test_a_refund_dated_before_the_sale_is_refused(world: World):
    unit, token = world.unit()
    sold_at = utc_now() - timedelta(hours=1)
    world.sell(token, occurred_at=sold_at)

    response = world.signed(
        "refunds", world.event_body(token, occurred_at=sold_at - timedelta(minutes=1))
    )

    assert response.json()["units"][0]["error"] == {
        "code": "BEFORE_SALE",
        "message": "The refund time is earlier than the sale.",
    }
    assert world.refresh(unit).lifecycle_status == S.SOLD


def test_a_void_needs_a_reason(world: World):
    unit, token = world.unit()
    world.sell(token)

    for reason in (None, "   "):
        body = world.event_body(token, transaction_id="DEMO-VOID-1")
        if reason is not None:
            body["reason"] = reason
        response = world.signed("voids", body)
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "NEED_REASON",
            "message": "Give a reason for the void.",
        }
    assert world.events(unit, E.SALE_CORRECTED) == []


def test_a_void_records_a_correction_and_keeps_the_sale(world: World):
    unit, token = world.unit()
    world.sell(token)
    (sale,) = world.events(unit, E.SOLD)

    response = world.signed(
        "voids", world.event_body(token, transaction_id="DEMO-VOID-1", reason="Rang up twice")
    )

    assert response.json()["event_type"] == "SALE_CORRECTED"
    assert response.json()["recorded"] == 1
    (correction,) = world.events(unit, E.SALE_CORRECTED)
    assert correction.corrects_event_id == sale.event_id
    assert correction.reason == "Rang up twice"
    assert world.events(unit, E.SOLD) == [sale]
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.last_sold_company_id is None


# --- Lookup (read-only) ----------------------------------------------------------------------


def _snapshot(db: Session) -> tuple:
    db.expire_all()
    return (
        db.exec(select(func.count()).select_from(LifecycleEvent)).one(),
        db.exec(select(func.count()).select_from(AuditLog)).one(),
        tuple(
            db.exec(
                select(
                    ProductUnit.unit_id,
                    ProductUnit.lifecycle_status,
                    ProductUnit.current_holder_company_id,
                    ProductUnit.last_sold_at,
                    ProductUnit.updated_at,
                ).order_by(ProductUnit.unit_id)
            ).all()
        ),
    )


def test_lookup_changes_nothing_and_returns_no_internal_ids(world: World):
    _, token = world.unit()
    _, sold = world.unit(status=S.SOLD, last_sold_at=utc_now())
    before = _snapshot(world.db)

    response = world.signed("units/lookup", world.body(code=token))
    world.signed("units/lookup", world.body(code=sold))

    assert response.status_code == 200
    assert _snapshot(world.db) == before
    body = response.json()
    assert body == {
        "subject": "UNIT",
        "code_last4": token[-4:],
        "product_name": "Sample Palm Oil",
        "brand": "Demo Harvest",
        "size": "1 L",
        "gtin": "96385074",
        "batch_number": "DEMO-LOT-001",
        "expiry_date": None,
        "status": "RELEASED",
        "warning": None,
    }
    assert not UUID_PATTERN.search(response.text)
    assert token not in response.text


@pytest.mark.parametrize(
    ("status", "code", "message"),
    [
        (S.RECALLED, "RECALLED", "Covered by a recall from the manufacturer. Don't sell."),
        (S.ISSUED, "UNRELEASED", "Not yet released for sale by the manufacturer. Don't sell."),
        (S.VOIDED, "VOIDED", "This code was voided by the manufacturer. Don't sell."),
    ],
)
def test_lookup_warns_about_units_that_should_not_be_sold(world: World, status, code, message):
    _, token = world.unit(status=status)

    response = world.signed("units/lookup", world.body(code=token))

    assert response.json()["warning"] == {"code": code, "message": message}


def test_lookup_warns_about_a_sold_pack_with_its_date(world: World):
    from datetime import datetime

    from app.services.check import WAT

    _, token = world.unit(status=S.SOLD, last_sold_at=datetime(2026, 10, 28, 9, 0, tzinfo=WAT))

    response = world.signed("units/lookup", world.body(code=token))

    assert response.json()["warning"] == {
        "code": "ALREADY_SOLD",
        "message": (
            "Already recorded as sold on 28 Oct 2026. Don't sell this pack until it's checked."
        ),
    }


def test_lookup_of_an_unknown_code_is_404(world: World):
    response = world.signed("units/lookup", world.body(code=identity.new_token()))

    assert response.status_code == 404
    assert error_code(response) == "UNKNOWN_CODE"


# --- Retailer and till -----------------------------------------------------------------------


def test_an_unlinked_retailer_is_rejected(world: World):
    other, _ = world.make_retailer()
    unit, token = world.unit()
    body = world.sale_body(token) | {"retailer_id": str(other.company_id)}

    response = world.signed("sales", body)

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "RETAILER_NOT_LINKED",
        "message": (
            "This retailer is not linked to your POS account, or is not approved on FoodLens."
        ),
    }
    assert world.events(unit) == []


def test_a_revoked_link_is_rejected(world: World):
    found = pos_admin.get_partner(world.db, world.partner.partner_id)
    ((link, _),) = found.links
    pos_admin.revoke_link(world.db, world.admin, world.partner.partner_id, link.link_id)
    _, token = world.unit()

    assert error_code(world.sell(token)) == "RETAILER_NOT_LINKED"


@pytest.mark.parametrize(
    "change",
    [
        {"review_status": CompanyReviewStatus.SUSPENDED},
        {"review_status": CompanyReviewStatus.PENDING_REVIEW},
        {"is_retailer": False, "is_distributor": True},
    ],
)
def test_an_unapproved_or_non_retailer_company_is_rejected(world: World, change):
    for field, value in change.items():
        setattr(world.retailer, field, value)
    world.db.add(world.retailer)
    world.db.flush()
    _, token = world.unit()

    assert error_code(world.sell(token)) == "RETAILER_NOT_LINKED"
    assert error_code(world.signed("units/lookup", world.body(code=token))) == (
        "RETAILER_NOT_LINKED"
    )


def test_an_unregistered_till_is_rejected(world: World):
    _, token = world.unit()

    response = world.signed("sales", world.sale_body(token) | {"till_id": "TILL-9"})

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "UNKNOWN_TILL",
        "message": "This till is not registered for the retailer.",
    }


def test_a_till_whose_location_is_no_longer_reviewed_is_rejected(world: World):
    world.location.review_status = ReviewStatus.REJECTED
    world.db.add(world.location)
    world.db.flush()
    _, token = world.unit()

    assert error_code(world.sell(token)) == "UNKNOWN_TILL"


def test_a_till_of_another_retailer_cannot_be_used(world: World):
    other, location = world.make_retailer()
    pos_admin.link_retailer(world.db, world.admin, world.partner.partner_id, other.company_id)
    pos_admin.add_till(
        world.db,
        world.admin,
        world.partner.partner_id,
        other.company_id,
        "TILL-K",
        location.location_id,
    )
    _, token = world.unit()

    response = world.signed("sales", world.sale_body(token) | {"till_id": "TILL-K"})

    assert error_code(response) == "UNKNOWN_TILL"


# --- No payment data (D122) ------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [{"amount": 1500}, {"card_number": "4111111111111111"}, {"customer_phone": "08000000000"}],
)
def test_payment_and_customer_fields_are_refused(world: World, extra):
    unit, token = world.unit()

    response = world.signed("sales", world.sale_body(token) | extra)

    assert response.status_code == 422
    assert error_code(response) == "INVALID_BODY"
    assert world.events(unit) == []


def test_a_payment_reference_longer_than_100_characters_is_refused(world: World):
    _, token = world.unit()

    response = world.sell(token, payment_reference="P" * 101)

    assert error_code(response) == "INVALID_BODY"


def test_no_column_can_hold_amounts_card_or_customer_data(engine):
    columns = {c["name"] for c in inspect(engine).get_columns("lifecycle_event")}
    banned = {"amount", "price", "total", "card", "pan", "customer", "phone", "email", "checkout"}
    assert not [c for c in columns if banned & set(c.split("_"))]
    assert {"transaction_ref", "payment_reference"} <= columns


def test_the_signing_secret_and_key_are_never_stored_in_plain_text(world: World):
    partner = world.db.get(PosPartner, world.partner.partner_id)
    assert world.secret not in partner.signing_secret_encrypted
    assert (
        Fernet(world.settings.pos_secret_key.encode())
        .decrypt(partner.signing_secret_encrypted.encode())
        .decode()
        == world.secret
    )
    (key,) = world.db.exec(
        select(PosPartnerKey).where(PosPartnerKey.partner_id == partner.partner_id)
    ).all()
    assert key.key_hash == hashlib.sha256(world.key.encode()).hexdigest()
    assert key.key_prefix == world.key[:8]
    audit = world.db.exec(select(AuditLog)).all()
    stored = json.dumps([[a.old_values, a.new_values] for a in audit])
    assert world.secret not in stored and world.key not in stored


# --- Rate limit (D119) -----------------------------------------------------------------------


def test_the_per_partner_rate_limit(session: Session, make_client):
    settings = pos_settings(
        rate_limit_enabled=True, rate_limit_pos_burst=2, rate_limit_pos_refill_per_second=0.001
    )
    world = build_world(session, make_client, settings)
    _, token = world.unit()
    body = world.body(code=token)

    assert world.signed("units/lookup", body).status_code == 200
    assert world.signed("units/lookup", body).status_code == 200
    limited = world.signed("units/lookup", body)

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.json()["error"]["message"].startswith("Too many requests. Try again in ")
    counted = session.exec(
        select(RateLimitDaily).where(RateLimitDaily.bucket == RateLimitBucket.POS)
    ).one()
    assert counted.count == 1 and counted.area_id is None

    # Another partner has its own bucket.
    found, key, secret = pos_admin.create_partner(session, settings, world.admin, "Other Till Co")
    pos_admin.link_retailer(
        session, world.admin, found.partner.partner_id, world.retailer.company_id
    )
    pos_admin.add_till(
        session,
        world.admin,
        found.partner.partner_id,
        world.retailer.company_id,
        "TILL-1",
        world.location.location_id,
    )
    assert world.signed("units/lookup", body, key=key, secret=secret).status_code == 200


# --- What a consumer sees --------------------------------------------------------------------


def test_a_consumer_check_after_a_pos_sale_shows_just_sold(world: World):
    unit, token = world.unit()
    world.sell(token)

    check = world.check(token)

    assert check["result"] == "RECOGNISED_JUST_SOLD"
    assert "Just sold by Demo Corner Shop, Lagos" in check["message"]
    assert "at the shop till" in json.dumps(check)
    assert world.refresh(unit).lifecycle_status == S.SOLD  # the check changed nothing


# --- Replay matches the direct writes ---------------------------------------------------------


def test_replay_gives_the_same_state_as_merchant_writes(world: World):
    member_user = f.make_user(world.db)
    member = f.make_member(world.db, member_user, world.retailer, role=MemberRole.OWNER)
    unit, token = world.unit()
    for event_type in (E.RECEIVED, E.SOLD, E.RETURNED, E.SOLD):
        lifecycle.record_merchant_event(world.db, member, token, event_type)
    stored = world.refresh(unit)
    before = (
        stored.lifecycle_status,
        stored.current_holder_company_id,
        stored.last_sold_at,
        stored.last_sold_area_id,
        stored.last_sold_company_id,
    )

    lifecycle.replay_unit(world.db, stored)

    replayed = world.refresh(unit)
    assert (
        replayed.lifecycle_status,
        replayed.current_holder_company_id,
        replayed.last_sold_at,
        replayed.last_sold_area_id,
        replayed.last_sold_company_id,
    ) == before


# --- Admin -----------------------------------------------------------------------------------


def signed_in(world: World, user: AppUser) -> TestClient:
    client = world.make_client(settings=world.settings)
    login = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert login.status_code == 200
    return client


def test_admin_routes_need_an_admin(world: World):
    user = f.make_user(world.db, password_hash=hash_password(PASSWORD))
    member = signed_in(world, user)
    anonymous = world.make_client(settings=world.settings)
    pid = world.partner.partner_id

    for client, status in ((anonymous, 401), (member, 403)):
        assert client.get("/api/admin/pos/partners").status_code == status
        assert client.post("/api/admin/pos/partners", json={"name": "X"}).status_code == status
        assert client.post(f"/api/admin/pos/partners/{pid}/keys").status_code == status
        assert client.get("/api/admin/pos/retailers").status_code == status


def test_admin_creates_a_partner_and_sees_the_credentials_once(world: World):
    admin = signed_in(world, world.admin)

    created = admin.post("/api/admin/pos/partners", json={"name": "Sample Checkout Co (fictional)"})

    assert created.status_code == 201
    credentials = created.json()["credentials"]
    assert credentials["api_key"].startswith("flk_")
    assert credentials["signing_secret"].startswith("fls_")
    listing = admin.get("/api/admin/pos/partners")
    assert listing.status_code == 200
    assert credentials["api_key"] not in listing.text
    assert credentials["signing_secret"] not in listing.text
    partner = next(p for p in listing.json() if p["name"] == "Sample Checkout Co (fictional)")
    assert partner["keys"][0]["key_prefix"] == credentials["api_key"][:8]
    assert world.db.exec(
        select(AuditLog).where(AuditLog.entity_type == "pos_partner", AuditLog.action == "create")
    ).all()


def test_admin_cannot_create_a_partner_without_pos_secret_key(session: Session, make_client):
    world = build_world(session, make_client, pos_settings())
    client = make_client(settings=pos_settings(pos_secret_key=""))
    login = client.post("/api/auth/login", json={"email": world.admin.email, "password": PASSWORD})
    assert login.status_code == 200

    response = client.post("/api/admin/pos/partners", json={"name": "No Key Co"})

    assert response.status_code == 503
    assert response.json()["detail"] == "POS integration is not set up on this server."


def test_admin_links_only_approved_retailers(world: World):
    admin = signed_in(world, world.admin)
    pid = world.partner.partner_id
    distributor = f.make_company(
        world.db, is_manufacturer=False, is_distributor=True, review_status="APPROVED"
    )
    pending, _ = world.make_retailer(
        "Pending Shop", review_status=CompanyReviewStatus.PENDING_REVIEW
    )

    for company in (distributor, pending, world.manufacturer):
        response = admin.post(
            f"/api/admin/pos/partners/{pid}/retailers",
            json={"retailer_id": str(company.company_id)},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Choose an approved retailer company."
    again = admin.post(
        f"/api/admin/pos/partners/{pid}/retailers",
        json={"retailer_id": str(world.retailer.company_id)},
    )
    assert again.status_code == 409


def test_admin_adds_tills_only_on_the_retailers_reviewed_locations(world: World):
    admin = signed_in(world, world.admin)
    pid = world.partner.partner_id
    other, other_location = world.make_retailer()
    path = f"/api/admin/pos/partners/{pid}/tills"

    unlinked = admin.post(
        path,
        json={
            "retailer_id": str(other.company_id),
            "till_ref": "T2",
            "location_id": str(other_location.location_id),
        },
    )
    assert unlinked.status_code == 422
    assert unlinked.json()["detail"] == "Link the retailer to this partner first."

    wrong_location = admin.post(
        path,
        json={
            "retailer_id": str(world.retailer.company_id),
            "till_ref": "T2",
            "location_id": str(other_location.location_id),
        },
    )
    assert wrong_location.status_code == 422
    assert wrong_location.json()["detail"] == (
        "Choose a reviewed location of this retailer that has an area."
    )

    duplicate = admin.post(
        path,
        json={
            "retailer_id": str(world.retailer.company_id),
            "till_ref": "TILL-1",
            "location_id": str(world.location.location_id),
        },
    )
    assert duplicate.status_code == 409

    added = admin.post(
        path,
        json={
            "retailer_id": str(world.retailer.company_id),
            "till_ref": "TILL-2",
            "location_id": str(world.location.location_id),
        },
    )
    assert added.status_code == 200
    till = next(t for t in added.json()["tills"] if t["till_ref"] == "TILL-2")
    removed = admin.delete(f"{path}/{till['till_id']}")
    assert removed.status_code == 200
    assert [t["till_ref"] for t in removed.json()["tills"]] == ["TILL-1"]


def test_removing_a_till_keeps_the_events_that_used_it(world: World):
    unit, token = world.unit()
    world.sell(token)
    till = world.db.exec(select(PosTill).where(PosTill.till_ref == "TILL-1")).one()

    pos_admin.remove_till(world.db, world.admin, world.partner.partner_id, till.till_id)

    (sale,) = world.events(unit, E.SOLD)
    assert sale.till_ref == "TILL-1"
    assert error_code(world.sell(world.unit()[1])) == "UNKNOWN_TILL"


def test_retailer_options_list_only_approved_retailers_with_reviewed_locations(world: World):
    admin = signed_in(world, world.admin)

    options = admin.get("/api/admin/pos/retailers").json()

    names = [o["display_name"] for o in options]
    assert "Demo Corner Shop" in names
    assert world.manufacturer.display_name not in names
    shop = next(o for o in options if o["display_name"] == "Demo Corner Shop")
    assert [loc["name"] for loc in shop["locations"]] == ["Main shop"]


# --- Simulated till (D123, D151) -------------------------------------------------------------


def shop_client(world: World) -> TestClient:
    user = f.make_user(world.db, password_hash=hash_password(PASSWORD))
    f.make_member(world.db, user, world.retailer, role=MemberRole.STAFF)
    return signed_in(world, user)


def test_demo_routes_are_absent_when_the_flag_is_off(session: Session, make_client):
    world = build_world(session, make_client, pos_settings(demo_pos_enabled=False))
    client = shop_client(world)

    assert client.get("/api/demo/pos/tills").status_code == 404
    assert (
        client.post("/api/demo/pos/sales", json={"till_ref": "TILL-1", "code": "X"}).status_code
        == 404
    )


def test_the_demo_till_records_through_the_signed_path(world: World):
    client = shop_client(world)
    unit, token = world.unit()

    tills = client.get("/api/demo/pos/tills")
    assert tills.json() == [
        {
            "till_ref": "TILL-1",
            "retailer_name": "Demo Corner Shop",
            "location_name": "Main shop",
            "area": "Lagos",
        }
    ]
    lookup = client.post("/api/demo/pos/lookup", json={"till_ref": "TILL-1", "code": token})
    assert lookup.json()["status"] == "RELEASED"
    assert lookup.json()["warning"] is None

    sale = client.post("/api/demo/pos/sales", json={"till_ref": "TILL-1", "code": token})

    assert sale.status_code == 200, sale.text
    assert sale.json()["recorded"] == 1
    assert sale.json()["transaction_id"].startswith("DEMO-TXN-")
    (event,) = world.events(unit, E.SOLD)
    assert event.source == EventSource.POS_API
    assert event.pos_partner_id == world.partner.partner_id
    assert event.payment_reference.startswith("DEMO-PAY-")
    assert world.secret not in sale.text and world.key not in sale.text
    assert "Just sold by Demo Corner Shop" in world.check(token)["message"]

    sold = client.post("/api/demo/pos/lookup", json={"till_ref": "TILL-1", "code": token})
    assert sold.json()["warning"]["code"] == "ALREADY_SOLD"

    refund = client.post("/api/demo/pos/refunds", json={"till_ref": "TILL-1", "code": token})
    assert refund.json()["recorded"] == 1
    assert world.refresh(unit).lifecycle_status == S.IN_STOCK

    client.post("/api/demo/pos/sales", json={"till_ref": "TILL-1", "code": token})
    no_reason = client.post("/api/demo/pos/voids", json={"till_ref": "TILL-1", "code": token})
    assert error_code(no_reason) == "NEED_REASON"
    void = client.post(
        "/api/demo/pos/voids",
        json={"till_ref": "TILL-1", "code": token, "reason": "Rang up the wrong pack"},
    )
    assert void.json()["recorded"] == 1
    assert [e.event_type for e in world.events(unit)] == [
        E.SOLD,
        E.RETURNED,
        E.SOLD,
        E.SALE_CORRECTED,
    ]


def test_the_demo_till_needs_a_linked_retailer_member(world: World):
    anonymous = world.make_client(settings=world.settings)
    assert anonymous.get("/api/demo/pos/tills").status_code == 401

    outsider = signed_in(world, f.make_user(world.db, password_hash=hash_password(PASSWORD)))
    response = outsider.get("/api/demo/pos/tills")
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "NOT_A_RETAILER",
        "message": "Sign in as a member of a retailer linked to the demo till.",
    }

    other, _ = world.make_retailer()
    user = f.make_user(world.db, password_hash=hash_password(PASSWORD))
    f.make_member(world.db, user, other)
    unlinked = signed_in(world, user)
    assert unlinked.get("/api/demo/pos/tills").json() == []
    _, token = world.unit()
    refused = unlinked.post("/api/demo/pos/sales", json={"till_ref": "TILL-1", "code": token})
    assert error_code(refused) == "RETAILER_NOT_LINKED"


def test_the_demo_till_honours_a_suspended_partner(world: World):
    client = shop_client(world)
    pos_admin.set_status(
        world.db, world.admin, world.partner.partner_id, PosPartnerStatus.SUSPENDED
    )

    response = client.get("/api/demo/pos/tills")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "DEMO_NOT_SET_UP",
        "message": "The demo till is not set up on this server.",
    }


# --- Wording (CLAUDE.md rule 1) --------------------------------------------------------------


def test_pos_wording_avoids_banned_words():
    banned = re.compile(
        r"\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac", re.I
    )
    from app.services import pos as pos_service
    from app.services import pos_auth

    modules = (pos_service, pos_auth, demo_pos, pos_admin)
    texts = [v for m in modules for k, v in vars(m).items() if k.startswith(("MSG_", "WARN_"))]
    texts += [pos_service.warn_sold("1 Oct 2026"), pos_service.msg_event_too_old(7)]
    assert len(texts) > 20
    assert not [t for t in texts if banned.search(t)]
