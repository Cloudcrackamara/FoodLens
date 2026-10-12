"""Wholesale order requests and supplier pages (D95-D100, CLAUDE.md rules 6-7)."""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import AppUser, AuditLog, Company, Product, SupplierLocation
from app.models.enums import (
    CompanyReviewStatus,
    CompanyType,
    MemberRole,
    OrderStatus,
    ProductStatus,
    RegisterStatus,
    ReviewStatus,
)
from tests import factories as f

PASSWORD = "correct-horse-battery"


@dataclass
class Party:
    client: TestClient
    user: AppUser
    company: Company

    @property
    def orders(self) -> str:
        return f"/api/companies/{self.company.company_id}/orders"


@dataclass
class Seller(Party):
    location: SupplierLocation
    oil: Product
    rice: Product


@pytest.fixture
def party(make_client: Callable[..., TestClient], session: Session):
    """A signed-in member of a new company, each with their own browser (client)."""

    def build(
        company_type=CompanyType.WHOLESALER,
        status=CompanyReviewStatus.APPROVED,
        name: str = "Demo Market Traders",
    ) -> Party:
        client = make_client()
        user = f.make_user(session, password_hash=hash_password(PASSWORD))
        company = f.make_company(
            session, company_type=company_type, review_status=status, display_name=name
        )
        f.make_member(session, user, company, role=MemberRole.OWNER)
        response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
        assert response.status_code == 200
        return Party(client, user, company)

    return build


def listed_location(session: Session, company: Company, **overrides) -> SupplierLocation:
    values = {
        "company_id": company.company_id,
        "name": "Demo Depot",
        "address": "1 Demo Street (fictional)",
        "area": "Demo Market",
        "review_status": ReviewStatus.APPROVED,
    }
    location = SupplierLocation(**(values | overrides))
    session.add(location)
    session.flush()
    return location


@pytest.fixture
def seller(party, session: Session) -> Seller:
    base = party(company_type=CompanyType.MANUFACTURER, name="Demo Harvest Foods")
    location = listed_location(session, base.company)
    oil = f.make_product(
        session, base.company, name="Sample Palm Oil", status=ProductStatus.PUBLISHED
    )
    rice = f.make_product(session, base.company, name="Sample Rice", status=ProductStatus.PUBLISHED)
    return Seller(base.client, base.user, base.company, location, oil, rice)


@pytest.fixture
def buyer(party) -> Party:
    return party()


def order_body(seller: Seller, **overrides) -> dict:
    body = {
        "lines": [{"product_id": str(seller.oil.product_id), "quantity": "10", "unit": "carton"}],
        "fulfilment_method": "PICKUP",
        "pickup_location_id": str(seller.location.location_id),
    }
    return body | overrides


