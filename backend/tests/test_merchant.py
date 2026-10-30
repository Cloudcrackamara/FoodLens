"""Merchant page (Phase 4): custody, carton events, returns, corrections, rejected states, company
and approval blocks, allocation notes, staff, and what a consumer sees afterwards."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, func, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AllocationCarton,
    AllocationUnit,
    AppUser,
    Carton,
    Company,
    CompanyMember,
    LifecycleEvent,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    SupplierLocation,
)
from app.models.enums import (
    AnnouncementKind,
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    MemberRole,
    MembershipStatus,
    ProductStatus,
    ReviewStatus,
)
from app.services import identity
from tests import factories as f

PASSWORD = "correct-horse-battery"
E = LifecycleEventType
S = LifecycleStatus


@dataclass
class Shop:
    client: TestClient
    user: AppUser
    company: Company
    member: CompanyMember

    @property
    def base(self) -> str:
        return f"/api/companies/{self.company.company_id}"

    def lookup(self, code: str):
        return self.client.post(f"{self.base}/merchant/lookup", json={"code": code})

    def event(self, code: str, event_type: E, **extra):
        return self.client.post(
            f"{self.base}/merchant/events", json={"code": code, "event_type": event_type} | extra
        )


@dataclass
class World:
    db: Session
    manufacturer: Company
    batch: ProductBatch
    owner: AppUser
    make_shop: Callable[..., Shop]

    def unit(self, status=S.RELEASED, carton: Carton | None = None, **overrides):
        """A released unit held by the manufacturer, and its raw code."""
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

    def carton(self, units: int = 3, status=S.RELEASED):
        token = identity.new_token()
        carton = f.make_carton(
            self.db,
            self.batch,
            self.manufacturer,
            qr_token_hash=identity.token_hash(token),
            lifecycle_status=status,
            current_holder_company_id=self.manufacturer.company_id,
        )
        members = [self.unit(status=status, carton=carton) for _ in range(units)]
        return carton, token, members

    def events(self, event_type: E, **where) -> list[LifecycleEvent]:
        statement = select(LifecycleEvent).where(LifecycleEvent.event_type == event_type)
        for column, value in where.items():
            statement = statement.where(getattr(LifecycleEvent, column) == value)
        return list(self.db.exec(statement.order_by(LifecycleEvent.recorded_at)).all())

    def refresh(self, unit: ProductUnit) -> ProductUnit:
        self.db.expire(unit)
        return self.db.get(ProductUnit, unit.unit_id)


@pytest.fixture
def world(session: Session, make_client: Callable[..., TestClient]) -> World:
    manufacturer = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    product = f.make_product(session, manufacturer, status=ProductStatus.PUBLISHED)
    batch = f.make_batch(session, product, review_status=ReviewStatus.APPROVED)
    owner = f.make_user(session)

    def make_shop(
        name: str = "Demo Corner Shop",
        *,
        role=MemberRole.OWNER,
        company: Company | None = None,
        status=CompanyReviewStatus.APPROVED,
        city: str | None = "Lagos",
        location_status=ReviewStatus.APPROVED,
        **flags,
    ) -> Shop:
        client = make_client(settings=Settings(rate_limit_enabled=False))
        user = f.make_user(session, password_hash=hash_password(PASSWORD))
        if company is None:
            flags = {"is_manufacturer": False, "is_retailer": True} | flags
            company = f.make_company(session, display_name=name, review_status=status, **flags)
            if city:
                session.add(
                    SupplierLocation(
                        company_id=company.company_id,
                        name="Main shop",
                        address="1 Demo Street",
                        area=city,
                        area_id=f.area(session, city).area_id,
                        review_status=location_status,
                    )
                )
                session.flush()
        member = f.make_member(session, user, company, role=role)
        login = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
        assert login.status_code == 200
        return Shop(client, user, company, member)

    return World(session, manufacturer, batch, owner, make_shop)


def count_events(db: Session) -> int:
    return db.exec(select(func.count()).select_from(LifecycleEvent)).one()


# --- Custody (D113) ---------------------------------------------------------------------------


def test_sale_without_a_transfer_is_allowed_and_labelled(world: World):
    shop = world.make_shop()
    unit, token = world.unit()

    response = shop.event(token, E.SOLD)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status_after"] == "SOLD"
    assert body["packs"] == 1
    assert body["notes"] == ["Received without a recorded transfer."]
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.SOLD
    assert unit.current_holder_company_id == shop.company.company_id
    assert unit.last_sold_company_id == shop.company.company_id
    assert unit.last_sold_area_id == f.area(world.db, "Lagos").area_id
    (event,) = world.events(E.SOLD)
    assert event.source == EventSource.MERCHANT_APP
    assert event.actor_user_id == shop.user.user_id
    assert event.actor_company_id == shop.company.company_id
    assert event.received_without_transfer is True


def test_receipt_without_a_transfer_is_allowed_and_labelled(world: World):
    shop = world.make_shop()
    unit, token = world.unit()

    response = shop.event(token, E.RECEIVED)

    assert response.status_code == 200
    assert response.json()["notes"] == ["Received without a recorded transfer."]
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.current_holder_company_id == shop.company.company_id
    assert world.events(E.RECEIVED)[0].received_without_transfer is True


def test_a_receipt_after_a_transfer_to_the_company_is_not_labelled(world: World):
    distributor = world.make_shop("Demo Distribution", is_retailer=False, is_distributor=True)
    shop = world.make_shop()
    unit, token = world.unit()

    assert distributor.event(token, E.RECEIVED).status_code == 200
    sent = distributor.event(token, E.TRANSFERRED, to_company_id=str(shop.company.company_id))
    assert sent.status_code == 200
    assert sent.json()["status_after"] == "IN_TRANSIT"
    assert world.refresh(unit).current_holder_company_id == shop.company.company_id

    received = shop.event(token, E.RECEIVED)

    assert received.status_code == 200
    assert received.json()["notes"] == []
    assert (
        world.events(E.RECEIVED, actor_company_id=shop.company.company_id)[
            0
        ].received_without_transfer
        is False
    )
    assert world.events(E.TRANSFERRED)[0].to_company_id == shop.company.company_id


def test_only_the_holder_can_transfer(world: World):
    shop = world.make_shop()
    other = world.make_shop("Demo Other Shop")
    _, token = world.unit()
    before = count_events(world.db)

    refused = shop.event(token, E.TRANSFERRED, to_company_id=str(other.company.company_id))

    assert refused.status_code == 409
    assert (
        refused.json()["detail"] == "Only the company holding this pack in stock can transfer it."
    )
    assert count_events(world.db) == before


def test_a_transfer_needs_another_approved_company(world: World):
    shop = world.make_shop()
    pending = f.make_company(world.db, review_status=CompanyReviewStatus.PENDING_REVIEW)
    _, token = world.unit()
    shop.event(token, E.RECEIVED)

    missing = shop.event(token, E.TRANSFERRED)
    unapproved = shop.event(token, E.TRANSFERRED, to_company_id=str(pending.company_id))
    itself = shop.event(token, E.TRANSFERRED, to_company_id=str(shop.company.company_id))
    unknown = shop.event(token, E.TRANSFERRED, to_company_id=str(uuid.uuid4()))

    assert [r.status_code for r in (missing, unapproved, itself, unknown)] == [422] * 4
    assert missing.json()["detail"] == "Choose the company receiving the stock."
    assert unapproved.json()["detail"] == "Choose another approved company."


# --- Cartons ----------------------------------------------------------------------------------


def test_a_carton_event_applies_to_every_unit_and_shares_a_group(world: World):
    shop = world.make_shop()
    carton, token, members = world.carton(units=3)

    response = shop.event(token, E.RECEIVED)

    assert response.status_code == 200
    body = response.json()
    assert (body["subject"], body["packs"], body["status_after"]) == ("CARTON", 3, "IN_STOCK")
    for unit, _ in members:
        unit = world.refresh(unit)
        assert unit.lifecycle_status == S.IN_STOCK
        assert unit.current_holder_company_id == shop.company.company_id
    events = world.events(E.RECEIVED)
    assert len(events) == 4  # one carton row plus one per unit
    assert len({e.group_id for e in events}) == 1
    assert sum(e.carton_id is not None for e in events) == 1
    world.db.expire(carton)
    assert world.db.get(Carton, carton.carton_id).lifecycle_status == S.IN_STOCK


def test_units_in_a_received_carton_can_still_be_handled_one_by_one(world: World):
    shop = world.make_shop()
    _, carton_token, members = world.carton(units=2)
    shop.event(carton_token, E.RECEIVED)
    (first, first_token), (second, _) = members

    sold = shop.event(first_token, E.SOLD)

    assert sold.status_code == 200
    assert sold.json()["notes"] == []
    assert world.refresh(first).lifecycle_status == S.SOLD
    assert world.refresh(second).lifecycle_status == S.IN_STOCK


def test_a_carton_with_one_sold_unit_is_refused_as_a_whole(world: World):
    shop = world.make_shop()
    _, carton_token, members = world.carton(units=3)
    other = world.make_shop("Demo Other Shop")
    other.event(members[0][1], E.SOLD)
    before = count_events(world.db)

    refused = shop.event(carton_token, E.RECEIVED)

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "1 of the 3 packs in this carton can't take this event. "
        "This pack is already recorded as sold."
    )
    assert count_events(world.db) == before
    assert world.refresh(members[1][0]).lifecycle_status == S.RELEASED


# --- Returns and corrections (D140) -----------------------------------------------------------


def test_only_the_seller_can_return_a_sale(world: World):
    seller = world.make_shop()
    other = world.make_shop("Demo Other Shop")
    distributor = world.make_shop("Demo Distribution", is_retailer=False, is_distributor=True)
    unit, token = world.unit()
    seller.event(token, E.SOLD)
    before = count_events(world.db)

    for outsider in (other, distributor):
        refused = outsider.event(token, E.RETURNED)
        assert refused.status_code == 403
        assert refused.json()["detail"] == "Only the company that recorded the sale can do this."
        assert outsider.event(token, E.SALE_CORRECTED, reason="Wrong pack").status_code == 403

    assert count_events(world.db) == before
    assert world.refresh(unit).lifecycle_status == S.SOLD


def test_a_return_puts_the_unit_back_in_stock_and_keeps_the_sale(world: World):
    seller = world.make_shop()
    unit, token = world.unit()
    seller.event(token, E.SOLD)
    (sale,) = world.events(E.SOLD)

    returned = seller.event(token, E.RETURNED)

    assert returned.status_code == 200
    assert returned.json()["status_after"] == "IN_STOCK"
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.current_holder_company_id == seller.company.company_id
    assert (unit.last_sold_at, unit.last_sold_area_id, unit.last_sold_company_id) == (
        None,
        None,
        None,
    )
    assert [e.event_id for e in world.events(E.SOLD)] == [sale.event_id]
    (ret,) = world.events(E.RETURNED)
    assert ret.returns_event_id == sale.event_id
    # The unit can be sold again.
    assert seller.event(token, E.SOLD).status_code == 200


def test_a_correction_needs_a_reason_and_keeps_the_original_sale(world: World):
    seller = world.make_shop()
    unit, token = world.unit()
    seller.event(token, E.SOLD)
    (sale,) = world.events(E.SOLD)

    for reason in (None, "", "   "):
        extra = {} if reason is None else {"reason": reason}
        refused = seller.event(token, E.SALE_CORRECTED, **extra)
        assert refused.status_code == 422
        assert refused.json()["detail"] == "Give a reason for the correction."
    assert world.refresh(unit).lifecycle_status == S.SOLD

    corrected = seller.event(token, E.SALE_CORRECTED, reason="Rung up the wrong pack")

    assert corrected.status_code == 200
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.last_sold_company_id is None
    assert [e.event_id for e in world.events(E.SOLD)] == [sale.event_id]
    (fix,) = world.events(E.SALE_CORRECTED)
    assert fix.corrects_event_id == sale.event_id
    assert fix.reason == "Rung up the wrong pack"


def test_a_return_needs_a_recorded_sale(world: World):
    shop = world.make_shop()
    _, token = world.unit()
    shop.event(token, E.RECEIVED)

    refused = shop.event(token, E.RETURNED)

    assert refused.status_code == 409
    assert refused.json()["detail"] == "This pack is not recorded as sold."


def test_a_consumer_check_after_a_merchant_sale_shows_just_sold(world: World, make_client):
    shop = world.make_shop()
    unit, token = world.unit()
    shop.event(token, E.SOLD)
    consumer = make_client(settings=Settings(rate_limit_enabled=False))

    sold = consumer.post("/api/check/qr", json={"code": token, "identifier_type": "QR"}).json()

    assert sold["result"] == "RECOGNISED_JUST_SOLD"
    assert "Just sold by Demo Corner Shop, Lagos" in sold["message"]
    assert world.refresh(unit).lifecycle_status == S.SOLD  # the check changed nothing

    shop.event(token, E.RETURNED)
    again = consumer.post("/api/check/qr", json={"code": token, "identifier_type": "QR"}).json()

    assert again["result"] == "RECOGNISED_NOT_SOLD"
    assert again["title"] == "In circulation, not yet sold"


# --- Rejected states --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (S.VOIDED, "This code was voided by the manufacturer, so it can't be recorded."),
        (
            S.ISSUED,
            "The manufacturer has not released this code for sale yet, so it can't be recorded.",
        ),
        (S.RECALLED, "This pack is covered by a recall, so it can't be recorded."),
    ],
)
@pytest.mark.parametrize("event", [E.RECEIVED, E.SOLD, E.RETURNED])
def test_voided_unreleased_and_recalled_units_are_rejected(world: World, status, message, event):
    shop = world.make_shop()
    unit, token = world.unit(status=status)
    before = count_events(world.db)

    refused = shop.event(token, event)

    assert refused.status_code == 409
    assert refused.json()["detail"] == message
    assert count_events(world.db) == before
    assert world.refresh(unit).lifecycle_status == status


def test_a_live_recall_on_the_batch_blocks_every_event(world: World):
    shop = world.make_shop()
    _, token = world.unit()
    product_id = world.batch.product_id
    world.db.add(
        ProductAnnouncement(
            kind=AnnouncementKind.RECALL,
            product_id=product_id,
            batch_id=world.batch.batch_id,
            recall_reason="Packaging fault",
            title="Batch recall",
            message="Return this batch to the seller.",
            created_by_user_id=world.owner.user_id,
        )
    )
    world.db.flush()

    refused = shop.event(token, E.SOLD)

    assert refused.status_code == 409
    assert refused.json()["detail"] == "This pack is covered by a recall, so it can't be recorded."
    assert shop.lookup(token).json()["recalled"] is True


def test_a_sold_unit_cannot_be_received_sold_or_transferred_again(world: World):
    shop = world.make_shop()
    other = world.make_shop("Demo Other Shop")
    _, token = world.unit()
    shop.event(token, E.SOLD)

    for event, extra in (
        (E.RECEIVED, {}),
        (E.SOLD, {}),
        (E.TRANSFERRED, {"to_company_id": str(shop.company.company_id)}),
    ):
        refused = other.event(token, event, **extra)
        assert refused.status_code == 409
        assert refused.json()["detail"] == "This pack is already recorded as sold."


def test_an_unknown_code_is_not_found(world: World):
    shop = world.make_shop()

    assert shop.event(identity.new_token(), E.SOLD).status_code == 404
    assert shop.lookup("not a code").status_code == 404


def test_a_unit_of_an_unapproved_manufacturer_is_not_found(world: World):
    shop = world.make_shop()
    _, token = world.unit()
    world.manufacturer.review_status = CompanyReviewStatus.SUSPENDED
    world.db.flush()

    assert shop.event(token, E.SOLD).status_code == 404


def test_only_merchant_event_types_are_accepted(world: World):
    shop = world.make_shop()
    _, token = world.unit()

    for event in (E.ISSUED, E.RELEASED, E.VOIDED, E.RECALLED):
        assert shop.event(token, event).status_code == 422
    assert (
        shop.client.post(
            f"{shop.base}/merchant/events", json={"code": token, "event_type": "WITHDRAWN"}
        ).status_code
        == 422
    )


# --- Companies, approval and server-side control ---------------------------------------------


def test_cross_company_and_anonymous_access_is_blocked(world: World, make_client):
    shop = world.make_shop()
    other = world.make_shop("Demo Other Shop")
    _, token = world.unit()

    # Signed in, but for another company's path.
    other_path = f"/api/companies/{other.company.company_id}/merchant/events"
    forged = shop.client.post(other_path, json={"code": token, "event_type": "SOLD"})
    assert forged.status_code == 403
    assert (
        shop.client.post(
            f"/api/companies/{other.company.company_id}/merchant/lookup", json={"code": token}
        ).status_code
        == 403
    )
    assert (
        shop.client.get(
            f"/api/companies/{other.company.company_id}/merchant/destinations"
        ).status_code
        == 403
    )

    anonymous = make_client().post(
        f"{shop.base}/merchant/events", json={"code": token, "event_type": "SOLD"}
    )
    assert anonymous.status_code == 401
    assert world.events(E.SOLD) == []


@pytest.mark.parametrize(
    "status",
    [
        CompanyReviewStatus.PENDING_REVIEW,
        CompanyReviewStatus.REJECTED,
        CompanyReviewStatus.SUSPENDED,
    ],
)
def test_an_unapproved_company_cannot_record_events(world: World, status):
    shop = world.make_shop("Demo Pending Shop", status=status)
    _, token = world.unit()

    for response in (shop.event(token, E.SOLD), shop.lookup(token)):
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "Your company profile must be approved before you can record events."
        )
    assert world.events(E.SOLD) == []


def test_a_manufacturer_only_company_cannot_use_the_merchant_page(world: World):
    maker = world.make_shop("Demo Maker Only", is_manufacturer=True, is_retailer=False)
    _, token = world.unit()

    refused = maker.event(token, E.SOLD)

    assert refused.status_code == 403
    assert (
        refused.json()["detail"]
        == "Only distributor and retailer companies can record stock events."
    )


def test_the_event_area_comes_from_a_reviewed_location_only(world: World):
    unreviewed = world.make_shop(
        "Demo Unreviewed Shop", location_status=ReviewStatus.PENDING_REVIEW
    )
    no_location = world.make_shop("Demo No Location Shop", city=None)
    kano = world.make_shop("Demo Kano Shop", city="Kano")
    _, token = world.unit()
    expected = "Your company needs a reviewed location with an area before it can record events."

    for shop in (unreviewed, no_location):
        refused = shop.event(token, E.SOLD)
        assert refused.status_code == 409
        assert refused.json()["detail"] == expected

    assert kano.event(token, E.SOLD).status_code == 200
    assert world.events(E.SOLD)[0].area_id == f.area(world.db, "Kano").area_id


def test_the_client_cannot_set_status_holder_area_or_company(world: World):
    shop = world.make_shop()
    other = world.make_shop("Demo Other Shop")
    unit, token = world.unit()

    response = shop.event(
        token,
        E.RECEIVED,
        lifecycle_status="SOLD",
        current_holder_company_id=str(other.company.company_id),
        area_id=str(f.area(world.db, "Kano").area_id),
        actor_company_id=str(other.company.company_id),
        source="POS_API",
        received_without_transfer=False,
        to_company_id=str(other.company.company_id),
    )

    assert response.status_code == 200
    unit = world.refresh(unit)
    assert unit.lifecycle_status == S.IN_STOCK
    assert unit.current_holder_company_id == shop.company.company_id
    (event,) = world.events(E.RECEIVED)
    assert event.area_id == f.area(world.db, "Lagos").area_id
    assert event.actor_company_id == shop.company.company_id
    assert event.source == EventSource.MERCHANT_APP
    assert event.to_company_id is None
    assert event.received_without_transfer is True


def test_staff_can_record_events(world: World):
    owner = world.make_shop()
    staff = world.make_shop(role=MemberRole.STAFF, company=owner.company)
    _, token = world.unit()

    assert staff.event(token, E.SOLD).status_code == 200
    assert world.events(E.SOLD)[0].actor_user_id == staff.user.user_id


def test_lookup_describes_the_code_without_internal_ids(world: World):
    shop = world.make_shop()
    unit, token = world.unit()
    carton, carton_token, _ = world.carton(units=2)

    body = shop.lookup(token).json()
    assert body["subject"] == "UNIT"
    assert body["code_last4"] == identity.normalise(token)[-4:]
    assert body["product_name"] == "Sample Palm Oil"
    assert body["allowed_events"] == ["RECEIVED", "SOLD"]
    assert body["status_counts"] == [{"status": "RELEASED", "packs": 1}]
    assert str(unit.unit_id) not in str(body)

    carton_body = shop.lookup(carton_token).json()
    assert (carton_body["subject"], carton_body["packs"]) == ("CARTON", 2)
    assert str(carton.carton_id) not in str(carton_body)

    shop.event(token, E.SOLD)
    sold = shop.lookup(token).json()
    assert sold["allowed_events"] == ["RETURNED", "SALE_CORRECTED"]
    assert sold["sold_by_you"] == 1
    assert sold["blocked_reason"] is None

    other = world.make_shop("Demo Other Shop")
    blocked = other.lookup(token).json()
    assert blocked["allowed_events"] == []
    assert blocked["blocked_reason"] == "This pack is already recorded as sold."


def test_a_lookup_writes_nothing(world: World):
    shop = world.make_shop()
    unit, token = world.unit()
    before = count_events(world.db)

    shop.lookup(token)

    assert count_events(world.db) == before
    assert world.refresh(unit).lifecycle_status == S.RELEASED


def test_the_destinations_are_approved_companies_except_the_sender(world: World):
    shop = world.make_shop()
    approved = world.make_shop("Demo Other Shop")
    f.make_company(
        world.db, display_name="Demo Pending Co", review_status=CompanyReviewStatus.PENDING_REVIEW
    )

    names = [
        d["display_name"] for d in shop.client.get(f"{shop.base}/merchant/destinations").json()
    ]

    assert shop.company.display_name not in names
    assert approved.company.display_name in names
    assert "Demo Pending Co" not in names


# --- Allocation (D142): advisory ---------------------------------------------------------------


def test_a_batch_without_allocations_gets_no_note(world: World):
    shop = world.make_shop()
    _, token = world.unit()

    assert shop.event(token, E.RECEIVED).json()["notes"] == [
        "Received without a recorded transfer."
    ]
    assert world.events(E.RECEIVED)[0].outside_allocation is False


def test_a_receipt_inside_its_allocation_has_no_allocation_note(world: World):
    shop = world.make_shop()
    f.make_allocation(
        world.db,
        world.batch,
        world.owner,
        destination_company_id=shop.company.company_id,
        destination_area_id=f.area(world.db, "Lagos").area_id,
        quantity=5,
    )
    _, token = world.unit()

    response = shop.event(token, E.RECEIVED)

    assert "Received outside its allocation." not in response.json()["notes"]
    assert world.events(E.RECEIVED)[0].outside_allocation is False


def test_a_receipt_matching_no_allocation_gets_a_neutral_note_and_no_block(world: World):
    shop = world.make_shop()
    f.make_allocation(
        world.db,
        world.batch,
        world.owner,
        destination_area_id=f.area(world.db, "Kano").area_id,
        quantity=5,
    )
    unit, token = world.unit()

    response = shop.event(token, E.RECEIVED)

    assert response.status_code == 200
    assert "Received outside its allocation." in response.json()["notes"]
    assert world.events(E.RECEIVED)[0].outside_allocation is True
    assert world.refresh(unit).lifecycle_status == S.IN_STOCK
    assert world.db.exec(text("select count(*) from risk_alert")).one()[0] == 0


def test_quantity_allocations_count_down_with_each_receipt(world: World):
    shop = world.make_shop()
    f.make_allocation(
        world.db,
        world.batch,
        world.owner,
        destination_company_id=shop.company.company_id,
        destination_area_id=f.area(world.db, "Lagos").area_id,
        quantity=2,
    )
    codes = [world.unit()[1] for _ in range(3)]

    for code in codes:
        assert shop.event(code, E.RECEIVED).status_code == 200

    assert [e.outside_allocation for e in world.events(E.RECEIVED)] == [False, False, True]


def test_a_listed_unit_wins_over_the_quantity_allocation(world: World):
    shop = world.make_shop()
    lagos = f.area(world.db, "Lagos").area_id
    kano = f.area(world.db, "Kano").area_id
    f.make_allocation(
        world.db,
        world.batch,
        world.owner,
        destination_company_id=shop.company.company_id,
        destination_area_id=lagos,
        quantity=5,
    )
    elsewhere = f.make_allocation(
        world.db, world.batch, world.owner, destination_area_id=kano, quantity=1
    )
    unit, token = world.unit()
    world.db.add(AllocationUnit(allocation_id=elsewhere.allocation_id, unit_id=unit.unit_id))
    world.db.flush()

    shop.event(token, E.RECEIVED)

    # Listed for Kano, received in Lagos: outside, even though the Lagos quantity has room.
    assert world.events(E.RECEIVED)[0].outside_allocation is True


def test_a_listed_carton_belongs_to_its_allocation(world: World):
    shop = world.make_shop()
    allocation = f.make_allocation(
        world.db,
        world.batch,
        world.owner,
        destination_company_id=shop.company.company_id,
        destination_area_id=f.area(world.db, "Lagos").area_id,
        quantity=3,
    )
    carton, token, _ = world.carton(units=3)
    world.db.add(
        AllocationCarton(allocation_id=allocation.allocation_id, carton_id=carton.carton_id)
    )
    world.db.flush()

    shop.event(token, E.RECEIVED)

    assert all(e.outside_allocation is False for e in world.events(E.RECEIVED))


# --- Staff management (D106) ------------------------------------------------------------------


def test_the_owner_adds_and_deactivates_staff(world: World):
    owner = world.make_shop()
    newcomer = f.make_user(world.db, password_hash=hash_password(PASSWORD))

    added = owner.client.post(f"{owner.base}/members", json={"email": newcomer.email.upper()})

    assert added.status_code == 201
    body = added.json()
    assert (body["role"], body["membership_status"], body["email"]) == (
        "STAFF",
        "ACTIVE",
        newcomer.email,
    )
    roster = owner.client.get(f"{owner.base}/members").json()
    assert [m["role"] for m in roster] == ["OWNER", "STAFF"]

    staff_client = world.make_shop(company=owner.company, role=MemberRole.STAFF)  # another staff
    del staff_client
    gone = owner.client.post(f"{owner.base}/members/{body['member_id']}/deactivate")
    assert gone.status_code == 200
    assert gone.json()["membership_status"] == "INACTIVE"

    # Adding the same person again re-activates them.
    again = owner.client.post(f"{owner.base}/members", json={"email": newcomer.email})
    assert again.status_code == 201
    assert again.json()["membership_status"] == "ACTIVE"


def test_staff_cannot_manage_staff(world: World):
    owner = world.make_shop()
    staff = world.make_shop(role=MemberRole.STAFF, company=owner.company)
    someone = f.make_user(world.db)

    assert staff.client.get(f"{staff.base}/members").status_code == 403
    assert (
        staff.client.post(f"{staff.base}/members", json={"email": someone.email}).status_code == 403
    )
    assert (
        staff.client.post(f"{staff.base}/members/{owner.member.member_id}/deactivate").status_code
        == 403
    )


def test_a_deactivated_staff_member_loses_access(world: World):
    owner = world.make_shop()
    staff = world.make_shop(role=MemberRole.STAFF, company=owner.company)
    _, token = world.unit()
    assert staff.lookup(token).status_code == 200

    assert (
        owner.client.post(f"{owner.base}/members/{staff.member.member_id}/deactivate").status_code
        == 200
    )

    assert staff.lookup(token).status_code == 403
    assert staff.event(token, E.SOLD).status_code == 403


def test_staff_rules_for_unknown_taken_and_foreign_members(world: World):
    owner = world.make_shop()
    rival = world.make_shop("Demo Rival Shop")

    unknown = owner.client.post(f"{owner.base}/members", json={"email": "nobody@example.test"})
    taken = owner.client.post(f"{owner.base}/members", json={"email": rival.user.email})
    foreign = owner.client.post(f"{owner.base}/members/{rival.member.member_id}/deactivate")
    owner_row = owner.client.post(f"{owner.base}/members/{owner.member.member_id}/deactivate")

    assert [unknown.status_code, taken.status_code, foreign.status_code, owner_row.status_code] == [
        404,
        409,
        404,
        409,
    ]
    rival_member = world.db.get(CompanyMember, rival.member.member_id)
    assert rival_member.membership_status == MembershipStatus.ACTIVE


def test_no_new_text_uses_banned_words(world: World):
    from app.services import lifecycle, members

    banned = (
        "original",
        "genuine",
        "authentic",
        "safe",
        "unsafe",
        "fake",
        "adulteration",
        "nafdac",
    )
    texts = [
        value
        for module in (lifecycle, members)
        for name, value in vars(module).items()
        if name.startswith(("MSG_", "NOTE_")) and isinstance(value, str)
    ]
    assert texts
    for message in texts:
        assert not any(word in message.lower() for word in banned), message
