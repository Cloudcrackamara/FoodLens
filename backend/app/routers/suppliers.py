import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.db import DbSession
from app.schemas.company import SupplierRead
from app.schemas.order import SupplierDetailRead
from app.services import suppliers as supplier_service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(
    db: DbSession, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[SupplierRead]:
    """Public partner directory: approved companies with demo-reviewed locations only."""
    return supplier_service.list_suppliers(db, q)


@router.get("/{company_id}")
def supplier_page(company_id: uuid.UUID, db: DbSession) -> SupplierDetailRead:
    """Public partner page: reviewed locations, contacts, and published products."""
    detail = supplier_service.supplier_detail(db, company_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return detail
