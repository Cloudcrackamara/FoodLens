"""POS partner API (/api/pos/v1, D121). Thin: verification is in services/pos_auth.py and the
rules are in services/pos.py. See docs/POS_INTEGRATION.md.

The raw body is read before anything else, because the signature covers the exact bytes sent.
It is parsed only after the key, rate limit, timestamp and signature have passed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.db import DbSession
from app.models import PosPartner
from app.models.base import utc_now
from app.models.enums import LifecycleEventType
from app.schemas.pos import (
    PosEventResponse,
    PosLookupRequest,
    PosLookupResponse,
    PosRefundRequest,
    PosSaleRequest,
    PosVoidRequest,
)
from app.services import pos, pos_auth
from app.services.pos_auth import PosError, parse

router = APIRouter(prefix="/api/pos/v1", tags=["pos"])


async def raw_body(request: Request) -> bytes:
    return await request.body()


RawBody = Annotated[bytes, Depends(raw_body)]


def pos_error_response(_request: Request, error: Exception) -> JSONResponse:
    """App-wide handler: POS errors use {"error": {"code", "message"}}."""
    assert isinstance(error, PosError)
    return JSONResponse(
        {"error": {"code": error.code, "message": error.message}},
        status_code=error.status_code,
        headers=error.headers,
    )


def _partner(request: Request, db: DbSession, raw: bytes) -> PosPartner:
    return pos_auth.authenticate(
        db,
        request.app.state.settings,
        request.app.state.rate_limiters,
        request.headers,
        raw,
        utc_now(),
    )


@router.post("/units/lookup")
def units_lookup(request: Request, db: DbSession, raw: RawBody) -> PosLookupResponse:
    """Read-only: product, GTIN, batch, expiry, status and a warning. Changes nothing."""
    partner = _partner(request, db, raw)
    return pos.lookup(db, partner, parse(PosLookupRequest, raw))


@router.post("/sales")
def sales(request: Request, db: DbSession, raw: RawBody) -> PosEventResponse:
    """Call only after the till has confirmed payment. Records SOLD per pack."""
    partner = _partner(request, db, raw)
    body = parse(PosSaleRequest, raw)
    return pos.record(
        db, request.app.state.settings, partner, body, LifecycleEventType.SOLD, utc_now()
    )


@router.post("/refunds")
def refunds(request: Request, db: DbSession, raw: RawBody) -> PosEventResponse:
    partner = _partner(request, db, raw)
    body = parse(PosRefundRequest, raw)
    return pos.record(
        db, request.app.state.settings, partner, body, LifecycleEventType.RETURNED, utc_now()
    )


@router.post("/voids")
def voids(request: Request, db: DbSession, raw: RawBody) -> PosEventResponse:
    partner = _partner(request, db, raw)
    body = parse(PosVoidRequest, raw)
    return pos.record(
        db,
        request.app.state.settings,
        partner,
        body,
        LifecycleEventType.SALE_CORRECTED,
        utc_now(),
    )
