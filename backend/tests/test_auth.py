"""Register, login, logout, /me, sessions, and mass-assignment protection."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token
from app.models import AppUser, UserSession
from app.models.base import utc_now
from tests import factories as f

COOKIE = get_settings().session_cookie_name
PASSWORD = "correct-horse-battery"


def register(client: TestClient, **overrides):
    body = {
        "email": "ada@example.com",
        "password": PASSWORD,
        "display_name": "Ada Demo",
    } | overrides
    return client.post("/api/auth/register", json=body)


def make_login_user(session: Session, **overrides) -> AppUser:
    values = {"email": "ada@example.com", "password_hash": hash_password(PASSWORD)} | overrides
    return f.make_user(session, **values)


# --- Registration --------------------------------------------------------------------------


def test_register_creates_user_and_signs_in(client: TestClient, session: Session) -> None:
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["is_admin"] is False
    assert body["membership"] is None
    assert "password" not in response.text
    assert "password_hash" not in body
    assert client.get("/api/auth/me").json()["user_id"] == body["user_id"]


def test_register_ignores_mass_assignment_fields(client: TestClient, session: Session) -> None:
    attacker_id = "00000000-0000-0000-0000-000000000001"

    response = register(
        client,
        is_admin=True,
        is_active=False,
        user_id=attacker_id,
        password_hash="$2b$04$attacker-chosen-hash",
        review_status="APPROVED",
        status="APPROVED",
        membership={"company_id": attacker_id, "role": "OWNER"},
        created_at="2000-01-01T00:00:00Z",
    )

    assert response.status_code == 201
    user = session.exec(select(AppUser).where(AppUser.email == "ada@example.com")).one()
    assert user.is_admin is False
    assert user.is_active is True
    assert str(user.user_id) != attacker_id
    assert user.password_hash != "$2b$04$attacker-chosen-hash"
    assert user.created_at.year != 2000
    assert response.json()["membership"] is None


def test_register_stores_only_a_bcrypt_hash(client: TestClient, session: Session) -> None:
    register(client)

    user = session.exec(select(AppUser).where(AppUser.email == "ada@example.com")).one()
    assert user.password_hash.startswith("$2b$")
    assert PASSWORD not in user.password_hash


def test_register_normalizes_email_and_rejects_duplicates(client: TestClient) -> None:
    assert register(client, email="Ada@Example.com").json()["email"] == "ada@example.com"

    response = register(client, email="ADA@example.com")

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_register_rejects_short_password(client: TestClient) -> None:
    assert register(client, password="short").status_code == 422


def test_register_rejects_password_over_72_bytes(client: TestClient) -> None:
    assert register(client, password="é" * 37).status_code == 422  # 74 bytes


def test_register_rejects_invalid_email(client: TestClient) -> None:
    assert register(client, email="not-an-email").status_code == 422


# --- Login ---------------------------------------------------------------------------------


def test_login_with_correct_password_sets_httponly_cookie(
    client: TestClient, session: Session
) -> None:
    make_login_user(session)

    response = client.post(
        "/api/auth/login", json={"email": "ADA@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert client.get("/api/auth/me").status_code == 200


def test_login_with_wrong_password_is_rejected(client: TestClient, session: Session) -> None:
    make_login_user(session)

    response = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "wrong-password-1"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert "set-cookie" not in response.headers
    assert client.get("/api/auth/me").status_code == 401


def test_login_unknown_email_gives_same_error_as_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_inactive_user_is_rejected(client: TestClient, session: Session) -> None:
    make_login_user(session, is_active=False)

    response = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_session_token_is_stored_only_as_hash(client: TestClient, session: Session) -> None:
    make_login_user(session)
    client.post("/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    token = client.cookies[COOKIE]

    stored = session.exec(select(UserSession)).all()
    assert [s.token_hash for s in stored] == [hash_session_token(token)]
    assert token not in stored[0].token_hash


# --- Unauthenticated access, logout, and session validity -----------------------------------


def test_me_requires_sign_in(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not signed in"


def test_me_rejects_forged_cookie(client: TestClient) -> None:
    client.cookies.set(COOKIE, "forged-token")

    assert client.get("/api/auth/me").status_code == 401


def test_logout_revokes_session_and_old_cookie_stops_working(
    client: TestClient, session: Session
) -> None:
    register(client)
    old_token = client.cookies[COOKIE]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE, old_token)
    assert client.get("/api/auth/me").status_code == 401
    stored = session.exec(select(UserSession)).one()
    assert stored.revoked_at is not None


def test_logout_without_session_is_harmless(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_expired_session_is_rejected(client: TestClient, session: Session) -> None:
    register(client)
    stored = session.exec(select(UserSession)).one()
    stored.expires_at = utc_now() - timedelta(seconds=1)
    session.add(stored)
    session.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_deactivated_user_loses_existing_session(client: TestClient, session: Session) -> None:
    register(client)
    user = session.exec(select(AppUser)).one()
    user.is_active = False
    session.add(user)
    session.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_me_includes_company_membership(client: TestClient, session: Session) -> None:
    register(client)
    user = session.exec(select(AppUser)).one()
    company = f.make_company(session, display_name="Demo Harvest Foods")
    f.make_member(session, user, company)

    membership = client.get("/api/auth/me").json()["membership"]

    assert membership == {
        "company_id": str(company.company_id),
        "company_display_name": "Demo Harvest Foods",
        "company_review_status": "PENDING_REVIEW",
        "role": "OWNER",
    }
