"""Company registration, admin review, supplier locations, and the public directory."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import AppUser, AuditLog, Company, CompanyMember, SupplierLocation
from app.models.enums import CompanyReviewStatus, MemberRole, MembershipStatus, ReviewStatus
from app.schemas.company import SUPPLIER_BADGE
from tests import factories as f

PASSWORD = "correct-horse-battery"

COMPANY_BODY = {
    "company_type": "MANUFACTURER",
    "display_name": "Test Foods (fictional)",
    "contact_email": "hello@testfoods.example.com",
    "contact_phone": "+234 000 000 0000",
    "claimed_legal_name": "Test Foods Ltd (fictional)",
    "claimed_business_identifier": "DEMO-RC-9999",
    "claimed_address": "1 Demo Way",
}
LOCATION_BODY = {"name": "Main depot", "address": "2 Demo Way", "area": "Ikeja, Lagos"}


def sign_in(client: TestClient, session: Session, **user_overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **user_overrides)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user


def owned_company(
    session: Session, user: AppUser, status=CompanyReviewStatus.APPROVED, **overrides
) -> Company:
    company = f.make_company(session, review_status=status, **overrides)
    f.make_member(session, user, company, role=MemberRole.OWNER)
    return company


def make_location(session: Session, company: Company, status=ReviewStatus.APPROVED, **kw):
    location = SupplierLocation(
        company_id=company.company_id,
        name=kw.get("name", "Depot (fictional)"),
        address="1 Example Street",
        area=kw.get("area", "Ikeja"),
        review_status=status,
    )
    session.add(location)
    session.flush()
    return location


@pytest.fixture
def two_clients(make_client: Callable[..., TestClient]) -> tuple[TestClient, TestClient]:
    """Separate cookie jars for a company user and an admin."""
    return make_client(client_ip="203.0.113.1"), make_client(client_ip="203.0.113.2")


# --- Registration -----------------------------------------------------------------------------


def test_registration_creates_pending_company_and_owner(
    client: TestClient, session: Session
) -> None:
    user = sign_in(client, session)

    response = client.post("/api/companies", json=COMPANY_BODY)

    assert response.status_code == 201
    body = response.json()
    assert body["review_status"] == "PENDING_REVIEW"
    assert body["reviewed_at"] is None
    member = session.exec(select(CompanyMember).where(CompanyMember.user_id == user.user_id)).one()
    assert member.role == MemberRole.OWNER
    assert str(member.company_id) == body["company_id"]
    me = client.get("/api/auth/me").json()
    assert me["membership"]["role"] == "OWNER"
    assert me["membership"]["company_review_status"] == "PENDING_REVIEW"


def test_registration_ignores_review_and_ownership_fields(
    client: TestClient, session: Session
) -> None:
    user = sign_in(client, session)
    reviewer = f.make_user(session, is_admin=True)

    response = client.post(
        "/api/companies",
        json=COMPANY_BODY
        | {
            "review_status": "APPROVED",
            "reviewed_by_user_id": str(reviewer.user_id),
            "reviewed_at": "2026-01-01T00:00:00Z",
            "review_note": "self-approved",
            "company_id": "00000000-0000-0000-0000-000000000001",
            "role": "OWNER",
        },
    )

    company = session.get(Company, response.json()["company_id"])
    assert company.review_status == CompanyReviewStatus.PENDING_REVIEW
    assert company.reviewed_by_user_id is None
    assert company.reviewed_at is None
    assert company.review_note is None
    assert str(company.company_id) != "00000000-0000-0000-0000-000000000001"
    assert user


def test_registration_requires_sign_in(client: TestClient) -> None:
    assert client.post("/api/companies", json=COMPANY_BODY).status_code == 401


def test_user_cannot_register_a_second_company(client: TestClient, session: Session) -> None:
    sign_in(client, session)
    client.post("/api/companies", json=COMPANY_BODY)

    response = client.post("/api/companies", json=COMPANY_BODY | {"display_name": "Second"})

    assert response.status_code == 409


def test_admin_cannot_register_a_company(client: TestClient, session: Session) -> None:
    sign_in(client, session, is_admin=True)

    assert client.post("/api/companies", json=COMPANY_BODY).status_code == 403


# --- Admin review of companies --------------------------------------------------------------


def test_company_cannot_approve_itself(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user, CompanyReviewStatus.PENDING_REVIEW)

    response = client.post(
        f"/api/admin/companies/{company.company_id}/decision", json={"decision": "APPROVE"}
    )

    assert response.status_code == 403
    session.refresh(company)
    assert company.review_status == CompanyReviewStatus.PENDING_REVIEW


def test_admin_who_belongs_to_a_company_cannot_review_it(
    client: TestClient, session: Session
) -> None:
    admin = sign_in(client, session, is_admin=True)
    company = owned_company(session, admin, CompanyReviewStatus.PENDING_REVIEW)

    response = client.post(
        f"/api/admin/companies/{company.company_id}/decision", json={"decision": "APPROVE"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admins cannot review a company they belong to"


def test_non_admin_cannot_list_pending_companies(client: TestClient, session: Session) -> None:
    sign_in(client, session)

    assert client.get("/api/admin/companies").status_code == 403


def test_admin_lists_pending_companies_with_owner(client: TestClient, session: Session) -> None:
    owner = f.make_user(session, display_name="Owner Demo")
    pending = owned_company(session, owner, CompanyReviewStatus.PENDING_REVIEW)
    f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    sign_in(client, session, is_admin=True)

    response = client.get("/api/admin/companies", params={"review_status": "PENDING_REVIEW"})

    assert response.status_code == 200
    body = response.json()
    assert [c["company_id"] for c in body] == [str(pending.company_id)]
    assert body[0]["owner_display_name"] == "Owner Demo"


@pytest.mark.parametrize(
    ("start", "decision", "end"),
    [
        (CompanyReviewStatus.PENDING_REVIEW, "APPROVE", CompanyReviewStatus.APPROVED),
        (CompanyReviewStatus.PENDING_REVIEW, "REJECT", CompanyReviewStatus.REJECTED),
        (CompanyReviewStatus.APPROVED, "SUSPEND", CompanyReviewStatus.SUSPENDED),
        (CompanyReviewStatus.SUSPENDED, "APPROVE", CompanyReviewStatus.APPROVED),
    ],
)
def test_admin_decision_records_reviewer_time_note_and_audit(
    client: TestClient, session: Session, start, decision, end
) -> None:
    company = f.make_company(session, review_status=start)
    admin = sign_in(client, session, is_admin=True)

    response = client.post(
        f"/api/admin/companies/{company.company_id}/decision",
        json={"decision": decision, "note": "Checked demo profile"},
    )

    assert response.status_code == 200
    session.refresh(company)
    assert company.review_status == end
    assert company.reviewed_by_user_id == admin.user_id
    assert company.reviewed_at is not None
    assert company.review_note == "Checked demo profile"
    assert response.json()["reviewed_by_display_name"] == admin.display_name
    entry = session.exec(select(AuditLog).where(AuditLog.entity_id == company.company_id)).one()
    assert entry.actor_user_id == admin.user_id
    assert entry.old_values == {"review_status": start}


@pytest.mark.parametrize(
    ("start", "decision"),
    [
        (CompanyReviewStatus.APPROVED, "APPROVE"),
        (CompanyReviewStatus.PENDING_REVIEW, "SUSPEND"),
        (CompanyReviewStatus.REJECTED, "APPROVE"),
        (CompanyReviewStatus.SUSPENDED, "REJECT"),
    ],
)
def test_invalid_company_transitions_are_refused(
    client: TestClient, session: Session, start, decision
) -> None:
    company = f.make_company(session, review_status=start)
    sign_in(client, session, is_admin=True)

    response = client.post(
        f"/api/admin/companies/{company.company_id}/decision", json={"decision": decision}
    )

    assert response.status_code == 409
    session.refresh(company)
    assert company.review_status == start


# --- Supplier locations ---------------------------------------------------------------------


def test_approved_company_adds_location_as_pending(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user)

    response = client.post(
        f"/api/companies/{company.company_id}/locations",
        json=LOCATION_BODY | {"review_status": "APPROVED", "company_id": "x"},
    )

    assert response.status_code == 201
    assert response.json()["review_status"] == "PENDING_REVIEW"
    assert response.json()["reviewed_at"] is None


def test_pending_company_cannot_add_location(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user, CompanyReviewStatus.PENDING_REVIEW)

    response = client.post(f"/api/companies/{company.company_id}/locations", json=LOCATION_BODY)

    assert response.status_code == 409


def test_member_cannot_add_location_to_another_company(
    client: TestClient, session: Session
) -> None:
    user = sign_in(client, session)
    owned_company(session, user)
    other = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)

    response = client.post(f"/api/companies/{other.company_id}/locations", json=LOCATION_BODY)

    assert response.status_code == 403


def test_location_contact_must_belong_to_same_company(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user)
    outsider = f.make_member(session, f.make_user(session), f.make_company(session))

    response = client.post(
        f"/api/companies/{company.company_id}/locations",
        json=LOCATION_BODY | {"contact_member_id": str(outsider.member_id)},
    )

    assert response.status_code == 422


def test_company_cannot_mark_own_location_reviewed(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user)
    location = make_location(session, company, ReviewStatus.PENDING_REVIEW)

    response = client.post(
        f"/api/admin/locations/{location.location_id}/decision", json={"decision": "APPROVE"}
    )

    assert response.status_code == 403
    session.refresh(location)
    assert location.review_status == ReviewStatus.PENDING_REVIEW


def test_admin_marks_location_demo_reviewed(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    location = make_location(session, company, ReviewStatus.PENDING_REVIEW)
    admin = sign_in(client, session, is_admin=True)

    listed = client.get("/api/admin/locations", params={"review_status": "PENDING_REVIEW"})
    response = client.post(
        f"/api/admin/locations/{location.location_id}/decision",
        json={"decision": "APPROVE", "note": "Address checked"},
    )

    assert [loc["location_id"] for loc in listed.json()] == [str(location.location_id)]
    assert response.status_code == 200
    session.refresh(location)
    assert location.review_status == ReviewStatus.APPROVED
    assert location.reviewed_by_user_id == admin.user_id
    assert location.reviewed_at is not None


def test_location_of_unapproved_company_cannot_be_approved(
    client: TestClient, session: Session
) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.SUSPENDED)
    location = make_location(session, company, ReviewStatus.PENDING_REVIEW)
    sign_in(client, session, is_admin=True)

    response = client.post(
        f"/api/admin/locations/{location.location_id}/decision", json={"decision": "APPROVE"}
    )

    assert response.status_code == 409


def test_member_sees_own_company_with_locations(client: TestClient, session: Session) -> None:
    user = sign_in(client, session)
    company = owned_company(session, user)
    make_location(session, company, ReviewStatus.PENDING_REVIEW)

    response = client.get(f"/api/companies/{company.company_id}")

    assert response.status_code == 200
    assert [loc["review_status"] for loc in response.json()["locations"]] == ["PENDING_REVIEW"]


# --- Public supplier directory --------------------------------------------------------------


def directory(client: TestClient) -> list[dict]:
    response = client.get("/api/suppliers")
    assert response.status_code == 200
    return response.json()


def test_directory_is_public_and_shows_badge(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    make_location(session, company)

    suppliers = directory(client)

    assert [s["company_id"] for s in suppliers] == [str(company.company_id)]
    assert suppliers[0]["badge"] == SUPPLIER_BADGE == "FoodLens demo-reviewed profile"
    assert "not a NAFDAC or SON approval" in suppliers[0]["badge_note"]


@pytest.mark.parametrize(
    "status",
    [
        CompanyReviewStatus.PENDING_REVIEW,
        CompanyReviewStatus.REJECTED,
        CompanyReviewStatus.SUSPENDED,
    ],
)
def test_unapproved_companies_are_hidden_from_directory(
    client: TestClient, session: Session, status
) -> None:
    company = f.make_company(session, review_status=status)
    make_location(session, company)  # even with an approved location

    assert directory(client) == []


def test_company_without_reviewed_location_is_hidden(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    make_location(session, company, ReviewStatus.PENDING_REVIEW)
    make_location(session, company, ReviewStatus.REJECTED, name="Rejected depot")

    assert directory(client) == []


def test_directory_lists_only_reviewed_locations(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    make_location(session, company, name="Reviewed depot")
    make_location(session, company, ReviewStatus.PENDING_REVIEW, name="Pending depot")

    [supplier] = directory(client)

    assert [loc["name"] for loc in supplier["locations"]] == ["Reviewed depot"]


def test_directory_hides_claimed_fields_notes_and_login_emails(
    client: TestClient, session: Session
) -> None:
    company = f.make_company(
        session,
        review_status=CompanyReviewStatus.APPROVED,
        claimed_business_identifier="DEMO-RC-SECRET",
        review_note="internal note",
    )
    make_location(session, company)
    public = f.make_user(session, email="public-login@example.test", display_name="Ada Rep")
    hidden = f.make_user(session, email="hidden-login@example.test", display_name="Hidden Rep")
    f.make_member(
        session,
        public,
        company,
        role=MemberRole.REPRESENTATIVE,
        is_public_contact=True,
        public_title="Sales lead",
        public_email="sales@company.example",
    )
    f.make_member(session, hidden, company, role=MemberRole.REPRESENTATIVE)

    text = client.get("/api/suppliers").text
    [supplier] = directory(client)

    assert "DEMO-RC-SECRET" not in text
    assert "internal note" not in text
    assert "claimed" not in text
    assert "login@example.test" not in text
    assert supplier["contacts"] == [
        {"display_name": "Ada Rep", "title": "Sales lead", "phone": None,
         "email": "sales@company.example"}
    ]  # fmt: skip


def test_inactive_public_contact_is_hidden(client: TestClient, session: Session) -> None:
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    make_location(session, company)
    f.make_member(
        session,
        f.make_user(session),
        company,
        is_public_contact=True,
        membership_status=MembershipStatus.INACTIVE,
    )

    assert directory(client)[0]["contacts"] == []


def test_directory_search_matches_name_or_area(client: TestClient, session: Session) -> None:
    lagos = f.make_company(
        session, review_status=CompanyReviewStatus.APPROVED, display_name="Lagos Oils"
    )
    make_location(session, lagos, area="Ikeja, Lagos")
    kano = f.make_company(
        session, review_status=CompanyReviewStatus.APPROVED, display_name="Northern Grains"
    )
    make_location(session, kano, area="Kano")

    names = [s["display_name"] for s in client.get("/api/suppliers?q=kano").json()]

    assert names == ["Northern Grains"]


def test_full_flow_register_review_and_list(
    two_clients: tuple[TestClient, TestClient], session: Session
) -> None:
    company_client, admin_client = two_clients
    sign_in(company_client, session)
    sign_in(admin_client, session, is_admin=True)

    company_id = company_client.post("/api/companies", json=COMPANY_BODY).json()["company_id"]
    assert directory(company_client) == []

    admin_client.post(f"/api/admin/companies/{company_id}/decision", json={"decision": "APPROVE"})
    location = company_client.post(
        f"/api/companies/{company_id}/locations", json=LOCATION_BODY
    ).json()
    assert directory(company_client) == []

    admin_client.post(
        f"/api/admin/locations/{location['location_id']}/decision", json={"decision": "APPROVE"}
    )
    [supplier] = directory(company_client)
    assert supplier["display_name"] == "Test Foods (fictional)"
    assert supplier["badge"] == "FoodLens demo-reviewed profile"
