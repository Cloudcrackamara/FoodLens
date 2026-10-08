"""Load demo data. Run with: uv run python -m app.seed

Creates the seed admin from SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD when both are set.
Safe to run repeatedly. All demo data must be obviously fictional and use DEMO- references.
"""

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.db import get_engine
from app.core.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH, hash_password
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


def main() -> None:
    with Session(get_engine()) as db:
        admin = seed_admin(db, get_settings())
    if admin is None:
        print("Seed admin skipped: set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD in backend/.env.")
    else:
        print(f"Seed admin ready: {admin.email}")


if __name__ == "__main__":
    main()
