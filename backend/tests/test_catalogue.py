"""Company catalogue: products and batches go live at once; credentials are claims until an
admin approves them (docs/DECISIONS.md D61-D64)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import AppUser, AuditLog, Company, CredentialRecord, Product, RegulatoryAgency
from app.models.enums import CompanyReviewStatus, CompanyType, MemberRole, ReviewStatus
from tests import factories as f

PASSWORD = "correct-horse-battery"
PRODUCT = {
    "product_code": "demo-pc-5001",
    "name": "Sample Cocoa Drink",
    "brand": "Test Foods",
    "category": "Beverages",
    "package_size": "500 g",
    "manufacturer_name": "Test Foods Ltd (fictional)",
}


def sign_in(client: TestClient, session: Session, **overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **overrides)
    assert (
        client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).status_code
        == 200
    )
    return user


def my_company(
    client: TestClient, session: Session, status=CompanyReviewStatus.APPROVED
) -> Company:
    user = sign_in(client, session)
    company = f.make_company(session, review_status=status)
    f.make_member(session, user, company, role=MemberRole.OWNER)
    return company


def agency(session: Session) -> RegulatoryAgency:
    return f.make_agency(session, name="NAFDAC (simulated)")


def add_product(client: TestClient, company: Company, **overrides):
    return client.post(f"/api/companies/{company.company_id}/products", json=PRODUCT | overrides)


def add_batch(client: TestClient, company: Company, product_id: str, **overrides):
    body = {"batch_number": "lot-1", "expiry_date": "2099-12-31"} | overrides
    return client.post(
        f"/api/companies/{company.company_id}/products/{product_id}/batches", json=body
    )


def add_credential(client: TestClient, company: Company, product_id: str, agency_id, **kw):
    body = {"agency_id": str(agency_id), "reference_number": "demo-nafdac-5001"} | kw
    return client.post(
        f"/api/companies/{company.company_id}/products/{product_id}/credentials", json=body
    )


def lookup(client: TestClient, code: str, batch: str) -> dict:
    return client.post(
        "/api/lookups/batch", json={"product_code": code, "batch_number": batch}
    ).json()


@pytest.fixture
def admin_client(make_client: Callable[..., TestClient], session: Session) -> TestClient:
    client = make_client(client_ip="203.0.113.99")
    sign_in(client, session, is_admin=True)
    return client


# --- Products and batches go live immediately ----------------------------------------------


def test_product_and_batch_go_live_immediately(client: TestClient, session: Session) -> None:
    company = my_company(client, session)

    product = add_product(client, company)
    batch = add_batch(client, company, product.json()["product_id"])

    assert product.status_code == 201
    assert product.json()["status"] == "PUBLISHED"
    assert product.json()["product_code"] == "DEMO-PC-5001"  # stored normalised
    assert batch.status_code == 201
    assert batch.json()["batch_number"] == "LOT-1"
    result = lookup(client, "demo-pc-5001", "lot-1")
    # Live in lookups, but no approved credential yet, so never "record found".
    assert result["result"] == "DETAILS_MISMATCH"
    assert result["mismatch"] == {"field": "credential"}


def test_client_cannot_set_status_or_owner_on_product(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    other = f.make_company(session)

    response = add_product(
        client,
        company,
        status="DRAFT",
        company_id=str(other.company_id),
        reviewed_by_user_id=str(company.company_id),
    )

    product = session.get(Product, response.json()["product_id"])
    assert product.company_id == company.company_id
    assert product.reviewed_by_user_id is None


def test_pending_company_cannot_add_products(client: TestClient, session: Session) -> None:
    company = my_company(client, session, CompanyReviewStatus.PENDING_REVIEW)

    assert add_product(client, company).status_code == 409


def test_member_cannot_add_to_another_company(client: TestClient, session: Session) -> None:
    my_company(client, session)
    other = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)

    assert add_product(client, other).status_code == 403


def test_cannot_add_batch_to_another_companys_product(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    other_product = f.make_product(session, f.make_company(session))

    response = add_batch(client, company, str(other_product.product_id))

    assert response.status_code == 404


def test_duplicate_product_code_is_refused_case_insensitively(
    client: TestClient, session: Session
) -> None:
    company = my_company(client, session)
    add_product(client, company)

    assert add_product(client, company, product_code="DEMO-PC-5001").status_code == 409


def test_duplicate_batch_number_is_refused(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)

    assert add_batch(client, company, product_id, batch_number="LOT-1").status_code == 409


def test_batch_expiry_before_production_is_rejected(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]

    response = add_batch(
        client, company, product_id, production_date="2026-05-01", expiry_date="2026-01-01"
    )

    assert response.status_code == 422


def test_publishing_is_audited(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)

    actions = session.exec(select(AuditLog.entity_type, AuditLog.action)).all()
    assert ("product", "published") in actions
    assert ("product_batch", "published") in actions


# --- Credentials are claims until an admin approves them ------------------------------------


def test_credential_starts_as_claim_and_is_hidden_from_lookup(
    client: TestClient, session: Session
) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)
    nafdac = agency(session)

    response = add_credential(
        client, company, product_id, nafdac.agency_id, status="ACTIVE", review_status="APPROVED"
    )

    assert response.status_code == 201
    credential = session.exec(select(CredentialRecord)).one()
    assert credential.review_status == ReviewStatus.PENDING_REVIEW
    assert credential.status == "INACTIVE"  # member cannot set it to ACTIVE
    assert credential.data_mode == "DEMO"
    assert "claim" in credential.provenance
    result = lookup(client, "DEMO-PC-5001", "LOT-1")
    assert result["result"] == "DETAILS_MISMATCH"
    assert result["credentials"] == []


def test_admin_approval_makes_credential_visible(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)
    add_credential(client, company, product_id, agency(session).agency_id)
    credential = session.exec(select(CredentialRecord)).one()

    queue = admin_client.get("/api/admin/credentials", params={"review_status": "PENDING_REVIEW"})
    decision = admin_client.post(
        f"/api/admin/credentials/{credential.credential_id}/decision",
        json={"decision": "APPROVE", "note": "Reference format checked"},
    )

    assert [c["credential_id"] for c in queue.json()] == [str(credential.credential_id)]
    assert decision.status_code == 200
    assert decision.json()["review_status"] == "APPROVED"
    assert decision.json()["status"] == "ACTIVE"  # activated only by admin approval
    session.refresh(credential)
    assert credential.reviewed_by_user_id is not None
    assert credential.reviewed_at is not None
    assert lookup(client, "DEMO-PC-5001", "LOT-1")["result"] == "DEMO_RECORD_FOUND"


def test_rejected_credential_stays_out_of_lookup(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)
    add_credential(client, company, product_id, agency(session).agency_id)
    credential = session.exec(select(CredentialRecord)).one()

    admin_client.post(
        f"/api/admin/credentials/{credential.credential_id}/decision", json={"decision": "REJECT"}
    )

    assert lookup(client, "DEMO-PC-5001", "LOT-1")["result"] == "DETAILS_MISMATCH"


def test_company_cannot_approve_its_own_credential(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_credential(client, company, product_id, agency(session).agency_id)
    credential = session.exec(select(CredentialRecord)).one()

    response = client.post(
        f"/api/admin/credentials/{credential.credential_id}/decision", json={"decision": "APPROVE"}
    )

    assert response.status_code == 403
    session.refresh(credential)
    assert credential.review_status == ReviewStatus.PENDING_REVIEW


def test_credential_decision_only_once(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_credential(client, company, product_id, agency(session).agency_id)
    credential = session.exec(select(CredentialRecord)).one()
    url = f"/api/admin/credentials/{credential.credential_id}/decision"
    admin_client.post(url, json={"decision": "APPROVE"})

    assert admin_client.post(url, json={"decision": "REJECT"}).status_code == 409


def test_unknown_agency_is_rejected(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]

    response = add_credential(client, company, product_id, "00000000-0000-0000-0000-000000000000")

    assert response.status_code == 422


def test_agencies_are_listed(client: TestClient, session: Session) -> None:
    agency(session)

    names = [a["name"] for a in client.get("/api/agencies").json()]

    assert names == ["NAFDAC (simulated)"]


def test_member_sees_catalogue_with_claim_status(client: TestClient, session: Session) -> None:
    company = my_company(client, session)
    product_id = add_product(client, company).json()["product_id"]
    add_batch(client, company, product_id)
    add_credential(client, company, product_id, agency(session).agency_id)

    [product] = client.get(f"/api/companies/{company.company_id}/products").json()

    assert [b["batch_number"] for b in product["batches"]] == ["LOT-1"]
    assert [c["review_status"] for c in product["credentials"]] == ["PENDING_REVIEW"]


# --- Registration types and directory owner contact -----------------------------------------


@pytest.mark.parametrize("company_type", list(CompanyType))
def test_registration_accepts_each_company_type(
    client: TestClient, session: Session, company_type: CompanyType
) -> None:
    sign_in(client, session)

    response = client.post(
        "/api/companies",
        json={
            "company_type": company_type,
            "display_name": "Typed Co (fictional)",
            "contact_email": "typed@example.com",
            "claimed_legal_name": "Typed Co Ltd",
        },
    )

    assert response.status_code == 201
    assert response.json()["company_type"] == company_type


def test_directory_shows_owner_contact_without_login_email(
    client: TestClient, admin_client: TestClient, session: Session
) -> None:
    owner = sign_in(client, session, display_name="Ada Owner", email="ada-login@example.test")
    company_id = client.post(
        "/api/companies",
        json={
            "company_type": "BOTH",
            "display_name": "Owner Contact Co (fictional)",
            "contact_email": "sales@ownerco.example.com",
            "contact_phone": "+234 000 111 2222",
            "claimed_legal_name": "Owner Contact Co Ltd",
        },
    ).json()["company_id"]
    admin_client.post(f"/api/admin/companies/{company_id}/decision", json={"decision": "APPROVE"})
    location_id = client.post(
        f"/api/companies/{company_id}/locations",
        json={"name": "Depot", "address": "1 Way", "area": "Lagos"},
    ).json()["location_id"]
    admin_client.post(f"/api/admin/locations/{location_id}/decision", json={"decision": "APPROVE"})

    response = client.get("/api/suppliers")
    [supplier] = response.json()

    assert supplier["contacts"] == [
        {
            "display_name": "Ada Owner",
            "title": "Owner",
            "phone": "+234 000 111 2222",
            "email": "sales@ownerco.example.com",
        }
    ]
    assert "ada-login@example.test" not in response.text
    assert owner


# --- Company A cannot read-for-edit or modify company B's catalogue ---------------------------


@pytest.fixture
def company_b(make_client: Callable[..., TestClient], session: Session) -> dict:
    """Company B with a product, batch, and credential claim, created by B's own owner."""
    client_b = make_client(client_ip="203.0.113.50")
    company = my_company(client_b, session)
    product_id = add_product(client_b, company, product_code="demo-pc-b1").json()["product_id"]
    batch_id = add_batch(client_b, company, product_id).json()["batch_id"]
    add_credential(
        client_b, company, product_id, agency(session).agency_id, reference_number="demo-ref-b1"
    )
    credential = session.exec(select(CredentialRecord)).one()
    return {
        "company": company,
        "product_id": product_id,
        "batch_id": batch_id,
        "credential_id": str(credential.credential_id),
    }


