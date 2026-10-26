"""Consumer check of a pack or carton QR code (D115, D116, D138, D141, D143).

One main result per check, the first that applies:
  1. INVALID_IDENTITY          unknown code, voided, or from a manufacturer that is not approved
  2. SUSPICIOUS_ACTIVITY       an OPEN/INVESTIGATING MEDIUM or HIGH alert on the unit (rule 9
                               excluded), or one resolved as a suspected copy
  3. BATCH_OR_PRODUCT_WARNING  an active recall
  4. RECOGNISED_JUST_SOLD      sold at or after now - JUST_SOLD_WINDOW_HOURS (inclusive)
     RECOGNISED_PREVIOUSLY_SOLD an older sale
     RECOGNISED_NOT_SOLD       no standing sale (a valid return clears it, D140)
A recognised carton QR gives CARTON_CODE ("check the individual pack"), or the recall warning,
and its scan is always logged as CARTON_CODE (D148).

A check only appends one scan_event row. It never changes lifecycle_status, the sale columns or
any other unit data (CLAUDE.md rule 4). Risk rules run here from Phase 6; until then
SUSPICIOUS_ACTIVITY comes only from existing alerts.

Wording: recorded facts and possible patterns are separate lists. FoodLens never says the item
is original, genuine, authentic, safe or fake, and never mentions regulator verification.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    Area,
    Carton,
    Company,
    LifecycleEvent,
    Product,
    ProductAnnouncement,
    ProductBatch,
    ProductUnit,
    RiskAlert,
    ScanEvent,
)
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    AnnouncementKind,
    AnnouncementStatus,
    CheckResult,
    CompanyReviewStatus,
    EventSource,
    IdentifierType,
    LifecycleEventType,
    LifecycleStatus,
    RiskRule,
)
from app.schemas.check import (
    CheckBatch,
    CheckNotice,
    CheckProduct,
    CheckResponse,
    CheckSale,
)
from app.services import identity

# Nigeria has no daylight saving: West Africa Time is UTC+1 all year.
WAT = timezone(timedelta(hours=1), "WAT")
MAX_NOTICES = 5

TITLES = {
    CheckResult.INVALID_IDENTITY: "Code not recognised",
    CheckResult.SUSPICIOUS_ACTIVITY: "This code may have been copied",
    CheckResult.BATCH_OR_PRODUCT_WARNING: "Recall posted for this product",
    CheckResult.RECOGNISED_JUST_SOLD: "Just sold",
    CheckResult.RECOGNISED_PREVIOUSLY_SOLD: "Already recorded as sold",
    CheckResult.RECOGNISED_NOT_SOLD: "In circulation, not yet sold",
}

INVALID_SCANNED = "FoodLens has no active record of this code from an approved manufacturer."
INVALID_TYPED = "Check you typed it correctly, or scan the QR."
INVALID_TYPED_TITLE = "We couldn't find that code"
ASK_SELLER = (
    "Ask the seller about this pack, or choose another one. You can report a concern below."
)
NOT_SOLD_TIP = "Scan again after you pay. It should show this item as just sold by the shop."
CARTON_TITLE = "This is a carton code"
CARTON_MESSAGE = "This is a carton code; check the individual pack."
SUSPICIOUS_MESSAGE = (
    "FoodLens has seen activity for this code that often happens when a QR code is copied. "
    "This is a warning, not proof about the pack in your hand."
)
PREVIOUSLY_SOLD_ADVICE = (
    "If you are buying it now, ask the seller about it or choose another pack. "
    "If something seems wrong, report a concern below."
)

# Consumer wording for each rule that can make a result suspicious (D143). Rule 4 has no unit,
# and rules 8 and 9 never reach a consumer as a pattern (voided codes are INVALID_IDENTITY).
PATTERNS = {
    RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE: (
        "Checked in a different place some time after a recorded sale."
    ),
    RiskRule.R2_IMPOSSIBLE_TRAVEL: "Checked in places too far apart for the time between checks.",
    RiskRule.R3_SCAN_VOLUME: "Checked many more times than usual within 24 hours.",
    RiskRule.R5_POS_UNAVAILABLE_UNIT: (
        "A shop till tried to sell this code after it was already sold, recalled or not released."
    ),
    RiskRule.R6_UNRELEASED_SCANNED: (
        "Checked before the manufacturer recorded it as released for sale."
    ),
    RiskRule.R7_CUSTODY_CONFLICT: (
        "Two companies recorded receiving or selling this code with no transfer between them."
    ),
}
SUSPECTED_COPY_REVIEW = (
    "The manufacturer reviewed activity for this code and noted a suspected copy."
)


@dataclass
class _Context:
    product: Product
    batch: ProductBatch
    manufacturer: Company


def last4(code: str) -> str:
    return identity.normalise(code)[-4:]


def _day(when: datetime) -> str:
    local = when.astimezone(WAT)
    return f"{local.day} {local:%b %Y}"


def _time(when: datetime) -> str:
    return f"{when.astimezone(WAT):%H:%M} on {_day(when)} (Nigeria time)"


def _company_name(db: Session, company_id: uuid.UUID | None) -> str | None:
    company = db.get(Company, company_id) if company_id else None
    return company.display_name if company else None


def _area_name(db: Session, area_id: uuid.UUID | None) -> str | None:
    area = db.get(Area, area_id) if area_id else None
    return area.city if area else None


def _context(db: Session, batch_id: uuid.UUID) -> _Context | None:
    """Product, batch and manufacturer, or None if the manufacturer is not approved."""
    batch = db.get(ProductBatch, batch_id)
    product = db.get(Product, batch.product_id) if batch else None
    manufacturer = db.get(Company, product.company_id) if product else None
    if manufacturer is None or manufacturer.review_status != CompanyReviewStatus.APPROVED:
        return None
    return _Context(product, batch, manufacturer)


def _live_announcements(db: Session, ctx: _Context) -> list[ProductAnnouncement]:
    """Live notices for the product, and live recalls for the product or this batch."""
    return list(
        db.exec(
            select(ProductAnnouncement)
            .where(
                ProductAnnouncement.product_id == ctx.product.product_id,
                ProductAnnouncement.status == AnnouncementStatus.LIVE,
                or_(
                    ProductAnnouncement.batch_id.is_(None),
                    ProductAnnouncement.batch_id == ctx.batch.batch_id,
                ),
            )
            .order_by(ProductAnnouncement.created_at.desc())
        ).all()
    )


def _event_fact(db: Session, event: LifecycleEvent, ctx: _Context) -> str | None:
    when = _day(event.occurred_at)
    actor = _company_name(db, event.retailer_company_id or event.actor_company_id) or "a company"
    area = _area_name(db, event.area_id)
    where = f" in {area}" if area else ""
    match event.event_type:
        case LifecycleEventType.ISSUED:
            return f"Code issued by {ctx.manufacturer.display_name} on {when}."
        case LifecycleEventType.RELEASED:
            return f"Released for sale by {ctx.manufacturer.display_name} on {when}."
        case LifecycleEventType.TRANSFERRED:
            receiver = _company_name(db, event.to_company_id) or "another company"
            return f"Sent by {actor} to {receiver} on {when}."
        case LifecycleEventType.RECEIVED:
            note = (
                " (received without a recorded transfer)" if event.received_without_transfer else ""
            )
            return f"Received by {actor}{where} on {when}{note}."
        case LifecycleEventType.SOLD:
            till = " at the shop till" if event.source == EventSource.POS_API else ""
            return f"Recorded as sold by {actor}{where}{till} on {when}."
        case LifecycleEventType.RETURNED:
            return f"Recorded as returned to {actor} on {when}."
        case LifecycleEventType.SALE_CORRECTED:
            return f"Sale corrected by {actor} on {when}; the earlier sale stays in the record."
        case LifecycleEventType.RECALLED:
            return f"Recall recorded on {when}."
    return None


def _facts(db: Session, ctx: _Context, column, subject_id: uuid.UUID) -> list[str]:
    events = db.exec(
        select(LifecycleEvent)
        .where(column == subject_id)
        .order_by(LifecycleEvent.occurred_at, LifecycleEvent.recorded_at)
    ).all()
    return [fact for event in events if (fact := _event_fact(db, event, ctx))]


def _suspicious_patterns(db: Session, unit: ProductUnit) -> list[str]:
    alerts = db.exec(
        select(RiskAlert).where(
            RiskAlert.unit_id == unit.unit_id,
            RiskAlert.rule != RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
            or_(
                (
                    RiskAlert.status.in_([AlertStatus.OPEN, AlertStatus.INVESTIGATING])
                    & RiskAlert.level.in_([AlertLevel.MEDIUM, AlertLevel.HIGH])
                ),
                RiskAlert.status == AlertStatus.RESOLVED_SUSPECTED_COPY,
            ),
        )
    ).all()
    patterns: list[str] = []
    for alert in alerts:
        text = (
            SUSPECTED_COPY_REVIEW
            if alert.status == AlertStatus.RESOLVED_SUSPECTED_COPY
            else PATTERNS.get(alert.rule, "Unusual activity recorded for this code.")
        )
        if text not in patterns:
            patterns.append(text)
    return patterns


def _base(ctx: _Context, today: date) -> dict:
    expired = ctx.batch.expiry_date is not None and ctx.batch.expiry_date < today
    warnings = (
        [f"The expiry date of this batch ({_day_from_date(ctx.batch.expiry_date)}) has passed."]
        if expired
        else []
    )
    return {
        "product": CheckProduct(
            name=ctx.product.name,
            brand=ctx.product.brand,
            size=ctx.product.size,
            manufacturer_name=ctx.manufacturer.display_name,
            registration_number=ctx.product.registration_number,
        ),
        "batch": CheckBatch(
            batch_number=ctx.batch.batch_number,
            expiry_date=ctx.batch.expiry_date,
            expired=expired,
        ),
        "warnings": warnings,
    }


def _day_from_date(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _notices(rows: list[ProductAnnouncement]) -> list[CheckNotice]:
    return [
        CheckNotice(kind=a.kind.value, title=a.title, message=a.message, posted_at=a.created_at)
        for a in rows[:MAX_NOTICES]
    ]


def _invalid(identifier_type: IdentifierType, code: str, window: int) -> CheckResponse:
    typed = identifier_type == IdentifierType.TYPED
    return CheckResponse(
        result=CheckResult.INVALID_IDENTITY,
        identifier_type=identifier_type,
        subject=None,
        code_last4=last4(code),
        title=INVALID_TYPED_TITLE if typed else TITLES[CheckResult.INVALID_IDENTITY],
        message=INVALID_TYPED if typed else INVALID_SCANNED,
        advice=None if typed else ASK_SELLER,
        just_sold_window_hours=window,
    )


def _check_unit(
    db: Session, unit: ProductUnit, ctx: _Context, identifier_type: IdentifierType, code: str,
    now: datetime, window: int,
) -> CheckResponse:  # fmt: skip
    base = _base(ctx, now.astimezone(WAT).date())
    announcements = _live_announcements(db, ctx)
    recalled = unit.lifecycle_status == LifecycleStatus.RECALLED or any(
        a.kind == AnnouncementKind.RECALL for a in announcements
    )
    facts = _facts(db, ctx, LifecycleEvent.unit_id, unit.unit_id)
    if unit.lifecycle_status == LifecycleStatus.ISSUED:
        facts.append("Not yet recorded as released for sale by the manufacturer.")
    patterns = _suspicious_patterns(db, unit)
    sale = (
        CheckSale(
            retailer_name=_company_name(db, unit.last_sold_company_id),
            area=_area_name(db, unit.last_sold_area_id),
            sold_at=unit.last_sold_at,
        )
        if unit.last_sold_at
        else None
    )

    fields: dict = {"tip": None, "advice": None}
    if patterns:
        result = CheckResult.SUSPICIOUS_ACTIVITY
        fields |= {
            "message": SUSPICIOUS_MESSAGE,
            "advice": "Ask the seller about it or choose another pack, and report a concern.",
        }
        if recalled:
            base["warnings"].append("The manufacturer has posted a recall that covers this pack.")
    elif recalled:
        result = CheckResult.BATCH_OR_PRODUCT_WARNING
        fields |= {
            "message": (
                f"{ctx.manufacturer.display_name} has posted a recall that covers this pack. "
                "Read the company's message below before you buy or use it."
            ),
        }
    elif sale and sale.sold_at >= now - timedelta(hours=window):
        result = CheckResult.RECOGNISED_JUST_SOLD
        place = f", {sale.area}," if sale.area else ""
        fields |= {
            "message": (
                f"Just sold by {sale.retailer_name or 'a shop'}{place} at {_time(sale.sold_at)}. "
                "If that was your purchase, this matches."
            ),
            "tip": f"Sales recorded in the last {window} hours show as just sold.",
        }
    elif sale:
        result = CheckResult.RECOGNISED_PREVIOUSLY_SOLD
        place = f" in {sale.area}" if sale.area else ""
        fields |= {
            "message": (f"This code was already recorded as sold on {_day(sale.sold_at)}{place}."),
            "advice": PREVIOUSLY_SOLD_ADVICE,
        }
    else:
        result = CheckResult.RECOGNISED_NOT_SOLD
        fields |= {
            "message": (
                f"This code was issued by {ctx.manufacturer.display_name} and is in circulation."
            ),
            "tip": NOT_SOLD_TIP,
        }

    return CheckResponse(
        result=result,
        identifier_type=identifier_type,
        subject="PACK",
        code_last4=last4(code),
        title=TITLES[result],
        just_sold_window_hours=window,
        sale=sale if result != CheckResult.RECOGNISED_NOT_SOLD else None,
        recorded_facts=facts,
        possible_patterns=patterns,
        notices=_notices(announcements),
        can_note_purchase=sale is None,
        **base,
        **fields,
    )


def _check_carton(
    db: Session, carton: Carton, ctx: _Context, identifier_type: IdentifierType, code: str,
    now: datetime, window: int,
) -> CheckResponse:  # fmt: skip
    base = _base(ctx, now.astimezone(WAT).date())
    announcements = _live_announcements(db, ctx)
    recalled = carton.lifecycle_status == LifecycleStatus.RECALLED or any(
        a.kind == AnnouncementKind.RECALL for a in announcements
    )
    if recalled:
        result = CheckResult.BATCH_OR_PRODUCT_WARNING
        title = TITLES[result]
        message = (
            f"{ctx.manufacturer.display_name} has posted a recall that covers this carton. "
            "Read the company's message below."
        )
        base["warnings"].append(CARTON_MESSAGE)
    else:
        result = CheckResult.CARTON_CODE
        title, message = CARTON_TITLE, CARTON_MESSAGE
    return CheckResponse(
        result=result,
        identifier_type=identifier_type,
        subject="CARTON",
        code_last4=last4(code),
        title=title,
        message=message,
        just_sold_window_hours=window,
        recorded_facts=_facts(db, ctx, LifecycleEvent.carton_id, carton.carton_id),
        notices=_notices(announcements),
        **base,
    )


def check_code(
    db: Session,
    code: str,
    identifier_type: IdentifierType,
    *,
    area: Area | None,
    now: datetime,
    window_hours: int,
) -> CheckResponse:
    """Evaluate a code and append one anonymous scan_event. Changes nothing else."""
    digest = identity.token_hash(code)
    unit = db.exec(select(ProductUnit).where(ProductUnit.qr_token_hash == digest)).first()
    carton = None if unit else db.exec(select(Carton).where(Carton.qr_token_hash == digest)).first()
    subject = unit or carton
    ctx = _context(db, subject.batch_id) if subject else None
    now = now.astimezone(UTC)

    if subject is None or ctx is None or subject.lifecycle_status == LifecycleStatus.VOIDED:
        response = _invalid(identifier_type, code, window_hours)
    elif unit:
        response = _check_unit(db, unit, ctx, identifier_type, code, now, window_hours)
    else:
        response = _check_carton(db, carton, ctx, identifier_type, code, now, window_hours)

    # A recognised carton is always logged as CARTON_CODE, even under a recall, so carton scans
    # never count as pack checks in stats or risk rules (D148).
    logged = (
        CheckResult.CARTON_CODE
        if carton and response.result != CheckResult.INVALID_IDENTITY
        else response.result
    )
    db.add(
        ScanEvent(
            identifier_type=identifier_type,
            unit_id=unit.unit_id if unit else None,
            carton_id=carton.carton_id if carton else None,
            area_id=area.area_id if area else None,
            result=logged,
        )
    )
    db.commit()
    return response
