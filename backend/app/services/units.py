"""Unit and carton identities for a batch: generation, release and void (D110, D138, D139).

Rules:
- Only the owner of an approved manufacturer generates codes and voids units (D106). Owners and
  staff release. Pending companies get 409; other companies and non-manufacturers get 403/404.
- One generation is one transaction: cartons, units and ISSUED events. Raw tokens exist only in
  the returned label file; the database holds their hashes.
- Release moves ISSUED units (per batch or per carton) to RELEASED.
- Void is allowed only before release and needs a reason. Released units are recalled instead.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, insert
from sqlmodel import Session, select

from app.models import Carton, Company, CompanyMember, Product, ProductBatch, ProductUnit
from app.models.enums import (
    CompanyReviewStatus,
    LifecycleEventType,
    LifecycleStatus,
    ReviewStatus,
)
from app.services import audit, identity, labels, lifecycle
from app.services.catalogue import NotManufacturerError
from app.services.companies import CompanyNotApprovedError, NotFoundError

MAX_UNITS_PER_REQUEST = 2000


class UnitRuleError(Exception):
    """The request breaks a unit rule (422)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnitConflictError(Exception):
    """The units are in the wrong state for this action (409)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class OwnBatch:
    company: Company
    product: Product
    batch: ProductBatch


def own_batch(db: Session, member: CompanyMember, batch_id: uuid.UUID) -> OwnBatch:
    """The member's approved manufacturer and one of its published batches."""
    company = db.get(Company, member.company_id)
    if company is None:
        raise NotFoundError
    if not company.is_manufacturer:
        raise NotManufacturerError
    if company.review_status != CompanyReviewStatus.APPROVED:
        raise CompanyNotApprovedError
    batch = db.get(ProductBatch, batch_id)
    product = db.get(Product, batch.product_id) if batch else None
    if batch is None or product is None or product.company_id != company.company_id:
        raise NotFoundError  # another company's batch looks the same as a missing one
    if batch.review_status != ReviewStatus.APPROVED:
        raise UnitConflictError("Codes can be generated only for a published batch")
    return OwnBatch(company, product, batch)


# --- Generate ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedLabels:
    zip_bytes: bytes
    filename: str
    units: int
    cartons: int
    warning: str | None


def _next_carton_number(db: Session, batch_id: uuid.UUID) -> int:
    # Cartons are never deleted, so the count gives the next free C-number.
    return db.exec(select(func.count()).where(Carton.batch_id == batch_id)).one() + 1