def test_member_of_a_cannot_read_company_b_catalogue_or_profile(
    client: TestClient, session: Session, company_b: dict
) -> None:
    my_company(client, session)
    b = company_b["company"].company_id

    assert client.get(f"/api/companies/{b}/products").status_code == 403
    assert client.get(f"/api/companies/{b}").status_code == 403


def test_member_of_a_cannot_add_to_company_b_catalogue(
    client: TestClient, session: Session, company_b: dict
) -> None:
    my_company(client, session)
    b = company_b["company"]
    product_id = company_b["product_id"]

    assert add_product(client, b, product_code="demo-pc-x").status_code == 403
    assert add_batch(client, b, product_id, batch_number="lot-x").status_code == 403
    assert add_credential(client, b, product_id, agency(session).agency_id).status_code == 403


def test_member_of_a_cannot_reach_b_product_through_own_company(
    client: TestClient, session: Session, company_b: dict
) -> None:
    mine = my_company(client, session)
    product_id = company_b["product_id"]

    assert add_batch(client, mine, product_id, batch_number="lot-x").status_code == 404
    assert (
        add_credential(
            client, mine, product_id, agency(session).agency_id, reference_number="demo-x"
        ).status_code
        == 404
    )


def test_member_of_a_cannot_review_b_credential(
    client: TestClient, session: Session, company_b: dict
) -> None:
    my_company(client, session)

    response = client.post(
        f"/api/admin/credentials/{company_b['credential_id']}/decision",
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 403


def test_company_b_data_unchanged_after_a_attempts(
    client: TestClient, session: Session, company_b: dict
) -> None:
    my_company(client, session)
    b = company_b["company"]
    add_batch(client, b, company_b["product_id"], batch_number="lot-x")
    add_credential(client, b, company_b["product_id"], agency(session).agency_id)

    products = session.exec(select(Product).where(Product.company_id == b.company_id)).all()
    credentials = session.exec(select(CredentialRecord)).all()
    assert len(products) == 1
    assert len(credentials) == 1
    assert credentials[0].status == "INACTIVE"
