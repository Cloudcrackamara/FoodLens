"""Simulated till API for /demo/pos (D123, D151). Registered only with DEMO_POS_ENABLED=true.
Thin: services/demo_pos.py signs each request and runs the real POS verification."""

from fastapi import APIRouter, Request

from app.core.auth import CurrentUser
from app.core.db import DbSession
from app.models.base import utc_now
from app.models.enums import LifecycleEventType
from app.schemas.pos import (
    DemoLookupRequest,
    DemoTillRead,
    DemoVoidRequest,
    PosEventResponse,
    PosLookupResponse,
)
from app.services import demo_pos

router = APIRouter(prefix="/api/demo/pos", tags=["demo"])


@router.get("/tills")
def tills(user: CurrentUser, db: DbSession) -> list[DemoTillRead]:
    ctx = demo_pos.context(db, user)
    return [
        DemoTillRead(
            till_ref=till.till_ref,
            retailer_name=ctx.retailer.display_name,
            location_name=location.name,
            area=location.area,
        )
        for till, location in demo_pos.tills(db, ctx)
    ]


@router.post("/lookup")
def lookup(
    body: DemoLookupRequest, request: Request, user: CurrentUser, db: DbSession
) -> PosLookupResponse:
    ctx = demo_pos.context(db, user)
    state = request.app.state
    return demo_pos.lookup(
        db, state.settings, state.rate_limiters, ctx, body.till_ref, body.code, utc_now()
    )


def _record(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    event_type: LifecycleEventType,
    body: DemoLookupRequest,
    reason: str | None = None,
) -> PosEventResponse:
    ctx = demo_pos.context(db, user)
    state = request.app.state
    return demo_pos.record(
        db,
        state.settings,
        state.rate_limiters,
        ctx,
        event_type,
        body.till_ref,
        body.code,
        utc_now(),
        reason,
    )


@router.post("/sales")
def sale(
    body: DemoLookupRequest, request: Request, user: CurrentUser, db: DbSession
) -> PosEventResponse:
    """The demo "Confirm payment" button. No payment happens; FoodLens records the sale only."""
    return _record(request, user, db, LifecycleEventType.SOLD, body)


@router.post("/refunds")
def refund(
    body: DemoLookupRequest, request: Request, user: CurrentUser, db: DbSession
) -> PosEventResponse:
    return _record(request, user, db, LifecycleEventType.RETURNED, body)


@router.post("/voids")
def void(
    body: DemoVoidRequest, request: Request, user: CurrentUser, db: DbSession
) -> PosEventResponse:
    return _record(request, user, db, LifecycleEventType.SALE_CORRECTED, body, body.reason)