def generate(
    db: Session,
    member: CompanyMember,
    batch_id: uuid.UUID,
    *,
    quantity: int,
    units_per_carton: int | None,
    qr_size_mm: float,
    base_url: str,
) -> GeneratedLabels:
    owned = own_batch(db, member, batch_id)
    if not 1 <= quantity <= MAX_UNITS_PER_REQUEST:
        raise UnitRuleError(f"Generate between 1 and {MAX_UNITS_PER_REQUEST} packs at a time")
    if units_per_carton is not None and not 1 <= units_per_carton <= quantity:
        raise UnitRuleError("Packs per carton must be between 1 and the number of packs")

    carton_total = identity.carton_count(quantity, units_per_carton)
    issued = identity.new_identities(db, quantity + carton_total)
    carton_ids = [uuid.uuid4() for _ in range(carton_total)]
    unit_ids = [uuid.uuid4() for _ in range(quantity)]
    first_number = _next_carton_number(db, batch_id)
    carton_refs = [f"C{first_number + i:03d}" for i in range(carton_total)]

    carton_identities, unit_identities = issued[:carton_total], issued[carton_total:]
    holder = {"current_holder_company_id": owned.company.company_id}
    if carton_ids:
        db.execute(
            insert(Carton),
            [
                {
                    "carton_id": carton_id,
                    "batch_id": batch_id,
                    "manufacturer_id": owned.company.company_id,
                    "carton_ref": ref,
                    "qr_token_hash": ident.hash,
                    **holder,
                }
                for carton_id, ref, ident in zip(
                    carton_ids, carton_refs, carton_identities, strict=True
                )
            ],
        )

    def carton_index(n: int) -> int | None:
        return n // units_per_carton if units_per_carton else None

    db.execute(
        insert(ProductUnit),
        [
            {
                "unit_id": unit_id,
                "batch_id": batch_id,
                "product_id": owned.product.product_id,
                "manufacturer_id": owned.company.company_id,
                "parent_carton_id": (
                    carton_ids[carton_index(n)] if carton_index(n) is not None else None
                ),
                "qr_token_hash": ident.hash,
                **holder,
            }
            for n, (unit_id, ident) in enumerate(zip(unit_ids, unit_identities, strict=True))
        ],
    )
    lifecycle.record_manufacturer_event(
        db, member, LifecycleEventType.ISSUED, unit_ids=unit_ids, carton_ids=carton_ids
    )
    lifecycle.refresh_batch_release(db, owned.batch)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product_batch",
        entity_id=batch_id,
        action="codes_generated",
        new_values={
            "units": quantity,
            "cartons": carton_total,
            "carton_refs": [carton_refs[0], carton_refs[-1]] if carton_refs else [],
            "qr_size_mm": qr_size_mm,
        },
    )

    label_units = [
        labels.Label(
            ident.token,
            carton_refs[carton_index(n)] if carton_index(n) is not None else None,
        )
        for n, ident in enumerate(unit_identities)
    ]
    label_cartons = [
        labels.Label(ident.token, ref, is_carton=True)
        for ident, ref in zip(carton_identities, carton_refs, strict=True)
    ]
    # Build the file before committing: if it fails, no codes exist that nobody can print.
    zip_bytes = labels.build_zip(
        product_name=owned.product.name,
        batch_number=owned.batch.batch_number,
        base_url=base_url,
        qr_size_mm=qr_size_mm,
        cartons=label_cartons,
        units=label_units,
    )
    db.commit()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_batch = "".join(c if c.isalnum() or c in "-_" else "-" for c in owned.batch.batch_number)
    return GeneratedLabels(
        zip_bytes=zip_bytes,
        filename=f"foodlens-labels-{safe_batch}-{stamp}.zip",
        units=quantity,
        cartons=carton_total,
        warning=labels.size_warning(qr_size_mm),
    )


# --- Release ----------------------------------------------------------------------------------


def _carton_by_ref(db: Session, batch_id: uuid.UUID, carton_ref: str) -> Carton:
    carton = db.exec(
        select(Carton).where(
            Carton.batch_id == batch_id, Carton.carton_ref == carton_ref.strip().upper()
        )
    ).first()
    if carton is None:
        raise UnitRuleError(f"Carton {carton_ref} is not in this batch")
    return carton


def release(
    db: Session, member: CompanyMember, batch_id: uuid.UUID, carton_ref: str | None = None
) -> int:
    """Release the batch's ISSUED units, or those of one carton. Returns how many."""
    owned = own_batch(db, member, batch_id)
    units = select(ProductUnit.unit_id).where(
        ProductUnit.batch_id == batch_id, ProductUnit.lifecycle_status == LifecycleStatus.ISSUED
    )
    cartons = select(Carton.carton_id).where(
        Carton.batch_id == batch_id, Carton.lifecycle_status == LifecycleStatus.ISSUED
    )
    if carton_ref:
        carton = _carton_by_ref(db, batch_id, carton_ref)
        units = units.where(ProductUnit.parent_carton_id == carton.carton_id)
        cartons = cartons.where(Carton.carton_id == carton.carton_id)
    unit_ids = list(db.exec(units).all())
    carton_ids = list(db.exec(cartons).all())
    if not unit_ids:
        raise UnitConflictError("There are no unreleased packs to release here")

    lifecycle.record_manufacturer_event(
        db, member, LifecycleEventType.RELEASED, unit_ids=unit_ids, carton_ids=carton_ids
    )
    lifecycle.refresh_batch_release(db, owned.batch)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product_batch",
        entity_id=batch_id,
        action="units_released",
        new_values={"units": len(unit_ids), "carton_ref": carton_ref},
    )
    db.commit()
    return len(unit_ids)


# --- Void -------------------------------------------------------------------------------------


