from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.db import DbSession
from app.core.rate_limit import limit_lookups
from app.schemas.lookup import LookupRequest, LookupResponse
from app.services import lookup as lookup_service

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


def today() -> date:
    return date.today()


@router.post("/batch", dependencies=[Depends(limit_lookups)])
def lookup_batch(
    body: LookupRequest, db: DbSession, on_date: Annotated[date, Depends(today)]
) -> LookupResponse:
    """Public: no sign-in, no cookies. Rate limited per network (D40)."""
    response, batch = lookup_service.lookup_batch(
        db, product_code=body.product_code, batch_number=body.batch_number, today=on_date
    )
    lookup_service.record_scan(db, response, batch)
    return response
