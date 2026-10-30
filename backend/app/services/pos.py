"""POS lookups, sales, refunds and voids (D121, D122, D140, D151).

Requests reach here only after services/pos_auth.py has verified the key and signature.

- Every request names a retailer and a till. The retailer must be approved, flagged as a retailer
  and actively linked to the partner; the till must sit on a reviewed location of that retailer,
  which gives the event's area.
- Lookups write nothing.
- Sales, refunds and voids handle each pack on its own and return a per-pack result. Each is
  idempotent on (partner, transaction, unit, event type): a retry returns the same result and
  writes nothing. Status is replayed in occurred_at order, so late offline events take their
  place in the history.
- A refund (RETURNED) or void (SALE_CORRECTED) is accepted for the standing sale of the named
  retailer, however it was recorded (D140). The SOLD event always stays.
- Nothing about payment is stored beyond the opaque payment_reference.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import (
    Company,
    LifecycleEvent,
    PosPartner,
    PosPartnerRetailer,
    PosTill,
    ProductUnit,
    SupplierLocation,
)
from app.models.enums import (
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    PosLinkStatus,
    ReviewStatus,
)
from app.schemas.pos import (
    PosEventRequest,
    PosEventResponse,
    PosLookupRequest,
    PosLookupResponse,
    PosMessage,
    PosSaleRequest,
    PosUnitResult,
    PosVoidRequest,
)
from app.services import identity, lifecycle
from app.services.check import _day
from app.services.pos_auth import PosError

# Approved wording (2026-10-30). VOIDED, UNRELEASED, RECALLED, NOT_SOLD, NOT_SELLER and
# UNKNOWN_CODE reuse the merchant messages in services/lifecycle.py.
MSG_RETAILER_NOT_LINKED = (
    "This retailer is not linked to your POS account, or is not approved on FoodLens."
)
MSG_UNKNOWN_TILL = "This till is not registered for the retailer."
MSG_CARTON = "This is a carton code. Scan the individual pack."
MSG_ALREADY_SOLD = (
    "This pack is already recorded as sold. Don't complete the sale; set the pack aside and "
    "check it."
)
MSG_BEFORE_SALE = "The refund time is earlier than the sale."
MSG_DUPLICATE = "This pack appears more than once in the sale."
MSG_NEED_REASON = "Give a reason for the void."
MSG_EVENT_IN_FUTURE = "This event's time is in the future. Check the till clock."
WARN_RECALLED = "Covered by a recall from the manufacturer. Don't sell."
WARN_UNRELEASED = "Not yet released for sale by the manufacturer. Don't sell."
WARN_VOIDED = "This code was voided by the manufacturer. Don't sell."


def msg_event_too_old(days: int) -> str:
    return f"This event is older than {days} days and can't be recorded."


def msg_too_many_units(limit: int) -> str:
    return f"A request can carry at most {limit} packs."


def warn_sold(day: str) -> str:
    return f"Already recorded as sold on {day}. Don't sell this pack until it's checked."


# Merchant refusals mapped to POS error codes.
_PROBLEM_CODES = {
    lifecycle.MSG_VOIDED: "VOIDED",
    lifecycle.MSG_UNRELEASED: "UNRELEASED",
    lifecycle.MSG_RECALLED: "RECALLED",
    lifecycle.MSG_SOLD: "ALREADY_SOLD",
    lifecycle.MSG_NOT_SOLD: "NOT_SOLD",
    lifecycle.MSG_NOT_SELLER: "NOT_SELLER",
}
_MESSAGES = {"ALREADY_SOLD": MSG_ALREADY_SOLD}


@dataclass
class Till:
    retailer: Company
    till: PosTill
    area_id: uuid.UUID


def resolve_till(db: Session, partner: PosPartner, retailer_id: uuid.UUID, till_ref: str) -> Till:
    retailer = db.get(Company, retailer_id)
    link = db.exec(
        select(PosPartnerRetailer).where(
            PosPartnerRetailer.partner_id == partner.partner_id,
            PosPartnerRetailer.retailer_company_id == retailer_id,
            PosPartnerRetailer.status == PosLinkStatus.ACTIVE,
        )
    ).first()
    if (
        retailer is None
        or retailer.review_status != CompanyReviewStatus.APPROVED
        or not retailer.is_retailer
        or link is None
    ):
        raise PosError("RETAILER_NOT_LINKED", MSG_RETAILER_NOT_LINKED, 403)
    till = db.exec(
        select(PosTill).where(
            PosTill.partner_id == partner.partner_id,
            PosTill.retailer_company_id == retailer_id,
            PosTill.till_ref == till_ref,
        )
    ).first()
    location = db.get(SupplierLocation, till.location_id) if till else None
    if (
        till is None
        or location is None
        or location.company_id != retailer_id
        or location.review_status != ReviewStatus.APPROVED
        or location.area_id is None
    ):
        raise PosError("UNKNOWN_TILL", MSG_UNKNOWN_TILL, 422)
    return Till(retailer, till, location.area_id)


def _last4(code: str) -> str:
    return identity.normalise(code)[-4:]


def _unit_warning(unit: ProductUnit, recalled: bool) -> PosMessage | None:
    status = unit.lifecycle_status
    if status == LifecycleStatus.VOIDED:
        return PosMessage(code="VOIDED", message=WARN_VOIDED)
    if status == LifecycleStatus.ISSUED:
        return PosMessage(code="UNRELEASED", message=WARN_UNRELEASED)
    if recalled or status == LifecycleStatus.RECALLED:
        return PosMessage(code="RECALLED", message=WARN_RECALLED)
    if status == LifecycleStatus.SOLD and unit.last_sold_at is not None:
        return PosMessage(code="ALREADY_SOLD", message=warn_sold(_day(unit.last_sold_at)))
    return None


def lookup(db: Session, partner: PosPartner, body: PosLookupRequest) -> PosLookupResponse:
    """Read-only: never adds, changes or locks a row."""
    resolve_till(db, partner, body.retailer_id, body.till_id)
    try:
        subject = lifecycle.find_subject(db, body.code)
    except lifecycle.MerchantError:
        raise PosError("UNKNOWN_CODE", lifecycle.MSG_UNKNOWN_CODE, 404) from None
    if subject.carton is not None:
        status = subject.carton.lifecycle_status
        warning: PosMessage | None = PosMessage(code="CARTON_CODE", message=MSG_CARTON)
    else:
        unit = subject.units[0]
        status = unit.lifecycle_status
        warning = _unit_warning(unit, subject.recalled)
    return PosLookupResponse(
        subject=subject.kind,
        code_last4=_last4(body.code),
        product_name=subject.product.name,
        brand=subject.product.brand,
        size=subject.product.size,
        gtin=subject.product.gtin,
        batch_number=subject.batch.batch_number,
        expiry_date=subject.batch.expiry_date,
        status=status,
        warning=warning,
    )


def _check_request(settings: Settings, body: PosEventRequest, now: datetime) -> None:
    if len(body.units) > settings.pos_max_units_per_request:
        raise PosError(
            "TOO_MANY_UNITS", msg_too_many_units(settings.pos_max_units_per_request), 422
        )
    if body.occurred_at < now - timedelta(days=settings.pos_max_event_age_days):
        raise PosError("EVENT_TOO_OLD", msg_event_too_old(settings.pos_max_event_age_days), 422)
    if body.occurred_at > now + timedelta(seconds=settings.pos_max_future_seconds):
        raise PosError("EVENT_IN_FUTURE", MSG_EVENT_IN_FUTURE, 422)


def record(
    db: Session,
    settings: Settings,
    partner: PosPartner,
    body: PosEventRequest,
    event_type: LifecycleEventType,
    now: datetime,
) -> PosEventResponse:
    """Record SOLD, RETURNED or SALE_CORRECTED for each listed pack, in one transaction."""
    reason = None
    if event_type == LifecycleEventType.SALE_CORRECTED:
        assert isinstance(body, PosVoidRequest)
        reason = (body.reason or "").strip() or None
        if reason is None:
            raise PosError("NEED_REASON", MSG_NEED_REASON, 422)
    _check_request(settings, body, now)
    till = resolve_till(db, partner, body.retailer_id, body.till_id)
    payment_reference = body.payment_reference if isinstance(body, PosSaleRequest) else None

    group_id = uuid.uuid4()
    seen: set[str] = set()
    results = []
    for index, code in enumerate(body.units):
        normalised = identity.normalise(code)
        error: tuple[str, str] | None
        if normalised in seen:
            error = "DUPLICATE_IN_REQUEST", MSG_DUPLICATE
        else:
            seen.add(normalised)
            error = _record_code(
                db,
                partner,
                till,
                body,
                event_type,
                code,
                now=now,
                group_id=group_id,
                payment_reference=payment_reference,
                reason=reason,
            )
        results.append(
            PosUnitResult(
                index=index,
                code_last4=normalised[-4:],
                result="ERROR" if error else "RECORDED",
                error=PosMessage(code=error[0], message=error[1]) if error else None,
            )
        )
    db.commit()
    recorded = sum(1 for r in results if r.result == "RECORDED")
    return PosEventResponse(
        transaction_id=body.transaction_id,
        event_type=event_type,
        recorded=recorded,
        errors=len(results) - recorded,
        units=results,
    )


def _record_code(
    db: Session,
    partner: PosPartner,
    till: Till,
    body: PosEventRequest,
    event_type: LifecycleEventType,
    code: str,
    *,
    now: datetime,
    group_id: uuid.UUID,
    payment_reference: str | None,
    reason: str | None,
) -> tuple[str, str] | None:
    """Record one pack, or return (error code, message). An existing event with the same
    idempotency key counts as recorded and writes nothing."""
    try:
        subject = lifecycle.find_subject(db, code)
    except lifecycle.MerchantError:
        return "UNKNOWN_CODE", lifecycle.MSG_UNKNOWN_CODE
    if subject.carton is not None:
        return "CARTON_CODE", MSG_CARTON
    unit = db.exec(
        select(ProductUnit)
        .where(ProductUnit.unit_id == subject.units[0].unit_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    already = db.exec(
        select(LifecycleEvent.event_id).where(
            LifecycleEvent.pos_partner_id == partner.partner_id,
            LifecycleEvent.transaction_ref == body.transaction_id,
            LifecycleEvent.unit_id == unit.unit_id,
            LifecycleEvent.event_type == event_type,
        )
    ).first()
    if already is not None:
        return None

    retailer_id = till.retailer.company_id
    problem = lifecycle.unit_problem(unit, event_type, retailer_id, subject.recalled)
    if problem is not None:
        message = problem[0]
        code = _PROBLEM_CODES.get(message, "REFUSED")
        return code, _MESSAGES.get(code, message)

    sale_id = None
    if event_type != LifecycleEventType.SOLD:
        sale_id = lifecycle.standing_sale(db, unit.unit_id)
        sale = db.get(LifecycleEvent, sale_id) if sale_id else None
        if sale is not None and body.occurred_at < sale.occurred_at:
            return "BEFORE_SALE", MSG_BEFORE_SALE

    statement = insert(LifecycleEvent).values(
        event_id=uuid.uuid4(),
        unit_id=unit.unit_id,
        group_id=group_id,
        event_type=event_type,
        source=EventSource.POS_API,
        retailer_company_id=retailer_id,
        pos_partner_id=partner.partner_id,
        till_ref=till.till.till_ref,
        area_id=till.area_id,
        occurred_at=body.occurred_at,
        recorded_at=now,
        transaction_ref=body.transaction_id,
        payment_reference=payment_reference,
        reason=reason,
        received_without_transfer=(
            event_type == LifecycleEventType.SOLD
            and lifecycle.without_transfer(unit, event_type, retailer_id)
        ),
        outside_allocation=False,
        returns_event_id=sale_id if event_type == LifecycleEventType.RETURNED else None,
        corrects_event_id=sale_id if event_type == LifecycleEventType.SALE_CORRECTED else None,
    )
    db.execute(
        statement.on_conflict_do_nothing(
            index_elements=["pos_partner_id", "transaction_ref", "unit_id", "event_type"],
            index_where=text("pos_partner_id IS NOT NULL"),
        )
    )
    lifecycle.replay_unit(db, unit)
    return None