def void(
    db: Session,
    member: CompanyMember,
    batch_id: uuid.UUID,
    *,
    reason: str,
    whole_batch: bool = False,
    carton_refs: list[str] | None = None,
    tokens: list[str] | None = None,
) -> int:
    """Void unreleased units (and cartons) with a reason. Returns how many units. Any released or
    already voided target refuses the whole request (409)."""
    owned = own_batch(db, member, batch_id)
    if not reason.strip():
        raise UnitRuleError("Give a reason for voiding")
    carton_refs = carton_refs or []
    tokens = tokens or []
    if not whole_batch and not carton_refs and not tokens:
        raise UnitRuleError("Choose the whole batch, cartons, or codes to void")

    units: dict[uuid.UUID, ProductUnit] = {}
    cartons: dict[uuid.UUID, Carton] = {}
    if whole_batch:
        for unit in db.exec(
            select(ProductUnit).where(
                ProductUnit.batch_id == batch_id,
                ProductUnit.lifecycle_status == LifecycleStatus.ISSUED,
            )
        ):
            units[unit.unit_id] = unit
        for carton in db.exec(
            select(Carton).where(
                Carton.batch_id == batch_id, Carton.lifecycle_status == LifecycleStatus.ISSUED
            )
        ):
            cartons[carton.carton_id] = carton
    for ref in carton_refs:
        carton = _carton_by_ref(db, batch_id, ref)
        cartons[carton.carton_id] = carton
        for unit in db.exec(
            select(ProductUnit).where(ProductUnit.parent_carton_id == carton.carton_id)
        ):
            if unit.lifecycle_status != LifecycleStatus.VOIDED:
                units[unit.unit_id] = unit
    for token in tokens:
        digest = identity.token_hash(token)
        unit = db.exec(
            select(ProductUnit).where(
                ProductUnit.qr_token_hash == digest, ProductUnit.batch_id == batch_id
            )
        ).first()
        if unit is None:
            raise UnitRuleError(
                f"Code ending {identity.normalise(token)[-4:]} is not in this batch"
            )
        units[unit.unit_id] = unit

    if not units:
        raise UnitConflictError("There are no unreleased packs to void here")
    for row in [*units.values(), *cartons.values()]:
        if row.lifecycle_status == LifecycleStatus.VOIDED:
            raise UnitConflictError("Some of these packs are already voided")
        if row.lifecycle_status != LifecycleStatus.ISSUED:
            raise UnitConflictError(
                "Released packs cannot be voided. Use a recall for released stock."
            )

    lifecycle.record_manufacturer_event(
        db,
        member,
        LifecycleEventType.VOIDED,
        unit_ids=list(units),
        carton_ids=list(cartons),
        reason=reason.strip(),
    )
    lifecycle.refresh_batch_release(db, owned.batch)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product_batch",
        entity_id=batch_id,
        action="units_voided",
        new_values={
            "units": len(units),
            "carton_refs": sorted(c.carton_ref for c in cartons.values()),
            "reason": reason.strip(),
        },
    )
    db.commit()
    return len(units)


# --- Summary ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CartonSummary:
    carton_ref: str
    status: LifecycleStatus
    units: dict[str, int]


@dataclass(frozen=True)
class BatchSummary:
    product_name: str
    batch_number: str
    expiry_date: date | None
    released_at: datetime | None
    units: dict[str, int]
    loose_units: dict[str, int]
    cartons: list[CartonSummary]


def summary(db: Session, member: CompanyMember, batch_id: uuid.UUID) -> BatchSummary:
    """Counts by status, per carton and for loose units. Never any token or hash."""
    owned = own_batch(db, member, batch_id)
    rows = db.exec(
        select(ProductUnit.parent_carton_id, ProductUnit.lifecycle_status, func.count())
        .where(ProductUnit.batch_id == batch_id)
        .group_by(ProductUnit.parent_carton_id, ProductUnit.lifecycle_status)
    ).all()
    totals: dict[str, int] = {}
    per_carton: dict[uuid.UUID | None, dict[str, int]] = {}
    for carton_id, status, count in rows:
        totals[status] = totals.get(status, 0) + count
        per_carton.setdefault(carton_id, {})[status] = count
    cartons = db.exec(
        select(Carton).where(Carton.batch_id == batch_id).order_by(Carton.carton_ref)
    ).all()
    return BatchSummary(
        product_name=owned.product.name,
        batch_number=owned.batch.batch_number,
        expiry_date=owned.batch.expiry_date,
        released_at=owned.batch.released_at,
        units=totals,
        loose_units=per_carton.get(None, {}),
        cartons=[
            CartonSummary(c.carton_ref, c.lifecycle_status, per_carton.get(c.carton_id, {}))
            for c in cartons
        ],
    )
