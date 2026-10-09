"""Product announcement routes for company members and admins."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AdminUser, require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.models.enums import AnnouncementStatus
from app.schemas.announcement import (
    AdminAnnouncementRead,
    AnnouncementCreateRequest,
    AnnouncementHideRequest,
    AnnouncementRead,
)
from app.services import announcements as announcement_service
from app.services import companies as company_service

router = APIRouter(tags=["announcements"])

Member = Annotated[CompanyMember, Depends(require_company_member())]

_HANDLED = (
    company_service.NotFoundError,
    company_service.CompanyNotApprovedError,
    company_service.ConflictOfInterestError,
    company_service.InvalidTransitionError,
    announcement_service.SafetyClaimError,
    announcement_service.RegulatorClaimError,
)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, company_service.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, company_service.CompanyNotApprovedError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "Announcements can be posted after FoodLens approves your company profile",
        )
    if isinstance(exc, company_service.ConflictOfInterestError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN, "Admins cannot review a company they belong to"
        )
    if isinstance(exc, company_service.InvalidTransitionError):
        return HTTPException(status.HTTP_409_CONFLICT, exc.message)
    if isinstance(exc, announcement_service.SafetyClaimError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            'Announcements cannot claim a product is "safe" or "unsafe".',
        )
    if isinstance(exc, announcement_service.RegulatorClaimError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Announcements cannot claim NAFDAC or SON approval, registration, or certification. "
            "Consumers check registration against the register instead.",
        )
    raise exc


@router.get("/api/companies/{company_id}/announcements")
def list_company_announcements(
    company_id: uuid.UUID, member: Member, db: DbSession
) -> list[AnnouncementRead]:
    return [
        announcement_service.announcement_read(db, a)
        for a in announcement_service.company_announcements(db, member.company_id)
    ]


@router.post(
    "/api/companies/{company_id}/products/{product_id}/announcements",
    status_code=status.HTTP_201_CREATED,
)
def post_announcement(
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    body: AnnouncementCreateRequest,
    member: Member,
    db: DbSession,
) -> AnnouncementRead:
    try:
        announcement = announcement_service.post_announcement(db, member, product_id, body)
    except _HANDLED as exc:
        raise _http(exc) from None
    return announcement_service.announcement_read(db, announcement)


@router.post("/api/companies/{company_id}/announcements/{announcement_id}/withdraw")
def withdraw_announcement(
    company_id: uuid.UUID, announcement_id: uuid.UUID, member: Member, db: DbSession
) -> AnnouncementRead:
    try:
        announcement = announcement_service.withdraw_announcement(db, member, announcement_id)
    except _HANDLED as exc:
        raise _http(exc) from None
    return announcement_service.announcement_read(db, announcement)


@router.get("/api/admin/announcements")
def list_announcements(
    admin: AdminUser, db: DbSession, status: AnnouncementStatus | None = None
) -> list[AdminAnnouncementRead]:
    return announcement_service.list_announcements(db, status)


@router.post("/api/admin/announcements/{announcement_id}/hide")
def hide_announcement(
    announcement_id: uuid.UUID, body: AnnouncementHideRequest, admin: AdminUser, db: DbSession
) -> AnnouncementRead:
    try:
        announcement = announcement_service.admin_hide_announcement(
            db, admin, announcement_id, body.reason
        )
    except _HANDLED as exc:
        raise _http(exc) from None
    return announcement_service.announcement_read(db, announcement)
