from typing import Annotated

from fastapi import APIRouter, Query

from app.core.db import DbSession
from app.schemas.company import SupplierRead
from app.services import suppliers as supplier_service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(
    db: DbSession, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[SupplierRead]:
    """Public directory: approved companies with demo-reviewed locations only."""
    return supplier_service.list_suppliers(db, q)
