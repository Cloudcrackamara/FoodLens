"""Company-side routes: registration and the member's own company and locations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, require_company_member
from app.core.db import DbSession
from app.models import Company, CompanyMember, SupplierLocation
from app.schemas.company import (
    CompanyRead,
    CompanyRegisterRequest,
    LocationCreateRequest,
    LocationRead,
)
from app.services import companies as company_service

router = APIRouter(prefix="/api/companies", tags=["companies"])

Member = Annotated[CompanyMember, Depends(require_company_member())]


def location_read(location: SupplierLocation) -> LocationRead:
    return LocationRead.model_validate(location, from_attributes=True)


def company_read(db: DbSession, company: Company) -> CompanyRead:
    return CompanyRead.model_validate(
        {
            **company.model_dump(),
            "locations": [
                location_read(loc)
                for loc in company_service.company_locations(db, company.company_id)
            ],
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def register_company(body: CompanyRegisterRequest, user: CurrentUser, db: DbSession) -> CompanyRead:
    try:
        company = company_service.register_company(db, user, body)
    except company_service.AlreadyInCompanyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Your account already belongs to a company"
        ) from None
    except company_service.AdminCannotRegisterCompanyError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Admin accounts cannot register companies"
        ) from None
    return company_read(db, company)


@router.get("/{company_id}")
def get_my_company(company_id: uuid.UUID, member: Member, db: DbSession) -> CompanyRead:
    return company_read(db, company_service.get_company(db, member.company_id))


@router.post("/{company_id}/locations", status_code=status.HTTP_201_CREATED)
def add_location(
    company_id: uuid.UUID, body: LocationCreateRequest, member: Member, db: DbSession
) -> LocationRead:
    try:
        location = company_service.add_location(db, member, body)
    except company_service.CompanyNotApprovedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Locations can be added after FoodLens approves your company profile",
        ) from None
    except company_service.InvalidContactError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The contact must be an active member of your company",
        ) from None
    return location_read(location)
