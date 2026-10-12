"""Phase 4 closing items: direct contact edits are logged (rule 5, D103); published products
cannot be edited directly, only through change notices (rule 5)."""

from collections.abc import Callable

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import hash_password
from app.main import create_app
from app.models import AuditLog, Company
from app.models.enums import CompanyReviewStatus, MemberRole
from tests import factories as f

PASSWORD = "correct-horse-battery"


def signed_in_member(client: TestClient, session: Session, company: Company, role=MemberRole.OWNER):
    user = f.make_user(session, password_hash=hash_password(PASSWORD))
    member = f.make_member(
        session,
        user,
        company,
        role=role,
        is_public_contact=True,
        public_title="Owner",
        public_email=company.contact_email,
    )
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user, member


def contact_url(company: Company) -> str:
    return f"/api/companies/{company.company_id}/contact"


def test_owner_edits_contact_and_change_is_audited(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    user, member = signed_in_member(client, session, company)
    old_email = company.contact_email

    response = client.patch(
        contact_url(company),
        json={"contact_email": "Sales@New-Demo.example", "contact_phone": "+234 800 000 0000"},
    )

    assert response.status_code == 200
    assert response.json()["contact_email"] == "sales@new-demo.example"
    assert response.json()["contact_phone"] == "+234 800 000 0000"
    entry = session.exec(select(AuditLog).where(AuditLog.action == "contact_updated")).one()
    assert entry.actor_user_id == user.user_id
    assert entry.entity_id == company.company_id
    assert entry.created_at is not None
    assert entry.old_values == {"contact_email": old_email, "contact_phone": None}
    assert entry.new_values == {
        "contact_email": "sales@new-demo.example",
        "contact_phone": "+234 800 000 0000",
    }
    # The owner's directory contact follows the company details (D65).
    session.refresh(member)
    assert member.public_email == "sales@new-demo.example"


def test_contact_edit_works_while_pending_and_needs_no_review(
    client: TestClient, session: Session
) -> None:
    company = f.make_company(session)
    signed_in_member(client, session, company)

    response = client.patch(contact_url(company), json={"contact_email": "hi@pending.example"})

    assert response.status_code == 200
    assert response.json()["review_status"] == "PENDING_REVIEW"


def test_contact_edit_ignores_status_and_ownership_fields(
    client: TestClient, session: Session
) -> None:
    company = f.make_company(session)
    signed_in_member(client, session, company)

    body = {
        "contact_email": "hi@pending.example",
        "review_status": "APPROVED",
        "reviewed_by_user_id": None,
        "company_type": "BOTH",
        "display_name": "Renamed",
        "claimed_legal_name": "Renamed Ltd",
    }
    data = client.patch(contact_url(company), json=body).json()

    assert data["review_status"] == "PENDING_REVIEW"
    assert data["company_type"] == company.company_type.value
    assert data["display_name"] == company.display_name
    assert data["claimed_legal_name"] == company.claimed_legal_name


def test_unchanged_contact_writes_no_audit_entry(client: TestClient, session: Session) -> None:
    company = f.make_company(session)
    signed_in_member(client, session, company)

    client.patch(contact_url(company), json={"contact_email": company.contact_email})

    assert session.exec(select(AuditLog).where(AuditLog.action == "contact_updated")).all() == []


def test_invalid_email_rejected(client: TestClient, session: Session) -> None:
    company = f.make_company(session)
    signed_in_member(client, session, company)

    assert (
        client.patch(contact_url(company), json={"contact_email": "not-an-email"}).status_code
        == 422
    )


def test_only_the_owner_can_edit_contact(client: TestClient, session: Session) -> None:
    company = f.make_company(session)
    signed_in_member(client, session, company, role=MemberRole.REPRESENTATIVE)

    response = client.patch(contact_url(company), json={"contact_email": "rep@demo.example"})

    assert response.status_code == 403


def test_cannot_edit_another_companys_contact(
    make_client: Callable[..., TestClient], session: Session
) -> None:
    mine, theirs = f.make_company(session), f.make_company(session)
    client = make_client()
    signed_in_member(client, session, mine)

    response = client.patch(contact_url(theirs), json={"contact_email": "x@demo.example"})

    assert response.status_code == 403
    session.refresh(theirs)
    assert theirs.contact_email != "x@demo.example"


def test_signed_out_user_cannot_edit_contact(client: TestClient, session: Session) -> None:
    company = f.make_company(session)

    assert (
        client.patch(contact_url(company), json={"contact_email": "x@demo.example"}).status_code
        == 401
    )


def test_published_products_and_batches_have_no_direct_edit_routes() -> None:
    """Rule 5: published product and batch details change only through an approved change
    notice. No PUT/PATCH/DELETE route exists for products or batches."""
    app = create_app()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if "/products" in route.path or "/batches" in route.path:
            assert not route.methods & {"PUT", "PATCH", "DELETE"}, (route.path, route.methods)


def test_direct_product_edit_is_refused(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    signed_in_member(client, session, company)
    product = f.make_product(session, company)
    url = f"/api/companies/{company.company_id}/products/{product.product_id}"

    for method in ("PUT", "PATCH", "DELETE"):
        assert client.request(method, url, json={"name": "Changed"}).status_code in (404, 405)
    session.refresh(product)
    assert product.name == "Sample Palm Oil"
