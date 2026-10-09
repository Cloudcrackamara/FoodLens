"""Company catalogue routes: products and batches for a member's company."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.schemas.catalogue import (
    BatchCreateRequest,
    BatchRead,
    ProductCreateRequest,
    ProductRead,
)
from app.services import catalogue as catalogue_service
from app.services import companies as company_service

router = APIRouter(tags=["catalogue"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
NOT_APPROVED = "Products can be added after FoodLens approves your company profile"


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, company_service.CompanyNotApprovedError):
        return HTTPException(status.HTTP_409_CONFLICT, NOT_APPROVED)
    if isinstance(exc, company_service.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    if isinstance(exc, catalogue_service.DuplicateCodeError):
        return HTTPException(status.HTTP_409_CONFLICT, exc.message)
    if isinstance(exc, catalogue_service.InvalidRegistrationNumberError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Enter the registration number as printed, using letters, numbers, and - . / _",
        )
    raise exc


_HANDLED = (
    company_service.CompanyNotApprovedError,
    company_service.NotFoundError,
    catalogue_service.DuplicateCodeError,
    catalogue_service.InvalidRegistrationNumberError,
)


@router.get("/api/companies/{company_id}/products")
def list_products(company_id: uuid.UUID, member: Member, db: DbSession) -> list[ProductRead]:
    return catalogue_service.company_catalogue(db, member.company_id)


@router.post("/api/companies/{company_id}/products", status_code=status.HTTP_201_CREATED)
def add_product(
    company_id: uuid.UUID, body: ProductCreateRequest, member: Member, db: DbSession
) -> ProductRead:
    try:
        product = catalogue_service.add_product(db, member, body)
    except _HANDLED as exc:
        raise _error(exc) from None
    return ProductRead(**product.model_dump(), batches=[])


@router.post(
    "/api/companies/{company_id}/products/{product_id}/batches",
    status_code=status.HTTP_201_CREATED,
)
def add_batch(
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    body: BatchCreateRequest,
    member: Member,
    db: DbSession,
) -> BatchRead:
    try:
        batch = catalogue_service.add_batch(db, member, product_id, body)
    except _HANDLED as exc:
        raise _error(exc) from None
    return BatchRead.model_validate(batch, from_attributes=True)
