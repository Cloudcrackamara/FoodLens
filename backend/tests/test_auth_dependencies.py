"""current_user, require_admin, and require_company_member, exercised through test-only routes."""

from collections.abc import Callable
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.auth import AdminUser, CurrentUser, require_company_member
from app.core.security import hash_password
from app.models import AppUser, CompanyMember
from app.models.enums import MemberRole, MembershipStatus
from tests import factories as f

PASSWORD = "correct-horse-battery"

probe = APIRouter(prefix="/test-only")


@probe.get("/signed-in")
def signed_in(user: CurrentUser) -> dict:
    return {"user_id": str(user.user_id)}


@probe.get("/admin")
def admin_only(user: AdminUser) -> dict:
    return {"ok": True}


@probe.get("/companies/{company_id}/any-member")
def any_member(member: Annotated[CompanyMember, Depends(require_company_member())]) -> dict:
    return {"role": member.role}


@probe.get("/companies/{company_id}/owner-only")
def owner_only(
    member: Annotated[CompanyMember, Depends(require_company_member(MemberRole.OWNER))],
) -> dict:
    return {"role": member.role}


@pytest.fixture
def probe_client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(probe)


def sign_in(client: TestClient, session: Session, **user_overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **user_overrides)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user


# --- current_user / unauthenticated access --------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/test-only/signed-in",
        "/test-only/admin",
        "/test-only/companies/00000000-0000-0000-0000-000000000000/any-member",
    ],
)
def test_protected_routes_reject_unauthenticated_requests(
    probe_client: TestClient, path: str
) -> None:
    response = probe_client.get(path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not signed in"


def test_current_user_returns_signed_in_user(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)

    assert probe_client.get("/test-only/signed-in").json() == {"user_id": str(user.user_id)}


# --- require_admin ----------------------------------------------------------------------------


def test_non_admin_cannot_reach_admin_route(probe_client: TestClient, session: Session) -> None:
    sign_in(probe_client, session)

    response = probe_client.get("/test-only/admin")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_company_owner_is_not_an_admin(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)
    f.make_member(session, user, f.make_company(session), role=MemberRole.OWNER)

    assert probe_client.get("/test-only/admin").status_code == 403


def test_admin_can_reach_admin_route(probe_client: TestClient, session: Session) -> None:
    sign_in(probe_client, session, is_admin=True)

    assert probe_client.get("/test-only/admin").status_code == 200


# --- require_company_member ---------------------------------------------------------------


def test_member_can_reach_own_company(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)
    company = f.make_company(session)
    f.make_member(session, user, company, role=MemberRole.REPRESENTATIVE)

    response = probe_client.get(f"/test-only/companies/{company.company_id}/any-member")

    assert response.status_code == 200
    assert response.json() == {"role": "REPRESENTATIVE"}


def test_member_cannot_reach_another_company(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)
    f.make_member(session, user, f.make_company(session))
    other = f.make_company(session, display_name="Other Demo Co")

    response = probe_client.get(f"/test-only/companies/{other.company_id}/any-member")

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this company"


def test_role_restriction_is_enforced(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)
    company = f.make_company(session)
    f.make_member(session, user, company, role=MemberRole.REPRESENTATIVE)

    response = probe_client.get(f"/test-only/companies/{company.company_id}/owner-only")

    assert response.status_code == 403


def test_inactive_membership_has_no_access(probe_client: TestClient, session: Session) -> None:
    user = sign_in(probe_client, session)
    company = f.make_company(session)
    f.make_member(session, user, company, membership_status=MembershipStatus.INACTIVE)

    response = probe_client.get(f"/test-only/companies/{company.company_id}/any-member")

    assert response.status_code == 403


def test_admin_is_not_treated_as_company_member(probe_client: TestClient, session: Session) -> None:
    sign_in(probe_client, session, is_admin=True)
    company = f.make_company(session)

    response = probe_client.get(f"/test-only/companies/{company.company_id}/any-member")

    assert response.status_code == 403


def test_invalid_company_id_is_rejected(probe_client: TestClient, session: Session) -> None:
    sign_in(probe_client, session)

    assert probe_client.get("/test-only/companies/not-a-uuid/any-member").status_code == 422
