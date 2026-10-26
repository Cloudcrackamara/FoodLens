from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings
from app.core.db import DbSession
from app.core.rate_limit import enforce_rate_limit
from app.models import Area
from app.models.base import utc_now
from app.models.enums import RateLimitBucket
from app.schemas.check import (
    CheckRequest,
    CheckResponse,
    DemoCity,
    ReportRequest,
    ReportResponse,
)
from app.services import check as check_service
from app.services import location, rate_limit_counts, reports
from app.services.check import WAT

router = APIRouter(prefix="/api/check", tags=["check"])


def current_time() -> datetime:
    return utc_now()


def app_settings(request: Request) -> Settings:
    return request.app.state.settings


Now = Annotated[datetime, Depends(current_time)]
AppSettings = Annotated[Settings, Depends(app_settings)]


def _limit(
    request: Request, db: DbSession, name: str, bucket: RateLimitBucket, area: Area | None
) -> None:
    """Rate limit per network (D119). A hit is also counted for the area and day (D144)."""
    try:
        enforce_rate_limit(request, name)
    except HTTPException as error:
        if error.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            day = utc_now().astimezone(WAT).date()
            rate_limit_counts.count_hit(db, area.area_id if area else None, bucket, day)
        raise


@router.post("/qr")
def check_qr(
    body: CheckRequest, request: Request, db: DbSession, settings: AppSettings, now: Now
) -> CheckResponse:
    """Public: no sign-in, no cookies. Scanned QR codes, /p/{token} links and typed codes.
    The visitor's IP is used only to find a coarse area and is then discarded (D118)."""
    area = location.resolve_area(db, request, settings, body.simulated_city)
    _limit(request, db, "check", RateLimitBucket.CHECK, area)
    return check_service.check_code(
        db,
        body.code,
        body.identifier_type,
        area=area,
        now=now,
        window_hours=settings.just_sold_window_hours,
    )


@router.post("/report", status_code=status.HTTP_201_CREATED)
def report_concern(
    body: ReportRequest, request: Request, db: DbSession, settings: AppSettings
) -> ReportResponse:
    """Anonymous concern report (D120): no contact field, no identifiers kept."""
    area = location.resolve_area(db, request, settings, body.simulated_city)
    _limit(request, db, "report", RateLimitBucket.REPORT, area)
    reports.submit_report(
        db,
        code=body.code,
        concern_type=body.concern_type,
        description=body.description,
        area=area,
    )
    return ReportResponse(message=reports.RECEIVED)


@router.get("/demo-cities")
def demo_cities(db: DbSession, settings: AppSettings) -> list[DemoCity]:
    """The demo city picker. 404 unless SIMULATE_LOCATION_ENABLED is true."""
    if not settings.simulate_location_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location simulation is off.")
    return [DemoCity(city=a.city, state=a.state) for a in location.demo_cities(db)]