def place(buyer: Party, seller: Seller, **overrides) -> dict:
    response = buyer.client.post(buyer.orders, json=order_body(seller, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def seller_action(seller: Seller, order: dict, action: str, **body):
    return seller.client.post(f"{seller.orders}/{order['order_id']}/{action}", json=body or {})


# --- Placing ------------------------------------------------------------------------------------


def test_wholesaler_places_pickup_order(buyer: Party, seller: Seller, session: Session) -> None:
    order = place(buyer, seller, buyer_note="Please pack in cartons")

    assert order["status"] == "REQUESTED"
    assert order["buyer"]["company_id"] == str(buyer.company.company_id)
    assert order["seller"]["company_id"] == str(seller.company.company_id)
    assert order["pickup_location"]["name"] == "Demo Depot"
    assert order["lines"][0]["product_name"] == "Sample Palm Oil"
    assert order["lines"][0]["unit"] == "carton"
    assert (
        session.exec(select(AuditLog).where(AuditLog.action == "order_requested")).first()
        is not None
    )


def test_both_type_company_can_order_with_delivery(party, seller: Seller) -> None:
    buyer = party(company_type=CompanyType.BOTH)

    order = place(
        buyer,
        seller,
        fulfilment_method="DELIVERY",
        pickup_location_id=None,
        delivery_details="Shop 4, Demo Market Road (fictional)",
    )

    assert order["fulfilment_method"] == "DELIVERY"
    assert order["pickup_location"] is None
    assert order["delivery_details"].startswith("Shop 4")


def test_client_cannot_set_status_or_company_ids(buyer: Party, seller: Seller, party) -> None:
    other = party(name="Someone Else")
    body = order_body(
        seller,
        status="FULFILLED",
        buyer_company_id=str(other.company.company_id),
        seller_company_id=str(other.company.company_id),
        created_by_user_id=str(other.user.user_id),
        seller_note="Accepted already",
    )

    order = buyer.client.post(buyer.orders, json=body).json()

    assert order["status"] == "REQUESTED"
    assert order["buyer"]["company_id"] == str(buyer.company.company_id)
    assert order["seller"]["company_id"] == str(seller.company.company_id)
    assert order["seller_note"] is None


@pytest.mark.parametrize("quantity", ["0", "-3"])
def test_non_positive_quantity_rejected(buyer: Party, seller: Seller, quantity: str) -> None:
    lines = [{"product_id": str(seller.oil.product_id), "quantity": quantity, "unit": "carton"}]

    assert buyer.client.post(buyer.orders, json=order_body(seller, lines=lines)).status_code == 422


@pytest.mark.parametrize("status", [ProductStatus.DRAFT, ProductStatus.WITHDRAWN])
def test_unpublished_product_rejected(
    buyer: Party, seller: Seller, session: Session, status: ProductStatus
) -> None:
    hidden = f.make_product(session, seller.company, status=status)
    lines = [{"product_id": str(hidden.product_id), "quantity": "1", "unit": "bag"}]

    response = buyer.client.post(buyer.orders, json=order_body(seller, lines=lines))

    assert response.status_code == 422
    assert "published" in response.json()["detail"]


def test_products_from_two_suppliers_rejected(
    buyer: Party, seller: Seller, party, session: Session
) -> None:
    second = party(company_type=CompanyType.MANUFACTURER, name="Second Supplier")
    listed_location(session, second.company)
    other = f.make_product(session, second.company, status=ProductStatus.PUBLISHED)
    lines = [
        {"product_id": str(seller.oil.product_id), "quantity": "1", "unit": "carton"},
        {"product_id": str(other.product_id), "quantity": "1", "unit": "carton"},
    ]

    assert buyer.client.post(buyer.orders, json=order_body(seller, lines=lines)).status_code == 422


def test_duplicate_product_lines_rejected(buyer: Party, seller: Seller) -> None:
    line = {"product_id": str(seller.oil.product_id), "quantity": "1", "unit": "carton"}

    response = buyer.client.post(buyer.orders, json=order_body(seller, lines=[line, line]))

    assert response.status_code == 422


def test_company_cannot_order_from_itself(party, session: Session) -> None:
    both = party(company_type=CompanyType.BOTH)
    location = listed_location(session, both.company)
    product = f.make_product(session, both.company, status=ProductStatus.PUBLISHED)
    body = {
        "lines": [{"product_id": str(product.product_id), "quantity": "1", "unit": "bag"}],
        "fulfilment_method": "PICKUP",
        "pickup_location_id": str(location.location_id),
    }

    response = both.client.post(both.orders, json=body)

    assert response.status_code == 422
    assert "itself" in response.json()["detail"]


def test_manufacturer_only_company_cannot_order(party, seller: Seller) -> None:
    manufacturer = party(company_type=CompanyType.MANUFACTURER)

    response = manufacturer.client.post(manufacturer.orders, json=order_body(seller))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "status", [CompanyReviewStatus.PENDING_REVIEW, CompanyReviewStatus.SUSPENDED]
)
def test_unapproved_buyer_cannot_order(party, seller: Seller, status) -> None:
    buyer = party(status=status)

    assert buyer.client.post(buyer.orders, json=order_body(seller)).status_code == 403


@pytest.mark.parametrize(
    "status", [CompanyReviewStatus.PENDING_REVIEW, CompanyReviewStatus.SUSPENDED]
)
def test_unapproved_seller_cannot_receive_orders(
    buyer: Party, seller: Seller, session: Session, status
) -> None:
    seller.company.review_status = status
    session.add(seller.company)
    session.flush()

    assert buyer.client.post(buyer.orders, json=order_body(seller)).status_code == 422


def test_pickup_needs_a_reviewed_location_of_the_seller(
    buyer: Party, seller: Seller, session: Session
) -> None:
    pending = listed_location(session, seller.company, review_status=ReviewStatus.PENDING_REVIEW)
    elsewhere = listed_location(session, buyer.company)

    for location_id in (None, pending.location_id, elsewhere.location_id, uuid.uuid4()):
        body = order_body(seller, pickup_location_id=str(location_id) if location_id else None)
        assert buyer.client.post(buyer.orders, json=body).status_code == 422


def test_delivery_needs_details(buyer: Party, seller: Seller) -> None:
    body = order_body(seller, fulfilment_method="DELIVERY", pickup_location_id=None)

    assert buyer.client.post(buyer.orders, json=body).status_code == 422


def test_no_payment_fields_in_order_api(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    order_schemas = {
        name: schema
        for name, schema in schemas.items()
        if name.startswith(("Order", "Line", "Fulfil", "Decline", "Reply", "Supplier"))
    }
    assert "OrderCreateRequest" in order_schemas
    words = re.compile(r"payment|price|amount|currency|total|card|checkout", re.IGNORECASE)
    for name, schema in order_schemas.items():
        for field in schema.get("properties", {}):
            assert not words.search(field), f"{name}.{field}"


# --- Visibility ---------------------------------------------------------------------------------


def test_only_buyer_and_seller_see_an_order(buyer: Party, seller: Seller, party) -> None:
    order = place(buyer, seller)
    outsider = party(name="Outsider Traders")

    assert buyer.client.get(f"{buyer.orders}/{order['order_id']}").status_code == 200
    assert seller.client.get(f"{seller.orders}/{order['order_id']}").status_code == 200
    # Member of a third company, using their own company path: not found, nothing leaked.
    assert outsider.client.get(f"{outsider.orders}/{order['order_id']}").status_code == 404
    assert outsider.client.get(outsider.orders).json() == []
    # Using the buyer's company path without being a member: forbidden.
    assert outsider.client.get(f"{buyer.orders}/{order['order_id']}").status_code == 403
    assert outsider.client.post(f"{buyer.orders}/{order['order_id']}/cancel").status_code == 403


def test_signed_out_user_gets_401(buyer: Party, seller: Seller, client: TestClient) -> None:
    order = place(buyer, seller)

    assert client.get(f"{buyer.orders}/{order['order_id']}").status_code == 401


def test_lists_split_buying_and_selling(buyer: Party, seller: Seller) -> None:
    order = place(buyer, seller)

    assert [o["order_id"] for o in buyer.client.get(f"{buyer.orders}?role=buying").json()] == [
        order["order_id"]
    ]
    assert buyer.client.get(f"{buyer.orders}?role=selling").json() == []
    assert [o["order_id"] for o in seller.client.get(f"{seller.orders}?role=selling").json()] == [
        order["order_id"]
    ]


# --- Seller responses and status flow -----------------------------------------------------------


def test_only_the_addressed_seller_can_respond(
    buyer: Party, seller: Seller, party, session: Session
) -> None:
    order = place(buyer, seller)
    other_seller = party(company_type=CompanyType.MANUFACTURER, name="Other Supplier")
    listed_location(session, other_seller.company)

    for action, body in (("accept", {}), ("decline", {}), ("reply", {"message": "Hi"})):
        url = f"{order['order_id']}/{action}"
        assert buyer.client.post(f"{buyer.orders}/{url}", json=body).status_code == 403
        assert (
            other_seller.client.post(f"{other_seller.orders}/{url}", json=body).status_code == 404
        )
    assert seller_action(seller, order, "accept").json()["status"] == "ACCEPTED"


def test_seller_accepts_replies_and_fulfils_with_batches(
    buyer: Party, seller: Seller, session: Session
) -> None:
    order = place(
        buyer,
        seller,
        lines=[
            {"product_id": str(seller.oil.product_id), "quantity": "10", "unit": "carton"},
            {"product_id": str(seller.rice.product_id), "quantity": "2.5", "unit": "tonne"},
        ],
    )
    oil_a = f.make_batch(
        session, seller.oil, batch_number="LOT-A", review_status=ReviewStatus.APPROVED
    )
    oil_b = f.make_batch(
        session, seller.oil, batch_number="LOT-B", review_status=ReviewStatus.APPROVED
    )
    oil_line = next(line for line in order["lines"] if line["product_name"] == "Sample Palm Oil")

    assert seller_action(seller, order, "reply", message="Ready on Friday").status_code == 200
    assert seller_action(seller, order, "accept").status_code == 200
    fulfilled = seller_action(
        seller,
        order,
        "fulfil",
        allocations=[
            {
                "line_id": oil_line["line_id"],
                "batch_ids": [str(oil_a.batch_id), str(oil_b.batch_id)],
            }
        ],
    ).json()

    assert fulfilled["status"] == "FULFILLED"
    assert fulfilled["seller_note"] == "Ready on Friday"
    by_name = {line["product_name"]: line for line in fulfilled["lines"]}
    assert {b["batch_number"] for b in by_name["Sample Palm Oil"]["batches"]} == {"LOT-A", "LOT-B"}
    assert by_name["Sample Rice"]["batches"] == []
    # The buyer sees the same.
    seen = buyer.client.get(f"{buyer.orders}/{order['order_id']}").json()
    assert seen["status"] == "FULFILLED"
    actions = {row.action for row in session.exec(select(AuditLog)).all()}
    assert {"order_requested", "order_replied", "order_accepted", "order_fulfilled"} <= actions


def test_fulfil_without_batches_is_allowed(buyer: Party, seller: Seller) -> None:
    order = place(buyer, seller)
    seller_action(seller, order, "accept")

    assert seller_action(seller, order, "fulfil").json()["status"] == "FULFILLED"


def test_decline_with_reason(buyer: Party, seller: Seller) -> None:
    order = place(buyer, seller)

    declined = seller_action(seller, order, "decline", reason="Out of season").json()

    assert declined["status"] == "DECLINED"
    assert declined["seller_note"] == "Out of season"


@pytest.mark.parametrize(
    ("steps", "action"),
    [
        ([], "fulfil"),  # requested -> fulfilled
        (["accept"], "accept"),  # accepted -> accepted
        (["accept"], "decline"),  # accepted -> declined
        (["decline"], "accept"),  # declined -> accepted
        (["decline"], "fulfil"),
        (["accept", "fulfil"], "accept"),
        (["accept", "fulfil"], "decline"),
        (["accept", "fulfil"], "fulfil"),
        (["decline"], "reply"),
        (["accept", "fulfil"], "reply"),
    ],
)
def test_invalid_transitions_rejected(
    buyer: Party, seller: Seller, steps: list[str], action: str
) -> None:
    order = place(buyer, seller)
    for step in steps:
        assert seller_action(seller, order, step).status_code == 200

    body = {"message": "Hello"} if action == "reply" else {}
    response = seller.client.post(f"{seller.orders}/{order['order_id']}/{action}", json=body)

    assert response.status_code == 409


def test_buyer_cancels_only_while_requested(buyer: Party, seller: Seller) -> None:
    first = place(buyer, seller)
    second = place(buyer, seller)
    seller_action(seller, second, "accept")

    cancelled = buyer.client.post(f"{buyer.orders}/{first['order_id']}/cancel")
    too_late = buyer.client.post(f"{buyer.orders}/{second['order_id']}/cancel")
    again = buyer.client.post(f"{buyer.orders}/{first['order_id']}/cancel")

    assert cancelled.json()["status"] == "CANCELLED"
    assert too_late.status_code == 409
    assert again.status_code == 409
    assert seller_action(seller, first, "accept").status_code == 409


def test_seller_cannot_cancel(buyer: Party, seller: Seller) -> None:
    order = place(buyer, seller)

    assert seller.client.post(f"{seller.orders}/{order['order_id']}/cancel").status_code == 403


def test_suspended_seller_cannot_respond(buyer: Party, seller: Seller, session: Session) -> None:
    order = place(buyer, seller)
    seller.company.review_status = CompanyReviewStatus.SUSPENDED
    session.add(seller.company)
    session.flush()

    assert seller_action(seller, order, "accept").status_code == 403
    # The buyer can still withdraw the request.
    assert buyer.client.post(f"{buyer.orders}/{order['order_id']}/cancel").status_code == 200


# --- Batch allocation ---------------------------------------------------------------------------


def _accepted(buyer: Party, seller: Seller) -> dict:
    order = place(buyer, seller)
    seller_action(seller, order, "accept")
    return order


def test_batch_of_another_product_rejected(buyer: Party, seller: Seller, session: Session) -> None:
    order = _accepted(buyer, seller)
    rice_batch = f.make_batch(session, seller.rice, review_status=ReviewStatus.APPROVED)
    allocations = [
        {"line_id": order["lines"][0]["line_id"], "batch_ids": [str(rice_batch.batch_id)]}
    ]

    response = seller_action(seller, order, "fulfil", allocations=allocations)

    assert response.status_code == 422
    assert seller.client.get(f"{seller.orders}/{order['order_id']}").json()["status"] == "ACCEPTED"


def test_batch_of_another_company_rejected(
    buyer: Party, seller: Seller, party, session: Session
) -> None:
    order = _accepted(buyer, seller)
    other = party(company_type=CompanyType.MANUFACTURER, name="Other Supplier")
    foreign = f.make_batch(
        session, f.make_product(session, other.company), review_status=ReviewStatus.APPROVED
    )
    allocations = [{"line_id": order["lines"][0]["line_id"], "batch_ids": [str(foreign.batch_id)]}]

    assert seller_action(seller, order, "fulfil", allocations=allocations).status_code == 422


def test_unknown_line_or_batch_rejected(buyer: Party, seller: Seller, session: Session) -> None:
    order = _accepted(buyer, seller)
    batch = f.make_batch(session, seller.oil, review_status=ReviewStatus.APPROVED)

    bad_line = [{"line_id": str(uuid.uuid4()), "batch_ids": [str(batch.batch_id)]}]
    bad_batch = [{"line_id": order["lines"][0]["line_id"], "batch_ids": [str(uuid.uuid4())]}]

    assert seller_action(seller, order, "fulfil", allocations=bad_line).status_code == 422
    assert seller_action(seller, order, "fulfil", allocations=bad_batch).status_code == 422


# --- Supplier page ------------------------------------------------------------------------------


def test_supplier_page_shows_registration_results(
    seller: Seller, client: TestClient, session: Session
) -> None:
    agency = f.make_agency(session)
    names = {
        "registered_product_name": "Sample Palm Oil",
        "registered_company_name": seller.company.claimed_legal_name,
    }
    active = f.make_register(session, agency, **names)
    copied = f.make_register(session, agency, registered_product_name="Sample Chin Chin")
    expired = f.make_register(session, agency, expires_on=date.today() - timedelta(days=1))
    inactive = f.make_register(session, agency, status=RegisterStatus.INACTIVE)
    seller.oil.registration_number = active.registration_number
    seller.rice.registration_number = expired.registration_number
    f.make_product(
        session,
        seller.company,
        name="Sample Beans",
        status=ProductStatus.PUBLISHED,
        registration_number=inactive.registration_number,
    )
    f.make_product(
        session,
        seller.company,
        name="Sample Honey",
        status=ProductStatus.PUBLISHED,
        registration_number="DEMO-NAFDAC-UNKNOWN",
    )
    f.make_product(session, seller.company, name="Sample Yam Flour", status=ProductStatus.PUBLISHED)
    f.make_product(
        session,
        seller.company,
        name="Sample Cocoa",
        status=ProductStatus.PUBLISHED,
        registration_number=copied.registration_number,
    )
    f.make_product(session, seller.company, name="Draft Product", status=ProductStatus.DRAFT)
    session.add_all([seller.oil, seller.rice])
    session.flush()

    page = client.get(f"/api/suppliers/{seller.company.company_id}").json()

    results = {p["name"]: p["registration_result"] for p in page["products"]}
    assert results == {
        "Sample Palm Oil": "ACTIVE_IN_DEMO_REGISTER",
        "Sample Rice": "EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER",
        "Sample Beans": "EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER",
        "Sample Honey": "NOT_FOUND_IN_DEMO_REGISTER",
        "Sample Yam Flour": "NO_NUMBER_GIVEN",
        "Sample Cocoa": "REGISTERED_TO_ANOTHER_PRODUCT",
    }
    assert page["data_mode"] == "DEMO"
    assert page["disclaimer"].startswith("DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE")
    assert page["locations"][0]["location_id"] == str(seller.location.location_id)
    assert (
        "(demo data)"
        in next(p for p in page["products"] if p["name"] == "Sample Palm Oil")["registration_label"]
    )
    text = str(page).lower()
    for word in ("safe", "unsafe", "genuine", "verified"):
        assert not re.search(rf"\b{word}\b", text), word


def test_supplier_page_hidden_for_unlisted_companies(
    party, client: TestClient, session: Session
) -> None:
    no_location = party(company_type=CompanyType.MANUFACTURER)
    pending = party(
        company_type=CompanyType.MANUFACTURER, status=CompanyReviewStatus.PENDING_REVIEW
    )
    listed_location(session, pending.company)

    assert client.get(f"/api/suppliers/{no_location.company.company_id}").status_code == 404
    assert client.get(f"/api/suppliers/{pending.company.company_id}").status_code == 404
    assert client.get(f"/api/suppliers/{uuid.uuid4()}").status_code == 404


def test_directory_search_matches_product_names(seller: Seller, client: TestClient) -> None:
    found = client.get("/api/suppliers", params={"q": "palm oil"}).json()
    missing = client.get("/api/suppliers", params={"q": "chocolate"}).json()

    assert [s["company_id"] for s in found] == [str(seller.company.company_id)]
    assert missing == []


def test_batches_must_be_approved_to_link(buyer: Party, seller: Seller, session: Session) -> None:
    order = _accepted(buyer, seller)
    pending = f.make_batch(session, seller.oil, review_status=ReviewStatus.PENDING_REVIEW)
    allocations = [{"line_id": order["lines"][0]["line_id"], "batch_ids": [str(pending.batch_id)]}]

    assert seller_action(seller, order, "fulfil", allocations=allocations).status_code == 422


def test_order_status_values_match_the_flow() -> None:
    assert [s.value for s in OrderStatus] == [
        "REQUESTED",
        "ACCEPTED",
        "DECLINED",
        "FULFILLED",
        "CANCELLED",
    ]
