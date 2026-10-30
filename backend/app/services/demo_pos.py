"""Simulated till for /demo/pos (D123, D151). Only registered with DEMO_POS_ENABLED=true.

The browser sends a till and a code. The server builds the same JSON body a real till would send,
signs it with the demo partner's decrypted secret, and passes it through the real checks: the
per-partner rate limit, timestamp, HMAC signature, body parsing, retailer link and till, then the
same services/pos.py functions. Only the API key lookup is skipped, because the raw demo key is
never stored (D151). The browser never sees a key or secret.

Only signed-in members of a retailer linked to the demo partner can use it, and only with their
own company's tills.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.rate_limit import RateLimiters
from app.models import AppUser, Company, PosPartner, PosTill, SupplierLocation
from app.models.enums import LifecycleEventType, PosPartnerStatus
from app.schemas.pos import (
    PosEventResponse,
    PosLookupRequest,
    PosLookupResponse,
    PosRefundRequest,
    PosSaleRequest,
    PosVoidRequest,
)
from app.services import auth as auth_service
from app.services import pos, pos_auth
from app.services.pos_auth import PosError

DEMO_PARTNER_NAME = "Demo Till Systems (fictional)"

MSG_NOT_SET_UP = "The demo till is not set up on this server."
MSG_NO_RETAILER = "Sign in as a member of a retailer linked to the demo till."


@dataclass
class DemoContext:
    partner: PosPartner
    retailer: Company


def demo_partner(db: Session) -> PosPartner:
    partner = db.exec(select(PosPartner).where(PosPartner.name == DEMO_PARTNER_NAME)).first()
    if partner is None or partner.status != PosPartnerStatus.ACTIVE:
        raise PosError("DEMO_NOT_SET_UP", MSG_NOT_SET_UP, 404)
    return partner


def context(db: Session, user: AppUser) -> DemoContext:
    partner = demo_partner(db)
    found = auth_service.membership_with_company(db, user)
    if found is None or not found[1].is_retailer:
        raise PosError("NOT_A_RETAILER", MSG_NO_RETAILER, 403)
    return DemoContext(partner, found[1])


def tills(db: Session, ctx: DemoContext) -> list[tuple[PosTill, SupplierLocation]]:
    return list(
        db.exec(
            select(PosTill, SupplierLocation)
            .join(SupplierLocation, SupplierLocation.location_id == PosTill.location_id)
            .where(
                PosTill.partner_id == ctx.partner.partner_id,
                PosTill.retailer_company_id == ctx.retailer.company_id,
            )
            .order_by(PosTill.till_ref)
        ).all()
    )


def _reference(prefix: str) -> str:
    return f"DEMO-{prefix}-{secrets.token_hex(6).upper()}"


def _signed[M: BaseModel](
    db: Session,
    settings: Settings,
    limiters: RateLimiters,
    ctx: DemoContext,
    payload: dict,
    model: type[M],
    now: datetime,
) -> M:
    """Sign the body as a till would, then run the same verification the real API runs."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(now.timestamp()))
    signature = pos_auth.sign(pos_auth.decrypt_secret(settings, ctx.partner), timestamp, raw)
    pos_auth.enforce_partner_limit(db, limiters, ctx.partner)
    pos_auth.verify_signature(settings, ctx.partner, timestamp, signature, raw, now)
    return pos_auth.parse(model, raw)


def _base(ctx: DemoContext, till_ref: str) -> dict:
    return {"retailer_id": str(ctx.retailer.company_id), "till_id": till_ref}


def lookup(
    db: Session,
    settings: Settings,
    limiters: RateLimiters,
    ctx: DemoContext,
    till_ref: str,
    code: str,
    now: datetime,
) -> PosLookupResponse:
    payload = _base(ctx, till_ref) | {"code": code}
    body = _signed(db, settings, limiters, ctx, payload, PosLookupRequest, now)
    return pos.lookup(db, ctx.partner, body)


def record(
    db: Session,
    settings: Settings,
    limiters: RateLimiters,
    ctx: DemoContext,
    event_type: LifecycleEventType,
    till_ref: str,
    code: str,
    now: datetime,
    reason: str | None = None,
) -> PosEventResponse:
    payload = _base(ctx, till_ref) | {"occurred_at": now.isoformat(), "units": [code]}
    model: type[PosSaleRequest] | type[PosRefundRequest] | type[PosVoidRequest]
    match event_type:
        case LifecycleEventType.SOLD:
            payload |= {
                "transaction_id": _reference("TXN"),
                "payment_reference": _reference("PAY"),
            }
            model = PosSaleRequest
        case LifecycleEventType.RETURNED:
            payload |= {"transaction_id": _reference("RFD")}
            model = PosRefundRequest
        case _:
            payload |= {"transaction_id": _reference("VOID"), "reason": reason}
            model = PosVoidRequest
    body = _signed(db, settings, limiters, ctx, payload, model, now)
    return pos.record(db, settings, ctx.partner, body, event_type, now)
