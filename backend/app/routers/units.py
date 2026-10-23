"""Unit codes, labels, release, void and allocations. Thin: rules live in services/units.py and
services/allocations.py.

The path company must be the signed-in user's company (require_company_member). Generating codes
and voiding are owner only (D106).
"""

import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import select

from app.core.auth import require_company_member
from app.core.db import DbSession
from app.models import Area, CompanyMember
from app.models.enums import MemberRole
from app.schemas.units import (
    AllocationCreateRequest,
    AllocationRead,
    AreaRead,
    BatchSummaryRead,
    DestinationRead,
    GenerateRequest,
    ReleaseRequest,
    UnitsChanged,
    VoidRequest,
)
from app.services import allocations as allocation_service
from app.services import companies as company_service
from app.services import units as unit_service
from app.services.catalogue import NotManufacturerError
from app.services.identity import IdentityGenerationError

router = APIRouter(tags=["units"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
Owner = Annotated[CompanyMember, Depends(require_company_member(MemberRole.OWNER))]
BATCH = "/api/companies/{company_id}/batches/{batch_id}"
WARNING_HEADER = "X-FoodLens-Label-Warning"


def _run[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except NotManufacturerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only manufacturer companies manage pack codes"
        ) from None
    except company_service.CompanyNotApprovedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Pack codes can be managed after FoodLens approves your company profile",
        ) from None
    except company_service.NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found") from None
    except unit_service.UnitRuleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from None
    except unit_service.UnitConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    except IdentityGenerationError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Could not create codes. Try again."
        ) from None


@router.post(f"{BATCH}/units", response_class=Response)
def generate_units(
    company_id: uuid.UUID,
    batch_id: uuid.UUID,
    body: GenerateRequest,
    owner: Owner,
    db: DbSession,
    request: Request,
) -> Response:
    """One-time label file: a zip with the label PDF and printer CSVs. FoodLens keeps only the
    hashes, so this file cannot be downloaded again."""
    result = _run(
        lambda: unit_service.generate(
            db,
            owner,
            batch_id,
            quantity=body.quantity,
            units_per_carton=body.units_per_carton,
            qr_size_mm=body.qr_size_mm,
            base_url=request.app.state.public_base_url,
        )
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "Cache-Control": "no-store",
        "X-FoodLens-Units": str(result.units),
        "X-FoodLens-Cartons": str(result.cartons),
    }
    if result.warning:
        headers[WARNING_HEADER] = result.warning
    return Response(result.zip_bytes, media_type="application/zip", headers=headers)


@router.get(f"{BATCH}/units")
def batch_units(
    company_id: uuid.UUID, batch_id: uuid.UUID, member: Member, db: DbSession
) -> BatchSummaryRead:
    found = _run(lambda: unit_service.summary(db, member, batch_id))
    return BatchSummaryRead.model_validate(asdict(found))


@router.post(f"{BATCH}/release")
def release_units(
    company_id: uuid.UUID,
    batch_id: uuid.UUID,
    body: ReleaseRequest,
    member: Member,
    db: DbSession,
) -> UnitsChanged:
    count = _run(lambda: unit_service.release(db, member, batch_id, body.carton_ref or None))
    return UnitsChanged(units=count)


@router.post(f"{BATCH}/void")
def void_units(
    company_id: uuid.UUID, batch_id: uuid.UUID, body: VoidRequest, owner: Owner, db: DbSession
) -> UnitsChanged:
    count = _run(
        lambda: unit_service.void(
            db,
            owner,
            batch_id,
            reason=body.reason,
            whole_batch=body.whole_batch,
            carton_refs=body.carton_refs,
            tokens=body.codes,
        )
    )
    return UnitsChanged(units=count)


# --- Allocations ------------------------------------------------------------------------------


def _allocation_read(view: allocation_service.AllocationView) -> AllocationRead:
    company = view.company
    return AllocationRead(
        allocation_id=view.allocation.allocation_id,
        destination_area=AreaRead.model_validate(view.area, from_attributes=True),
        destination_company=(
            DestinationRead.model_validate(company, from_attributes=True) if company else None
        ),
        quantity=view.allocation.quantity,
        planned_date=view.allocation.planned_date,
        carton_refs=view.carton_refs,
        units_listed=view.units_listed,
        created_at=view.allocation.created_at,
    )


@router.get(f"{BATCH}/allocations")
def list_allocations(
    company_id: uuid.UUID, batch_id: uuid.UUID, member: Member, db: DbSession
) -> list[AllocationRead]:
    views = _run(lambda: allocation_service.list_for_batch(db, member, batch_id))
    return [_allocation_read(v) for v in views]


@router.post(f"{BATCH}/allocations", status_code=status.HTTP_201_CREATED)
def create_allocation(
    company_id: uuid.UUID,
    batch_id: uuid.UUID,
    body: AllocationCreateRequest,
    member: Member,
    db: DbSession,
) -> AllocationRead:
    data = allocation_service.AllocationInput(**body.model_dump())
    allocation = _run(lambda: allocation_service.create(db, member, batch_id, data))
    views = allocation_service.list_for_batch(db, member, batch_id)
    return _allocation_read(
        next(v for v in views if v.allocation.allocation_id == allocation.allocation_id)
    )


@router.delete(f"{BATCH}/allocations/{{allocation_id}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    company_id: uuid.UUID,
    batch_id: uuid.UUID,
    allocation_id: uuid.UUID,
    member: Member,
    db: DbSession,
) -> None:
    _run(lambda: allocation_service.delete(db, member, batch_id, allocation_id))


@router.get("/api/companies/{company_id}/allocation-destinations")
def allocation_destinations(
    company_id: uuid.UUID, member: Member, db: DbSession
) -> list[DestinationRead]:
    return [
        DestinationRead.model_validate(c, from_attributes=True)
        for c in allocation_service.destinations(db)
    ]


@router.get("/api/areas")
def list_areas(db: DbSession) -> list[AreaRead]:
    """Seeded reference areas (D118). Read-only."""
    rows = db.exec(select(Area).order_by(Area.city)).all()
    return [AreaRead.model_validate(a, from_attributes=True) for a in rows]
