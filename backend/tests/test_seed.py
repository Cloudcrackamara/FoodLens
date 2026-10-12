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


# --- Demo orders (D101) -------------------------------------------------------------------------


def _seed_orders(session: Session, password: str | None = None):
    from app.demo_data import seed_demo_data, seed_demo_orders

    seed_demo_data(session)
    seed_demo_orders(session, password)
    seed_demo_orders(session, password)  # idempotent


def test_demo_orders_cover_every_status(session: Session) -> None:
    from app.models import OrderBatchAllocation, WholesaleOrder
    from app.models.enums import OrderStatus

    _seed_orders(session)

    orders = session.exec(select(WholesaleOrder)).all()
    assert sorted(o.status for o in orders) == sorted(
        [OrderStatus.REQUESTED, OrderStatus.ACCEPTED, OrderStatus.DECLINED, OrderStatus.FULFILLED]
    )
    assert len(session.exec(select(OrderBatchAllocation)).all()) == 1


def test_demo_accounts_cannot_sign_in_without_password(session: Session) -> None:
    from app.demo_data import DEMO_BUYER_EMAIL

    _seed_orders(session)

    buyer = session.exec(select(AppUser).where(AppUser.email == DEMO_BUYER_EMAIL)).one()
    assert not verify_password("", buyer.password_hash)
    assert not verify_password("anything-at-all", buyer.password_hash)
    assert buyer.is_admin is False


def test_demo_accounts_use_seed_demo_password(session: Session) -> None:
    from app.demo_data import DEMO_SELLER_EMAIL

    _seed_orders(session, "demo-orders-password")

    seller = session.exec(select(AppUser).where(AppUser.email == DEMO_SELLER_EMAIL)).one()
    assert verify_password("demo-orders-password", seller.password_hash)


def test_demo_password_must_be_long_enough() -> None:
    from app.seed import demo_password

    assert demo_password(Settings(seed_demo_password=None)) is None
    with pytest.raises(SeedConfigError):
        demo_password(Settings(seed_demo_password="short"))
