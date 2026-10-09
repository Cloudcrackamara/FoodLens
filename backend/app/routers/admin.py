"""Admin review of companies and supplier locations. Every route requires an admin."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.auth import AdminUser
from app.core.db import DbSession
from app.models import AppUser, Company, SupplierLocation
from app.models.enums import CompanyReviewStatus, ReviewStatus
from app.routers.companies import location_read
from app.schemas.catalogue import AdminCredentialRead, CredentialDecisionRequest
from app.schemas.company import (
    AdminCompanyRead,
    AdminLocationRead,
    CompanyDecisionRequest,
    LocationDecisionRequest,
)
from app.services import catalogue as catalogue_service
from app.services import companies as company_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

CONFLICT_OF_INTEREST = "Admins cannot review a company they belong to"


def _admin_company_read(db: DbSession, company: Company) -> AdminCompanyRead:
    owner = company_service.company_owner(db, company.company_id)
    reviewer = db.get(AppUser, company.reviewed_by_user_id) if company.reviewed_by_user_id else None
    return AdminCompanyRead.model_validate(
        {
            **company.model_dump(),
            "locations": [
                location_read(loc)
                for loc in company_service.company_locations(db, company.company_id)
            ],
            "owner_display_name": owner.display_name if owner else None,
            "owner_email": owner.email if owner else None,
            "reviewed_by_display_name": reviewer.display_name if reviewer else None,
        }
    )


def _admin_location_read(location: SupplierLocation, company: Company) -> AdminLocationRead:
    return AdminLocationRead.model_validate(
        {
            **location.model_dump(),
            "company_display_name": company.display_name,
            "company_review_status": company.review_status,
        }
    )


def _decision_error(exc: Exception) -> HTTPException:
    if isinstance(exc, company_service.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, company_service.ConflictOfInterestError):
        return HTTPException(status.HTTP_403_FORBIDDEN, CONFLICT_OF_INTEREST)
    if isinstance(exc, company_service.InvalidTransitionError):
        return HTTPException(status.HTTP_409_CONFLICT, exc.message)
    raise exc


@router.get("/companies")
def list_companies(
    admin: AdminUser, db: DbSession, review_status: CompanyReviewStatus | None = None
) -> list[AdminCompanyRead]:
    return [
        _admin_company_read(db, company)
        for company in company_service.list_companies(db, review_status)
    ]


@router.post("/companies/{company_id}/decision")
def decide_company(
    company_id: uuid.UUID, body: CompanyDecisionRequest, admin: AdminUser, db: DbSession
) -> AdminCompanyRead:
    try:
        company = company_service.decide_company(db, admin, company_id, body.decision, body.note)
    except (
        company_service.NotFoundError,
        company_service.ConflictOfInterestError,
        company_service.InvalidTransitionError,
    ) as exc:
        raise _decision_error(exc) from None
    return _admin_company_read(db, company)


@router.get("/locations")
def list_locations(
    admin: AdminUser, db: DbSession, review_status: ReviewStatus | None = None
) -> list[AdminLocationRead]:
    return [
        _admin_location_read(location, company)
        for location, company in company_service.list_locations(db, review_status)
    ]


@router.post("/locations/{location_id}/decision")
def decide_location(
    location_id: uuid.UUID, body: LocationDecisionRequest, admin: AdminUser, db: DbSession
) -> AdminLocationRead:
    try:
        location = company_service.decide_location(db, admin, location_id, body.decision, body.note)
    except (
        company_service.NotFoundError,
        company_service.ConflictOfInterestError,
        company_service.InvalidTransitionError,
    ) as exc:
        raise _decision_error(exc) from None
    company = company_service.get_company(db, location.company_id)
    return _admin_location_read(location, company)


@router.get("/credentials")
def list_credentials(
    admin: AdminUser, db: DbSession, review_status: ReviewStatus | None = None
) -> list[AdminCredentialRead]:
    return catalogue_service.list_credentials(db, review_status)


@router.post("/credentials/{credential_id}/decision")
def decide_credential(
    credential_id: uuid.UUID, body: CredentialDecisionRequest, admin: AdminUser, db: DbSession
) -> AdminCredentialRead:
    """Approve a company's credential claim (it then appears in lookups) or reject it."""
    try:
        return catalogue_service.decide_credential(
            db, admin, credential_id, body.decision, body.note
        )
    except (
        company_service.NotFoundError,
        company_service.ConflictOfInterestError,
        company_service.InvalidTransitionError,
    ) as exc:
        raise _decision_error(exc) from None
