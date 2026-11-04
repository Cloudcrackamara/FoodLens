"""POS partner credentials and signed-request verification (D121, D151).

- API keys are shown once and stored only as a SHA-256 hash plus an 8-character prefix.
- The signing secret is shown once and stored Fernet-encrypted under POS_SECRET_KEY, because
  verifying an HMAC needs the raw secret.
- A request carries X-FoodLens-Key, X-FoodLens-Timestamp (Unix seconds) and X-FoodLens-Signature,
  the hex HMAC-SHA256(secret, "{timestamp}.{raw_body}"). Signing the timestamp with the body
  stops a captured body being replayed under a fresh timestamp.

Verification runs in this order: headers, key, per-partner rate limit, timestamp, signature.
The body is parsed only after the signature matches. The simulated till (D123) skips only the
key step, because the raw demo key is never stored (D151).
"""

import hashlib
import hmac
import secrets
from collections.abc import Mapping
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.rate_limit import RateLimiters
from app.models import PosPartner, PosPartnerKey
from app.models.enums import PosPartnerStatus, RateLimitBucket
from app.services import rate_limit_counts
from app.services.check import WAT

KEY_HEADER = "X-FoodLens-Key"
TIMESTAMP_HEADER = "X-FoodLens-Timestamp"
SIGNATURE_HEADER = "X-FoodLens-Signature"

KEY_PREFIX = "flk_"
SECRET_PREFIX = "fls_"

# Approved wording (2026-10-30).
MSG_MISSING_SIGNATURE = (
    "Missing X-FoodLens-Key, X-FoodLens-Timestamp or X-FoodLens-Signature header."
)
MSG_INVALID_KEY = "API key not recognised."
MSG_STALE = "Request timestamp is too far from the server time. Check the till clock."
MSG_INVALID_SIGNATURE = "Signature does not match the request."
MSG_NOT_CONFIGURED = "POS integration is not set up on this server."
MSG_INVALID_BODY = "Request body is not valid. Check the fields against the POS integration guide."


def msg_rate_limited(seconds: int) -> str:
    return f"Too many requests. Try again in {seconds} seconds."


class PosError(Exception):
    """A refused POS request. The app returns {"error": {"code", "message"}} with `status_code`."""

    def __init__(
        self, code: str, message: str, status_code: int, headers: dict[str, str] | None = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = headers


def new_api_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def new_signing_secret() -> str:
    return SECRET_PREFIX + secrets.token_urlsafe(32)


def key_hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _fernet(settings: Settings) -> Fernet:
    if not settings.pos_secret_key:
        raise PosError("POS_NOT_CONFIGURED", MSG_NOT_CONFIGURED, 503)
    try:
        return Fernet(settings.pos_secret_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise PosError("POS_NOT_CONFIGURED", MSG_NOT_CONFIGURED, 503) from None


def ensure_configured(settings: Settings) -> None:
    _fernet(settings)


def encrypt_secret(settings: Settings, raw_secret: str) -> str:
    return _fernet(settings).encrypt(raw_secret.encode("utf-8")).decode("ascii")


def decrypt_secret(settings: Settings, partner: PosPartner) -> str:
    try:
        return _fernet(settings).decrypt(partner.signing_secret_encrypted.encode("ascii")).decode()
    except InvalidToken:
        # Encrypted under another POS_SECRET_KEY: the partner cannot be verified on this server.
        raise PosError("POS_NOT_CONFIGURED", MSG_NOT_CONFIGURED, 503) from None


def sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("ascii") + b"." + raw_body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def partner_for_key(db: Session, raw_key: str) -> PosPartner:
    """The active partner owning this unrevoked key. Wrong, revoked and suspended all give the
    same answer, so a caller cannot tell which."""
    key = db.exec(select(PosPartnerKey).where(PosPartnerKey.key_hash == key_hash(raw_key))).first()
    partner = db.get(PosPartner, key.partner_id) if key and key.revoked_at is None else None
    if partner is None or partner.status != PosPartnerStatus.ACTIVE:
        raise PosError("INVALID_KEY", MSG_INVALID_KEY, 401)
    return partner


def enforce_partner_limit(db: Session, limiters: RateLimiters, partner: PosPartner) -> None:
    retry = limiters.retry_after("pos", str(partner.partner_id))
    if retry is not None:
        # D144 counts hits per area; a POS hit has no visitor area, so it is counted without one.
        rate_limit_counts.count_hit(db, None, RateLimitBucket.POS, datetime.now(WAT).date())
        raise PosError(
            "RATE_LIMITED", msg_rate_limited(retry), 429, headers={"Retry-After": str(retry)}
        )


def verify_signature(
    settings: Settings,
    partner: PosPartner,
    timestamp: str,
    signature: str,
    raw_body: bytes,
    now: datetime,
) -> None:
    try:
        sent = int(timestamp)
    except ValueError:
        raise PosError("STALE_TIMESTAMP", MSG_STALE, 401) from None
    if abs(now.timestamp() - sent) > settings.pos_max_skew_seconds:
        raise PosError("STALE_TIMESTAMP", MSG_STALE, 401)
    expected = sign(decrypt_secret(settings, partner), timestamp, raw_body)
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise PosError("INVALID_SIGNATURE", MSG_INVALID_SIGNATURE, 401)


def parse[M: BaseModel](model: type[M], raw_body: bytes) -> M:
    """Parse a verified body. Unknown fields are refused by the models (no payment data)."""
    try:
        return model.model_validate_json(raw_body)
    except ValidationError:
        raise PosError("INVALID_BODY", MSG_INVALID_BODY, 422) from None


def authenticate(
    db: Session,
    settings: Settings,
    limiters: RateLimiters,
    headers: Mapping[str, str],
    raw_body: bytes,
    now: datetime,
) -> PosPartner:
    """Full check for a partner request. `headers` is a case-insensitive mapping."""
    ensure_configured(settings)
    raw_key = headers.get(KEY_HEADER)
    timestamp = headers.get(TIMESTAMP_HEADER)
    signature = headers.get(SIGNATURE_HEADER)
    if not raw_key or not timestamp or not signature:
        raise PosError("MISSING_SIGNATURE", MSG_MISSING_SIGNATURE, 401)
    partner = partner_for_key(db, raw_key)
    enforce_partner_limit(db, limiters, partner)
    verify_signature(settings, partner, timestamp, signature, raw_body, now)
    return partner
