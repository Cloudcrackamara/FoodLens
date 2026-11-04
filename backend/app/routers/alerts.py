"""Risk alerts for the manufacturer's members and for admins (D125, D152). Thin: rules live in
services/alerts.py. A company route only ever reaches that company's own alerts."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import AdminUser, CurrentUser, require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.schemas.alerts import (
    AlertDetailRead,
    AlertNoteRead,
    AlertNoteRequest,
    AlertRead,
    AlertStatusRequest,
    StatusFilter,
)
from app.services import alerts
from app.services.risk import RULE_NAMES

router = APIRouter(tags=["alerts"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
COMPANY = "/api/companies/{company_id}/alerts"
ADMIN = "/api/admin/alerts"


def _read(found: alerts.AlertDetail) -> dict:
    alert = found.alert
    evidence = alert.evidence or {}
    return {
        "alert_id": alert.alert_id,
        "rule": alert.rule,
        "rule_name": RULE_NAMES[alert.rule],
        "level": alert.level,
        "status": alert.status,
        "explanation": evidence.get("explanation", ""),
        "occurrences": int(evidence.get("occurrences", 1)),
        "manufacturer_name": found.manufacturer_name,
        "product_name": found.product_name,
        "batch_number": found.batch_number,
        "carton_ref": found.carton_ref,
        "area": found.area,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
        "resolved_by_name": found.resolved_by_name,
        "resolved_at": alert.resolved_at,
    }


def _detail(found: alerts.AlertDetail) -> AlertDetailRead:
    return AlertDetailRead(
        **_read(found),
        snapshot=list((found.alert.evidence or {}).get("snapshot", [])),
        notes=[
            AlertNoteRead(author_name=name, body=note.body, created_at=note.created_at)
            for note, name in found.notes
        ],
    )


def _refuse(error: alerts.AlertError) -> HTTPException:
    return HTTPException(error.status_code, error.message)


# --- Manufacturer members ------------------------------------------------------------------


@router.get(COMPANY)
def company_alerts(
    company_id: uuid.UUID, member: Member, db: DbSession, status: StatusFilter = "OPEN"
) -> list[AlertRead]:
    return [AlertRead(**_read(a)) for a in alerts.list_for_company(db, company_id, status)]


@router.get(COMPANY + "/{alert_id}")
def company_alert(
    company_id: uuid.UUID, alert_id: uuid.UUID, member: Member, db: DbSession
) -> AlertDetailRead:
    try:
        return _detail(alerts.detail(db, alerts.get_for_company(db, company_id, alert_id)))
    except alerts.AlertError as error:
        raise _refuse(error) from None


@router.post(COMPANY + "/{alert_id}/status")
def company_alert_status(
    company_id: uuid.UUID,
    alert_id: uuid.UUID,
    body: AlertStatusRequest,
    member: Member,
    user: CurrentUser,
    db: DbSession,
) -> AlertDetailRead:
    try:
        alert = alerts.get_for_company(db, company_id, alert_id)
        return _detail(alerts.change_status(db, user, alert, body.status))
    except alerts.AlertError as error:
        raise _refuse(error) from None


@router.post(COMPANY + "/{alert_id}/notes")
def company_alert_note(
    company_id: uuid.UUID,
    alert_id: uuid.UUID,
    body: AlertNoteRequest,
    member: Member,
    user: CurrentUser,
    db: DbSession,
) -> AlertDetailRead:
    try:
        alert = alerts.get_for_company(db, company_id, alert_id)
        return _detail(alerts.add_note(db, user, alert, body.body))
    except alerts.AlertError as error:
        raise _refuse(error) from None


# --- Admins ---------------------------------------------------------------------------------


@router.get(ADMIN)
def admin_alerts(admin: AdminUser, db: DbSession, status: StatusFilter = "OPEN") -> list[AlertRead]:
    return [AlertRead(**_read(a)) for a in alerts.list_all(db, status)]


@router.get(ADMIN + "/{alert_id}")
def admin_alert(alert_id: uuid.UUID, admin: AdminUser, db: DbSession) -> AlertDetailRead:
    try:
        return _detail(alerts.detail(db, alerts.get_any(db, alert_id)))
    except alerts.AlertError as error:
        raise _refuse(error) from None


@router.post(ADMIN + "/{alert_id}/status")
def admin_alert_status(
    alert_id: uuid.UUID, body: AlertStatusRequest, admin: AdminUser, db: DbSession
) -> AlertDetailRead:
    try:
        return _detail(alerts.change_status(db, admin, alerts.get_any(db, alert_id), body.status))
    except alerts.AlertError as error:
        raise _refuse(error) from None


@router.post(ADMIN + "/{alert_id}/notes")
def admin_alert_note(
    alert_id: uuid.UUID, body: AlertNoteRequest, admin: AdminUser, db: DbSession
) -> AlertDetailRead:
    try:
        return _detail(alerts.add_note(db, admin, alerts.get_any(db, alert_id), body.body))
    except alerts.AlertError as error:
        raise _refuse(error) from None
