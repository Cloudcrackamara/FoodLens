"""Password hashing and session tokens. No business rules here."""

import hashlib
import secrets
from functools import lru_cache

import bcrypt

from app.core.config import get_settings

MIN_PASSWORD_LENGTH = 10
# bcrypt only uses the first 72 bytes; longer passwords are rejected rather than truncated.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # Over-long password or malformed hash.
        return False


@lru_cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password-used-for-timing")


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check, so unknown emails are not revealed by timing."""
    verify_password(password, _dummy_hash())


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Only this hash is stored; a database leak does not expose usable cookies."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
