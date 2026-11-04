"""Load demo data. Run with: uv run python -m app.seed

Creates the seed admin from SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD when both are set, then the
fictional demo companies, catalogue, orders and the unit-identity scenario (app/demo_data.py).
The demo accounts can sign in only when SEED_DEMO_PASSWORD is set. Safe to run repeatedly.

`uv run python -m app.seed --reset` first deletes ALL data in DATABASE_URL (accounts included,
only the reference areas stay) and seeds afresh. It runs only with APP_ENV=development.
"""

import sys

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.db import get_engine
from app.core.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH, hash_password
from app.demo_data import (
    DEMO_BUYER_EMAIL,
    DEMO_SELLER_EMAIL,
    seed_demo_data,
    seed_demo_orders,
    seed_demo_pos,
    seed_demo_scenario,
)
from app.models import AppUser
from app.services.auth import normalize_email


class SeedConfigError(Exception):
    pass


def seed_admin(db: Session, settings: Settings) -> AppUser | None:
    """Create the admin, or promote an existing account with that email. The password of an
    existing account is never overwritten. Returns None when the env vars are not set."""
    if not settings.seed_admin_email or not settings.seed_admin_password:
        return None

    password = settings.seed_admin_password
    if len(password) < MIN_PASSWORD_LENGTH or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise SeedConfigError(
            f"SEED_ADMIN_PASSWORD must be {MIN_PASSWORD_LENGTH} characters to "
            f"{MAX_PASSWORD_BYTES} bytes long"
        )

    email = normalize_email(settings.seed_admin_email)
    user = db.exec(select(AppUser).where(AppUser.email == email)).first()
    if user is None:
        user = AppUser(
            email=email,
            password_hash=hash_password(password),
            display_name=settings.seed_admin_display_name,
        )
    user.is_admin = True
    user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def demo_password(settings: Settings) -> str | None:
    """SEED_DEMO_PASSWORD, checked like any account password; None when not set."""
    password = settings.seed_demo_password or None
    if password and (
        len(password) < MIN_PASSWORD_LENGTH or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
    ):
        raise SeedConfigError(
            f"SEED_DEMO_PASSWORD must be {MIN_PASSWORD_LENGTH} characters to "
            f"{MAX_PASSWORD_BYTES} bytes long"
        )
    return password


def check_can_reset(settings: Settings) -> None:
    """Refuse before anything is deleted: outside development, or when the seed that follows could
    not rebuild the scenario or its sign-ins."""
    if settings.app_env != "development":
        raise SeedConfigError(f"--reset runs only with APP_ENV=development, not {settings.app_env}")
    required = {
        "POS_SECRET_KEY": settings.pos_secret_key,
        "SEED_ADMIN_EMAIL": settings.seed_admin_email,
        "SEED_ADMIN_PASSWORD": settings.seed_admin_password,
        "SEED_DEMO_PASSWORD": settings.seed_demo_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SeedConfigError(
            f"--reset deleted nothing: set {', '.join(missing)} in backend/.env first "
            "(README.md, Run the demo)"
        )


def reset_database(db: Session) -> None:
    """Empty every table except the migration version and the reference areas."""
    tables = db.exec(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename NOT IN ('alembic_version', 'area')"
        )
    ).all()
    names = ", ".join(f'"{name}"' for (name,) in tables)
    db.exec(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    db.commit()


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    reset = args == ["--reset"]
    if args and not reset:
        raise SystemExit("Usage: python -m app.seed [--reset]")
    settings = get_settings()
    password = demo_password(settings)
    if reset:
        check_can_reset(settings)
    with Session(get_engine()) as db:
        if reset:
            reset_database(db)
            print("Database emptied.")
        admin = seed_admin(db, settings)
        # Read now: later commits expire the object, and the session closes after this block.
        admin_email = admin.email if admin else None
        seed_demo_data(db)
        seed_demo_orders(db, password)
        if admin is not None:
            admin = db.get(AppUser, admin.user_id)
        pos_line = seed_demo_pos(db, settings, admin, password)
        scenario_line = seed_demo_scenario(db, settings)
    if admin_email is None:
        print("Seed admin skipped: set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD in backend/.env.")
    else:
        print(f"Seed admin ready: {admin_email}")
    print("Demo companies and catalogue ready.")
    if password:
        print(f"Demo order accounts ready: {DEMO_BUYER_EMAIL}, {DEMO_SELLER_EMAIL}")
    else:
        print("Demo order accounts cannot sign in: set SEED_DEMO_PASSWORD in backend/.env.")
    print(pos_line)
    print(scenario_line)
    off = [
        name
        for name, on in (
            ("DEMO_POS_ENABLED", settings.demo_pos_enabled),
            ("SIMULATE_LOCATION_ENABLED", settings.simulate_location_enabled),
        )
        if not on
    ]
    if off:
        print(f"The walkthrough also needs {' and '.join(off)}=true in backend/.env.")


if __name__ == "__main__":
    main()
