import pytest
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import verify_password
from app.models import AppUser
from app.seed import SeedConfigError, seed_admin
from tests import factories as f


def settings(**overrides) -> Settings:
    values = {
        "seed_admin_email": "Admin@FoodLens-Demo.example",
        "seed_admin_password": "demo-admin-password",
    } | overrides
    return Settings(**values)


def test_seed_admin_creates_admin_from_settings(session: Session) -> None:
    admin = seed_admin(session, settings())

    assert admin is not None
    assert admin.email == "admin@foodlens-demo.example"
    assert admin.is_admin is True
    assert verify_password("demo-admin-password", admin.password_hash)


def test_seed_admin_is_idempotent(session: Session) -> None:
    seed_admin(session, settings())
    seed_admin(session, settings())

    admins = session.exec(select(AppUser).where(AppUser.is_admin.is_(True))).all()
    assert len(admins) == 1


def test_seed_admin_promotes_existing_account_without_changing_password(
    session: Session,
) -> None:
    existing = f.make_user(session, email="admin@foodlens-demo.example")

    admin = seed_admin(session, settings())

    assert admin.user_id == existing.user_id
    assert admin.is_admin is True
    assert admin.password_hash == "not-a-real-hash"


def test_seed_admin_skipped_without_env(session: Session) -> None:
    assert seed_admin(session, settings(seed_admin_email=None, seed_admin_password=None)) is None
    assert session.exec(select(AppUser)).all() == []


def test_seed_admin_rejects_weak_password(session: Session) -> None:
    with pytest.raises(SeedConfigError):
        seed_admin(session, settings(seed_admin_password="short"))
