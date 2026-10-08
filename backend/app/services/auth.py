"""Account and session rules. Routers map these errors to HTTP responses."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import (
    burn_password_check,
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from app.models import AppUser, Company, CompanyMember, UserSession
from app.models.base import utc_now
from app.models.enums import MembershipStatus


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    """Wrong email, wrong password, or inactive account. Deliberately not distinguished."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, *, email: str, password: str, display_name: str) -> AppUser:
    """Create an ordinary user. Only these three inputs are accepted; is_admin, is_active,
    and every other column keep their defaults, whatever the client sent."""
    email = normalize_email(email)
    if db.exec(select(AppUser).where(AppUser.email == email)).first() is not None:
        raise EmailAlreadyRegisteredError

    user = AppUser(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # Concurrent registration with the same email.
        db.rollback()
        raise EmailAlreadyRegisteredError from exc
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> AppUser:
    user = db.exec(select(AppUser).where(AppUser.email == normalize_email(email))).first()
    if user is None:
        burn_password_check(password)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash) or not user.is_active:
        raise InvalidCredentialsError
    return user


def create_session(db: Session, user: AppUser, *, now: datetime | None = None) -> str:
    """Start a session and return the raw token for the cookie. Only its hash is stored."""
    now = now or utc_now()
    token = new_session_token()
    db.add(
        UserSession(
            user_id=user.user_id,
            token_hash=hash_session_token(token),
            created_at=now,
            expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
        )
    )
    db.commit()
    return token


def user_for_session_token(
    db: Session, token: str, *, now: datetime | None = None
) -> AppUser | None:
    """The active user behind a valid, unexpired, unrevoked session, or None."""
    now = now or utc_now()
    statement = (
        select(AppUser)
        .join(UserSession, UserSession.user_id == AppUser.user_id)
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            AppUser.is_active.is_(True),
        )
    )
    return db.exec(statement).first()


def revoke_session(db: Session, token: str, *, now: datetime | None = None) -> None:
    session = db.exec(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
        )
    ).first()
    if session is not None:
        session.revoked_at = now or utc_now()
        db.add(session)
        db.commit()


def active_membership(
    db: Session, *, user_id: uuid.UUID, company_id: uuid.UUID | None = None
) -> CompanyMember | None:
    """The user's active membership, optionally only if it is for company_id."""
    statement = select(CompanyMember).where(
        CompanyMember.user_id == user_id,
        CompanyMember.membership_status == MembershipStatus.ACTIVE,
    )
    if company_id is not None:
        statement = statement.where(CompanyMember.company_id == company_id)
    return db.exec(statement).first()


def membership_with_company(db: Session, user: AppUser) -> tuple[CompanyMember, Company] | None:
    member = active_membership(db, user_id=user.user_id)
    if member is None:
        return None
    company = db.get(Company, member.company_id)
    return (member, company) if company is not None else None
