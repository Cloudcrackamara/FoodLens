"""Product announcements: live without review, labelled, never change product data, hideable."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import AppUser, Company, Product, ProductAnnouncement
from app.models.enums import (
    AnnouncementStatus,
    CompanyReviewStatus,
    MemberRole,
    ProductStatus,
    ReviewStatus,
)
from tests import factories as f

PASSWORD = "correct-horse-battery"
LABEL = "Message from the company — not reviewed by FoodLens"


def sign_in(client: TestClient, session: Session, **overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **overrides)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user


def company_with_product(
    client: TestClient, session: Session, status=CompanyReviewStatus.APPROVED
) -> tuple[Company, Product]:
    user = sign_in(client, session)
    company = f.make_company(session, review_status=status)
    f.make_member(session, user, company, role=MemberRole.OWNER)
    product = f.make_product(
        session,
        company,
        product_code="DEMO-PC-8001",
        registration_number="DEMO-NAFDAC-8001",
        status=ProductStatus.PUBLISHED,
    )
    f.make_batch(session, product, batch_number="LOT-8", review_status=ReviewStatus.APPROVED)
    f.make_register(session, f.make_agency(session), registration_number="DEMO-NAFDAC-8001")
    return company, product


def post(client: TestClient, company: Company, product: Product, **body):
    payload = {"title": "New packaging", "message": "From March 2027 the bottle is green."} | body
    return client.post(
        f"/api/companies/{company.company_id}/products/{product.product_id}/announcements",
        json=payload,
    )


def lookup(client: TestClient) -> dict:
    return client.post(
        "/api/lookups/registration",
        json={"registration_number": "DEMO-NAFDAC-8001", "batch_number": "LOT-8"},
    ).json()


@pytest.fixture
def admin_client(make_client: Callable[..., TestClient], session: Session) -> TestClient:
    client = make_client(client_ip="203.0.113.77")
    sign_in(client, session, is_admin=True)
    return client


def test_announcement_goes_live_and_shows_in_lookup_with_label(
    client: TestClient, session: Session
) -> None:
    company, product = company_with_product(client, session)

    response = post(client, company, product, status="HIDDEN")

    assert response.status_code == 201
    assert response.json()["status"] == "LIVE"  # client cannot set status
    result = lookup(client)
    assert result["result"] == "REGISTERED_ACTIVE"
    assert result["announcements"] == [
        {
            "title": "New packaging",
            "message": "From March 2027 the bottle is green.",
            "posted_at": result["announcements"][0]["posted_at"],
            "label": LABEL,
        }
    ]


def test_announcement_never_changes_product_data(client: TestClient, session: Session) -> None:
    company, product = company_with_product(client, session)
    before = product.model_dump()

    post(client, company, product, title="Name change", message="Now called Something Else")

    session.refresh(product)
    assert product.model_dump() == before
    assert lookup(client)["product"]["name"] == before["name"]


def test_only_latest_three_live_announcements_are_shown(
    client: TestClient, session: Session
) -> None:
    company, product = company_with_product(client, session)
    for n in range(4):
        post(client, company, product, title=f"Note {n}")

    titles = [a["title"] for a in lookup(client)["announcements"]]

    assert len(titles) == 3


@pytest.mark.parametrize(
    "body",
    [
        {"title": "Now SAFE to drink"},
        {"message": "This product is safe."},
        {"message": "Beware of unsafe copies"},
    ],
)
def test_safety_words_are_refused(client: TestClient, session: Session, body: dict) -> None:
    company, product = company_with_product(client, session)

    response = post(client, company, product, **body)

    assert response.status_code == 422
    assert session.exec(select(ProductAnnouncement)).all() == []


@pytest.mark.parametrize(
    "message",
    [
        "Beware of fake versions sold in open markets.",
        "Counterfeit bottles have a blue cap. Report fakes to us.",
        "New seal added for food safety and tamper evidence.",
        "Store safely away from sunlight.",
    ],
)
def test_counterfeit_warnings_and_other_words_are_allowed(
    client: TestClient, session: Session, message: str
) -> None:
    company, product = company_with_product(client, session)

    response = post(client, company, product, title="Counterfeit warning", message=message)

    assert response.status_code == 201
    assert lookup(client)["announcements"][0]["message"] == message


def test_pending_company_cannot_post(client: TestClient, session: Session) -> None:
    company, product = company_with_product(client, session, CompanyReviewStatus.PENDING_REVIEW)

    assert post(client, company, product).status_code == 409


def test_cannot_post_on_another_companys_product(client: TestClient, session: Session) -> None:
    company, _ = company_with_product(client, session)
    other_product = f.make_product(session, f.make_company(session), product_code="DEMO-PC-X")

    assert post(client, company, other_product).status_code == 404


def test_company_can_withdraw_its_own_announcement(client: TestClient, session: Session) -> None:
    company, product = company_with_product(client, session)
    announcement_id = post(client, company, product).json()["announcement_id"]

    response = client.post(
        f"/api/companies/{company.company_id}/announcements/{announcement_id}/withdraw"
    )

    assert response.json()["status"] == "HIDDEN"
    assert lookup(client)["announcements"] == []


def test_admin_hides_announcement_and_records_who(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    company, product = company_with_product(client, session)
    announcement_id = post(client, company, product).json()["announcement_id"]

    listed = admin_client.get("/api/admin/announcements", params={"status": "LIVE"}).json()
    response = admin_client.post(
        f"/api/admin/announcements/{announcement_id}/hide", json={"reason": "Misleading"}
    )

    assert [a["announcement_id"] for a in listed] == [announcement_id]
    assert response.status_code == 200
    stored = session.get(ProductAnnouncement, announcement_id)
    assert stored.status == AnnouncementStatus.HIDDEN
    assert stored.hidden_by_user_id is not None and stored.hidden_at is not None
    assert lookup(client)["announcements"] == []
    hidden = admin_client.get("/api/admin/announcements", params={"status": "HIDDEN"}).json()
    assert hidden[0]["hidden_by_display_name"] is not None


def test_company_cannot_use_admin_hide(client: TestClient, session: Session) -> None:
    company, product = company_with_product(client, session)
    announcement_id = post(client, company, product).json()["announcement_id"]

    response = client.post(f"/api/admin/announcements/{announcement_id}/hide", json={})

    assert response.status_code == 403


def test_member_cannot_withdraw_another_companys_announcement(
    client: TestClient, make_client: Callable[..., TestClient], session: Session
) -> None:
    company, product = company_with_product(client, session)
    announcement_id = post(client, company, product).json()["announcement_id"]
    outsider = make_client(client_ip="203.0.113.88")
    outsider_user = sign_in(outsider, session)
    other = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    f.make_member(session, outsider_user, other)

    response = outsider.post(
        f"/api/companies/{other.company_id}/announcements/{announcement_id}/withdraw"
    )

    assert response.status_code == 404
    assert session.get(ProductAnnouncement, announcement_id).status == AnnouncementStatus.LIVE


def test_hidden_announcement_cannot_be_hidden_again(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    company, product = company_with_product(client, session)
    announcement_id = post(client, company, product).json()["announcement_id"]
    admin_client.post(f"/api/admin/announcements/{announcement_id}/hide", json={})

    assert (
        admin_client.post(f"/api/admin/announcements/{announcement_id}/hide", json={}).status_code
        == 409
    )


def test_announcements_hidden_when_company_suspended(client: TestClient, session: Session) -> None:
    company, product = company_with_product(client, session)
    post(client, company, product)
    company.review_status = CompanyReviewStatus.SUSPENDED
    session.add(company)
    session.flush()

    result = lookup(client)

    assert result["result"] == "REGISTERED_ACTIVE"  # the register record itself is unaffected
    assert [w["code"] for w in result["warnings"]] == ["BATCH_NOT_IN_CATALOGUE"]
    assert result["announcements"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Now NAFDAC approved!",
        "nafdac-registered since 2020",
        "Proudly NAFDAC Certified",
        "SON approved packaging",
        "son-certified factory",
        "Approved by NAFDAC",
        "registered by Nafdac",
        "certified by SON",
    ],
)
def test_regulator_claims_are_refused(client: TestClient, session: Session, text: str) -> None:
    company, product = company_with_product(client, session)

    response = post(client, company, product, message=text)

    assert response.status_code == 422
    assert "NAFDAC or SON" in response.json()["detail"]
    assert session.exec(select(ProductAnnouncement)).all() == []


@pytest.mark.parametrize(
    "text",
    [
        "Check the NAFDAC number printed on the cap.",
        "Our SON MANCAP number is on the label.",
        "Registered office moved to Ikeja.",
    ],
)
def test_mentioning_regulators_without_a_claim_is_allowed(
    client: TestClient, session: Session, text: str
) -> None:
    company, product = company_with_product(client, session)

    assert post(client, company, product, message=text).status_code == 201


def test_son_claim_filter_is_case_insensitive_even_for_everyday_son(
    client: TestClient, session: Session
) -> None:
    """Known limitation (D86): matching "SON approved" in any case also catches this sentence."""
    company, product = company_with_product(client, session)

    assert (
        post(client, company, product, message="My son approved the new taste").status_code == 422
    )
