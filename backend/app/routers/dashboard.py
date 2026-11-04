"""Manufacturer and admin dashboard reads (D144, D154). Thin: rules live in services/. Company
routes take the company from require_company_member, so a member only reaches their own data."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AdminUser, CurrentUser, require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.models.base import utc_now
from app.models.enums import ReportStatus
from app.schemas.dashboard import (
    ManufacturerStatsRead,
    PartnerRead,
    PlatformStatsRead,
    ReportRead,
    ReportStatusRequest,
    ScanningRowRead,
    TimelineRead,
    TimelineRequest,
)
from app.services import partners, reports, stats, timeline

router = APIRouter(tags=["dashboard"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
COMPANY = "/api/companies/{company_id}"


def _timeline_missing() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, timeline.MSG_NOT_FOUND)


def _report_read(view: reports.ReportView) -> ReportRead:
    report = view.report
    return ReportRead(
        report_id=report.report_id,
        concern_type=report.concern_type,
        description=report.description,
        status=report.status,
        manufacturer_name=view.manufacturer_name,
        product_name=view.product_name,
        batch_number=view.batch_number,
        area=view.area,
        created_at=report.created_at,
    )


# --- Manufacturer members ------------------------------------------------------------------


@router.post(f"{COMPANY}/units/timeline")
def pack_timeline(
    company_id: uuid.UUID, body: TimelineRequest, member: Member, db: DbSession
) -> TimelineRead:
    """A POST, so the code stays out of URLs and logs. Writes nothing."""
    try:
        return TimelineRead.model_validate(timeline.by_code(db, company_id, body.code))
    except timeline.TimelineNotFound:
        raise _timeline_missing() from None


@router.get(f"{COMPANY}/alerts/{{alert_id}}/timeline")
def alert_timeline(
    company_id: uuid.UUID, alert_id: uuid.UUID, member: Member, db: DbSession
) -> TimelineRead:
    try:
        return TimelineRead.model_validate(timeline.by_alert(db, company_id, alert_id))
    except timeline.TimelineNotFound:
        raise _timeline_missing() from None


@router.get(f"{COMPANY}/partners")
def list_partners(company_id: uuid.UUID, member: Member, db: DbSession) -> list[PartnerRead]:
    return [
        PartnerRead(
            display_name=p.company.display_name,
            is_manufacturer=p.company.is_manufacturer,
            is_distributor=p.company.is_distributor,
            is_retailer=p.company.is_retailer,
            places=p.places,
            received=p.received,
            sold=p.sold,
            pos_partners=p.pos_partners,
        )
        for p in partners.partners(db, company_id)
    ]


@router.get(f"{COMPANY}/stats")
def manufacturer_stats(
    company_id: uuid.UUID, member: Member, db: DbSession
) -> ManufacturerStatsRead:
    return ManufacturerStatsRead.model_validate(stats.manufacturer_stats(db, company_id, utc_now()))


@router.get(f"{COMPANY}/reports")
def company_reports(
    company_id: uuid.UUID, member: Member, db: DbSession, status: ReportStatus | None = None
) -> list[ReportRead]:
    views = reports.list_reports(db, manufacturer_id=company_id, status=status, admin=False)
    return [_report_read(v) for v in views]


@router.post(f"{COMPANY}/reports/{{report_id}}/status")
def company_report_status(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    body: ReportStatusRequest,
    member: Member,
    user: CurrentUser,
    db: DbSession,
) -> ReportRead:
    try:
        return _report_read(
            reports.change_status(
                db, user, report_id, body.status, manufacturer_id=company_id, admin=False
            )
        )
    except reports.ReportError as error:
        raise HTTPException(error.status_code, error.message) from None


# --- Admins ---------------------------------------------------------------------------------


@router.get("/api/admin/stats")
def platform_stats(admin: AdminUser, db: DbSession) -> PlatformStatsRead:
    return PlatformStatsRead.model_validate(stats.platform_stats(db, utc_now()))


@router.get("/api/admin/scanning")
def scanning_panel(admin: AdminUser, db: DbSession) -> list[ScanningRowRead]:
    return [ScanningRowRead.model_validate(r) for r in stats.scanning_panel(db, utc_now())]


@router.get("/api/admin/reports")
def admin_reports(
    admin: AdminUser, db: DbSession, status: ReportStatus | None = None
) -> list[ReportRead]:
    views = reports.list_reports(db, manufacturer_id=None, status=status, admin=True)
    return [_report_read(v) for v in views]


@router.post("/api/admin/reports/{report_id}/status")
def admin_report_status(
    report_id: uuid.UUID, body: ReportStatusRequest, admin: AdminUser, db: DbSession
) -> ReportRead:
    try:
        return _report_read(
            reports.change_status(
                db, admin, report_id, body.status, manufacturer_id=None, admin=True
            )
        )
    except reports.ReportError as error:
        raise HTTPException(error.status_code, error.message) from None
