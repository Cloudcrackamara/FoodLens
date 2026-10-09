"""Change notice routes for company members and admins."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import AdminUser, require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.models.change import MAX_ATTACHMENT_BYTES
from app.models.enums import ChangeNoticeStatus
from app.schemas.change_notice import (
    AdminChangeNoticeRead,
    AttachmentRead,
    ChangeNoticeCreateRequest,
    ChangeNoticeRead,
    ClarificationResponseRequest,
    NoticeDecisionRequest,
)
from app.services import change_notices as notice_service
from app.services import companies as company_service

router = APIRouter(tags=["change notices"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
COMPANY = "/api/companies/{company_id}/change-notices"


def storage_dir(request: Request) -> Path:
    return request.app.state.upload_dir


StorageDir = Annotated[Path, Depends(storage_dir)]


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, company_service.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, company_service.ConflictOfInterestError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN, "Admins cannot review a company they belong to"
        )
    if isinstance(exc, company_service.InvalidTransitionError):
        return HTTPException(status.HTTP_409_CONFLICT, exc.message)
    if isinstance(exc, notice_service.StaleNoticeError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "The record changed after this notice was submitted. Reject it and ask the company "
            "for a new notice.",
        )
    if isinstance(exc, notice_service.InvalidChangesError | notice_service.InvalidAttachmentError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message)
    if isinstance(exc, notice_service.AttachmentTooLargeError):
        return HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Files can be at most {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB",
        )
    raise exc


_HANDLED = (
    company_service.NotFoundError,
    company_service.ConflictOfInterestError,
    company_service.InvalidTransitionError,
    notice_service.StaleNoticeError,
    notice_service.InvalidChangesError,
    notice_service.InvalidAttachmentError,
    notice_service.AttachmentTooLargeError,
)


def _file_response(path: Path, attachment) -> FileResponse:
    return FileResponse(
        path,
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


# --- Company members ----------------------------------------------------------------------


@router.get(COMPANY)
def list_company_notices(
    company_id: uuid.UUID, member: Member, db: DbSession
) -> list[ChangeNoticeRead]:
    return [
        notice_service.notice_read(db, n)
        for n in notice_service.company_notices(db, member.company_id)
    ]


@router.post(COMPANY, status_code=status.HTTP_201_CREATED)
def submit_notice(
    company_id: uuid.UUID, body: ChangeNoticeCreateRequest, member: Member, db: DbSession
) -> ChangeNoticeRead:
    try:
        notice = notice_service.submit_notice(db, member, body)
    except _HANDLED as exc:
        raise _http(exc) from None
    return notice_service.notice_read(db, notice)


@router.post(COMPANY + "/{notice_id}/respond")
def respond(
    company_id: uuid.UUID,
    notice_id: uuid.UUID,
    body: ClarificationResponseRequest,
    member: Member,
    db: DbSession,
) -> ChangeNoticeRead:
    try:
        notice = notice_service.respond_to_clarification(db, member, notice_id, body.message)
    except _HANDLED as exc:
        raise _http(exc) from None
    return notice_service.notice_read(db, notice)


@router.post(COMPANY + "/{notice_id}/attachments", status_code=status.HTTP_201_CREATED)
def upload_attachment(
    company_id: uuid.UUID,
    notice_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    member: Member,
    db: DbSession,
    upload_dir: StorageDir,
) -> AttachmentRead:
    try:
        attachment = notice_service.add_attachment(
            db, member, notice_id, file.filename, file.file, upload_dir
        )
    except _HANDLED as exc:
        raise _http(exc) from None
    return AttachmentRead.model_validate(attachment, from_attributes=True)


@router.get("/api/companies/{company_id}/attachments/{attachment_id}")
def download_own_attachment(
    company_id: uuid.UUID,
    attachment_id: uuid.UUID,
    member: Member,
    db: DbSession,
    upload_dir: StorageDir,
) -> FileResponse:
    try:
        attachment = notice_service.attachment_for_member(db, member, attachment_id)
        path = notice_service.attachment_path(upload_dir, attachment)
    except _HANDLED as exc:
        raise _http(exc) from None
    return _file_response(path, attachment)


# --- Admins -------------------------------------------------------------------------------


@router.get("/api/admin/change-notices")
def list_notices(
    admin: AdminUser, db: DbSession, review_status: ChangeNoticeStatus | None = None
) -> list[AdminChangeNoticeRead]:
    return [
        notice_service.admin_notice_read(db, n)
        for n in notice_service.list_notices(db, review_status)
    ]


@router.post("/api/admin/change-notices/{notice_id}/decision")
def decide_notice(
    notice_id: uuid.UUID, body: NoticeDecisionRequest, admin: AdminUser, db: DbSession
) -> AdminChangeNoticeRead:
    try:
        notice = notice_service.decide_notice(db, admin, notice_id, body.decision, body.note)
    except _HANDLED as exc:
        raise _http(exc) from None
    return notice_service.admin_notice_read(db, notice)


@router.get("/api/admin/attachments/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID, admin: AdminUser, db: DbSession, upload_dir: StorageDir
) -> FileResponse:
    try:
        attachment = notice_service.attachment_for_admin(db, attachment_id)
        path = notice_service.attachment_path(upload_dir, attachment)
    except _HANDLED as exc:
        raise _http(exc) from None
    return _file_response(path, attachment)
