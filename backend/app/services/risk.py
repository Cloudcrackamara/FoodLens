"""Deterministic, explainable risk rules (D124, D142, D143, D152).

The rules run synchronously, in the same transaction as the check or lifecycle event that
triggers them. An alert is a signal for the manufacturer to review, never a verdict.

    Consumer check of a pack       6, 3, 2, 9, then 1 (rule 1 needs to know what else fired)
    Consumer check, voided code    8 (pack or carton code)
    Consumer check, invalid code   4 (per area, admin only)
    Merchant or POS receipt/sale   7, plus 2 and 9 on a sale (single packs only)
    POS lookup or sale refused     5 (a lookup of the till's own standing sale is not a signal)

Never a signal: a buyer rescanning in the same area within the just-sold window, a sale that a
valid return or correction followed, carton events (except rule 8), a receipt outside its
allocation.

At most one OPEN or INVESTIGATING alert per (rule, unit), per (rule, carton), per (rule, batch,
area) for rule 9 and per (rule, area) for rule 4. A new trigger appends its evidence to that
alert and can raise its level. Evidence keeps ids plus a snapshot of what was seen, so it still
reads after the 12-month scan purge.
"""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import (
    Area,
    BatchAllocation,
    Carton,
    Company,
    LifecycleEvent,
    ProductUnit,
    RiskAlert,
    ScanEvent,
)
from app.models.base import utc_now
from app.models.enums import (
    AlertLevel,
    AlertStatus,
    CheckResult,
    LifecycleEventType,
    LifecycleStatus,
    RiskRule,
)

# Nigeria time for explanations (UTC+1 all year); kept here to avoid importing services.check.
_WAT = timezone(timedelta(hours=1), "WAT")
INVALID_BURST_MINUTES = 10
SCAN_VOLUME_HOURS = 24
# Evidence lists are capped so a burst cannot grow one alert without bound.
MAX_EVIDENCE = 100

OPEN_STATUSES = (AlertStatus.OPEN, AlertStatus.INVESTIGATING)
_LEVEL_ORDER = {AlertLevel.LOW: 0, AlertLevel.MEDIUM: 1, AlertLevel.HIGH: 2}

# Approved wording (30 Oct 2026). Dashboard only; consumers see check.PATTERNS.
RULE_NAMES = {
    RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE: "Checked elsewhere after a sale",
    RiskRule.R2_IMPOSSIBLE_TRAVEL: "Seen too far apart, too quickly",
    RiskRule.R3_SCAN_VOLUME: "Many checks in 24 hours",
    RiskRule.R4_INVALID_BURST: "Burst of unrecognised codes",
    RiskRule.R5_POS_UNAVAILABLE_UNIT: "Till tried an unavailable pack",
    RiskRule.R6_UNRELEASED_SCANNED: "Unreleased pack checked",
    RiskRule.R7_CUSTODY_CONFLICT: "Custody conflict",
    RiskRule.R8_VOIDED_CODE_IN_USE: "Voided code in use",
    RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED: "More seen than allocated",
}
_POS_STATES = {
    "ALREADY_SOLD": "sold",
    "RECALLED": "recalled",
    "UNRELEASED": "not released",
    "VOIDED": "voided",
}


@dataclass(frozen=True)
class Thresholds:
    window_hours: int
    different_area_km: float
    travel_min_km: float
    max_travel_kmh: float
    scan_volume: int
    invalid_burst: int
    overage_pct: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "Thresholds":
        return cls(
            window_hours=settings.just_sold_window_hours,
            different_area_km=settings.risk_different_area_km,
            travel_min_km=settings.risk_travel_min_km,
            max_travel_kmh=settings.risk_max_travel_kmh,
            scan_volume=settings.risk_scan_volume,
            invalid_burst=settings.risk_invalid_burst,
            overage_pct=settings.allocation_overage_pct,
        )


# --- Helpers ---------------------------------------------------------------------------------


def _time(when: datetime) -> str:
    local = when.astimezone(_WAT)
    return f"{local:%H:%M} on {local.day} {local:%b %Y}"


def _day(when: datetime) -> str:
    local = when.astimezone(_WAT)
    return f"{local.day} {local:%b %Y}"


def _duration(hours: float) -> str:
    minutes = max(0, round(hours * 60))
    return f"{minutes // 60} h {minutes % 60} min"


def km_between(a: Area, b: Area) -> float:
    """Great-circle distance between two area centres."""
    lat1, lon1, lat2, lon2 = map(
        math.radians, (float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude))
    )
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _company_name(db: Session, company_id: uuid.UUID | None) -> str:
    company = db.get(Company, company_id) if company_id else None
    return company.display_name if company else "a company"


def _undone_sales():
    """SOLD events that a valid return or sale correction followed: ignored by every rule."""
    returned = select(LifecycleEvent.returns_event_id).where(
        LifecycleEvent.returns_event_id.is_not(None)
    )
    corrected = select(LifecycleEvent.corrects_event_id).where(
        LifecycleEvent.corrects_event_id.is_not(None)
    )
    return returned.union(corrected)


def _standing(query):
    """Limit a lifecycle_event query to events that still count: no undone sales."""
    return query.where(
        or_(
            LifecycleEvent.event_type != LifecycleEventType.SOLD,
            LifecycleEvent.event_id.not_in(_undone_sales()),
        )
    )


def _str_ids(ids) -> list[str]:
    return [str(i) for i in ids if i is not None]


def _raise(
    db: Session,
    rule: RiskRule,
    level: AlertLevel,
    explanation: str,
    *,
    now: datetime,
    manufacturer_id: uuid.UUID | None,
    unit_id: uuid.UUID | None = None,
    carton_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    area_id: uuid.UUID | None = None,
    event_ids=(),
    scan_ids=(),
    snapshot: dict[str, Any] | None = None,
) -> RiskAlert:
    """Open a new alert, or append to the open one with the same subject."""
    statement = select(RiskAlert).where(RiskAlert.rule == rule, RiskAlert.status.in_(OPEN_STATUSES))
    if rule == RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED:
        statement = statement.where(RiskAlert.batch_id == batch_id, RiskAlert.area_id == area_id)
    elif unit_id is not None:
        statement = statement.where(RiskAlert.unit_id == unit_id)
    elif carton_id is not None:
        statement = statement.where(RiskAlert.carton_id == carton_id, RiskAlert.unit_id.is_(None))
    else:
        statement = statement.where(RiskAlert.area_id == area_id, RiskAlert.unit_id.is_(None))
    entry = {"at": now.isoformat(), "explanation": explanation, **(snapshot or {})}
    existing = db.exec(statement.with_for_update()).first()
    if existing is not None:
        evidence = dict(existing.evidence)
        evidence["explanation"] = explanation
        evidence["occurrences"] = int(evidence.get("occurrences", 1)) + 1
        for key, ids in (("event_ids", event_ids), ("scan_ids", scan_ids)):
            known = list(evidence.get(key, []))
            known += [i for i in _str_ids(ids) if i not in known]
            evidence[key] = known[-MAX_EVIDENCE:]
        evidence["snapshot"] = (list(evidence.get("snapshot", [])) + [entry])[-MAX_EVIDENCE:]
        existing.evidence = evidence
        if _LEVEL_ORDER[level] > _LEVEL_ORDER[existing.level]:
            existing.level = level
        existing.updated_at = utc_now()
        db.add(existing)
        db.flush()
        return existing

    alert = RiskAlert(
        rule=rule,
        level=level,
        manufacturer_id=manufacturer_id,
        unit_id=unit_id,
        carton_id=carton_id,
        batch_id=batch_id,
        area_id=area_id,
        evidence={
            "explanation": explanation,
            "occurrences": 1,
            "event_ids": _str_ids(event_ids),
            "scan_ids": _str_ids(scan_ids),
            "snapshot": [entry],
        },
    )
    try:
        with db.begin_nested():
            db.add(alert)
            db.flush()
    except IntegrityError:
        # Another request opened the same alert first: append to it instead.
        db.expunge(alert)
        return _raise(
            db, rule, level, explanation, now=now, manufacturer_id=manufacturer_id,
            unit_id=unit_id, carton_id=carton_id, batch_id=batch_id, area_id=area_id,
            event_ids=event_ids, scan_ids=scan_ids, snapshot=snapshot,
        )  # fmt: skip
    return alert


@dataclass
class _Sighting:
    at: datetime
    area: Area
    what: str  # "check", "sale" or "receipt"
    scan_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None


def _last_sighting(
    db: Session, unit_id: uuid.UUID, before: datetime, skip_event: uuid.UUID | None = None
) -> _Sighting | None:
    """The unit's most recent earlier sighting with an area: a consumer check, or a standing
    receipt or sale."""
    scan = db.exec(
        select(ScanEvent)
        .where(
            ScanEvent.unit_id == unit_id,
            ScanEvent.area_id.is_not(None),
            ScanEvent.created_at <= before,
        )
        .order_by(ScanEvent.created_at.desc())
    ).first()
    events = select(LifecycleEvent).where(
        LifecycleEvent.unit_id == unit_id,
        LifecycleEvent.event_type.in_([LifecycleEventType.RECEIVED, LifecycleEventType.SOLD]),
        LifecycleEvent.area_id.is_not(None),
        LifecycleEvent.occurred_at <= before,
    )
    if skip_event is not None:
        events = events.where(LifecycleEvent.event_id != skip_event)
    event = db.exec(_standing(events).order_by(LifecycleEvent.occurred_at.desc())).first()
    options = []
    if scan is not None:
        options.append(
            _Sighting(scan.created_at, db.get(Area, scan.area_id), "check", scan_id=scan.scan_id)
        )
    if event is not None:
        what = "sale" if event.event_type == LifecycleEventType.SOLD else "receipt"
        options.append(
            _Sighting(event.occurred_at, db.get(Area, event.area_id), what, event_id=event.event_id)
        )
    return max(options, key=lambda s: s.at) if options else None


# --- Rules -----------------------------------------------------------------------------------


def _rule2(
    db: Session,
    th: Thresholds,
    unit: ProductUnit,
    area: Area,
    at: datetime,
    *,
    now: datetime,
    scan_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> RiskAlert | None:
    previous = _last_sighting(db, unit.unit_id, at, skip_event=event_id)
    if previous is None or previous.area.area_id == area.area_id:
        return None
    km = km_between(previous.area, area)
    if km <= th.travel_min_km:
        return None
    hours = (at - previous.at).total_seconds() / 3600
    speed = math.inf if hours <= 0 else km / hours
    if speed <= th.max_travel_kmh:
        return None
    speed_text = "faster than 1,000 km/h" if speed > 1000 else f"about {round(speed)} km/h"
    explanation = (
        f"Seen in {previous.area.city} at {_time(previous.at)} and in {area.city} at {_time(at)}: "
        f"{round(km)} km apart in {_duration(hours)} ({speed_text})."
    )
    return _raise(
        db, RiskRule.R2_IMPOSSIBLE_TRAVEL, AlertLevel.HIGH, explanation, now=now,
        manufacturer_id=unit.manufacturer_id, unit_id=unit.unit_id, batch_id=unit.batch_id,
        area_id=area.area_id, event_ids=[previous.event_id, event_id],
        scan_ids=[previous.scan_id, scan_id],
        snapshot={
            "from": {
                "area": previous.area.city,
                "at": previous.at.isoformat(),
                "what": previous.what,
            },
            "to": {"area": area.city, "at": at.isoformat()},
            "km": round(km),
            "hours": round(hours, 2),
        },
    )  # fmt: skip


def _rule9(
    db: Session,
    th: Thresholds,
    unit: ProductUnit,
    area: Area,
    *,
    now: datetime,
    scan_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> RiskAlert | None:
    """Distinct packs of the batch seen in this area (checks and standing sales, including
    packs allocated elsewhere) above the area's allocation by more than the overage percent.
    An area without an allocation counts as 0; a batch with no allocations is skipped."""
    allocations = db.exec(
        select(BatchAllocation).where(BatchAllocation.batch_id == unit.batch_id)
    ).all()
    if not allocations:
        return None
    allocated = sum(a.quantity for a in allocations if a.destination_area_id == area.area_id)
    checked = db.exec(
        select(ScanEvent.unit_id)
        .join(ProductUnit, ProductUnit.unit_id == ScanEvent.unit_id)
        .where(
            ProductUnit.batch_id == unit.batch_id,
            ScanEvent.area_id == area.area_id,
            ScanEvent.result != CheckResult.INVALID_IDENTITY,
        )
        .distinct()
    ).all()
    sold = db.exec(
        _standing(
            select(LifecycleEvent.unit_id)
            .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
            .where(
                ProductUnit.batch_id == unit.batch_id,
                LifecycleEvent.event_type == LifecycleEventType.SOLD,
                LifecycleEvent.area_id == area.area_id,
            )
        ).distinct()
    ).all()
    seen = len(set(checked) | set(sold) | {unit.unit_id})
    if seen <= allocated * (1 + th.overage_pct / 100):
        return None
    existing = db.exec(
        select(RiskAlert).where(
            RiskAlert.rule == RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
            RiskAlert.batch_id == unit.batch_id,
            RiskAlert.area_id == area.area_id,
            RiskAlert.status.in_(OPEN_STATUSES),
        )
    ).first()
    if existing is not None and int(existing.evidence.get("seen", 0)) >= seen:
        return existing  # nothing new to add
    explanation = (
        f"More units seen in {area.city} than were allocated there: possible counterfeit or "
        f"unauthorised supply. ({seen} seen, {allocated} allocated.)"
    )
    alert = _raise(
        db, RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED, AlertLevel.MEDIUM, explanation, now=now,
        manufacturer_id=unit.manufacturer_id, batch_id=unit.batch_id, area_id=area.area_id,
        event_ids=[event_id], scan_ids=[scan_id],
        snapshot={"area": area.city, "seen": seen, "allocated": allocated},
    )  # fmt: skip
    alert.evidence = {**alert.evidence, "seen": seen}
    db.add(alert)
    return alert


def _other_open_alerts(db: Session, unit_id: uuid.UUID) -> bool:
    return (
        db.exec(
            select(func.count())
            .select_from(RiskAlert)
            .where(
                RiskAlert.unit_id == unit_id,
                RiskAlert.status.in_(OPEN_STATUSES),
                RiskAlert.rule.not_in(
                    [
                        RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE,
                        RiskRule.R9_MORE_OBSERVED_THAN_ALLOCATED,
                    ]
                ),
            )
        ).one()
        > 0
    )


# --- Entry points ----------------------------------------------------------------------------


def on_pack_check(
    db: Session,
    th: Thresholds,
    *,
    unit: ProductUnit,
    scan_id: uuid.UUID,
    area: Area | None,
    now: datetime,
) -> list[RiskAlert]:
    """A consumer check of a recognised, not voided pack. Runs before the result is built, so
    an alert raised by this check counts towards it (D116)."""
    fired: list[RiskAlert] = []
    where = f" in {area.city}" if area else ""

    if unit.lifecycle_status == LifecycleStatus.ISSUED:
        fired.append(
            _raise(
                db,
                RiskRule.R6_UNRELEASED_SCANNED,
                AlertLevel.MEDIUM,
                f"Checked by a consumer{where} before the manufacturer released it for sale.",
                now=now,
                manufacturer_id=unit.manufacturer_id,
                unit_id=unit.unit_id,
                batch_id=unit.batch_id,
                area_id=area.area_id if area else None,
                scan_ids=[scan_id],
                snapshot={"area": area.city if area else None},
            )  # fmt: skip
        )

    recent = db.exec(
        select(func.count())
        .select_from(ScanEvent)
        .where(
            ScanEvent.unit_id == unit.unit_id,
            ScanEvent.created_at >= now - timedelta(hours=SCAN_VOLUME_HOURS),
        )
    ).one()
    checks = recent + 1
    if checks > th.scan_volume:
        fired.append(
            _raise(
                db,
                RiskRule.R3_SCAN_VOLUME,
                AlertLevel.MEDIUM,
                f"Checked {checks} times in 24 hours (alert threshold: {th.scan_volume} checks).",
                now=now,
                manufacturer_id=unit.manufacturer_id,
                unit_id=unit.unit_id,
                batch_id=unit.batch_id,
                scan_ids=[scan_id],
                snapshot={"checks": checks},
            )  # fmt: skip
        )

    if area is None:
        return fired

    travel = _rule2(db, th, unit, area, now, now=now, scan_id=scan_id)
    if travel is not None:
        fired.append(travel)
    _rule9(db, th, unit, area, now=now, scan_id=scan_id)  # dashboard only; never escalates rule 1

    sold_area = db.get(Area, unit.last_sold_area_id) if unit.last_sold_area_id else None
    if (
        unit.last_sold_at is not None
        and sold_area is not None
        and now - unit.last_sold_at > timedelta(hours=th.window_hours)
        and km_between(sold_area, area) > th.different_area_km
    ):
        combined = bool(fired) or _other_open_alerts(db, unit.unit_id)
        hours = int((now - unit.last_sold_at).total_seconds() // 3600)
        fired.append(
            _raise(
                db,
                RiskRule.R1_SCAN_AFTER_SALE_ELSEWHERE,
                AlertLevel.MEDIUM if combined else AlertLevel.LOW,
                f"Checked in {area.city} at {_time(now)}, {hours} hours after it was recorded as "
                f"sold in {sold_area.city}.",
                now=now,
                manufacturer_id=unit.manufacturer_id,
                unit_id=unit.unit_id,
                batch_id=unit.batch_id,
                area_id=area.area_id,
                scan_ids=[scan_id],
                snapshot={"area": area.city, "sold_in": sold_area.city, "hours_after_sale": hours},
            )  # fmt: skip
        )
    return fired


def on_voided_check(
    db: Session,
    *,
    unit: ProductUnit | None,
    carton: Carton | None,
    scan_id: uuid.UUID,
    area: Area | None,
    now: datetime,
) -> RiskAlert:
    """Rule 8: a voided pack or carton code is in use (possible leaked label file)."""
    subject = unit or carton
    assert subject is not None
    explanation = (
        f"A voided code was checked in {area.city}: possible leaked label file."
        if area
        else "A voided code was checked: possible leaked label file."
    )
    return _raise(
        db, RiskRule.R8_VOIDED_CODE_IN_USE, AlertLevel.HIGH, explanation, now=now,
        manufacturer_id=subject.manufacturer_id, unit_id=unit.unit_id if unit else None,
        carton_id=carton.carton_id if carton else None, batch_id=subject.batch_id,
        area_id=area.area_id if area else None, scan_ids=[scan_id],
        snapshot={"area": area.city if area else None, "subject": "carton" if carton else "pack"},
    )  # fmt: skip


def on_invalid_check(db: Session, th: Thresholds, *, scan_id: uuid.UUID, area: Area | None,
                     now: datetime) -> RiskAlert | None:  # fmt: skip
    """Rule 4: a burst of unrecognised codes from one area. No unit and no manufacturer: admin
    only."""
    if area is None:
        return None
    earlier = db.exec(
        select(func.count())
        .select_from(ScanEvent)
        .where(
            ScanEvent.area_id == area.area_id,
            ScanEvent.result == CheckResult.INVALID_IDENTITY,
            ScanEvent.created_at >= now - timedelta(minutes=INVALID_BURST_MINUTES),
        )
    ).one()
    count = earlier + 1
    if count < th.invalid_burst:
        return None
    return _raise(
        db, RiskRule.R4_INVALID_BURST, AlertLevel.MEDIUM,
        f"{count} unrecognised codes were checked from {area.city} within "
        f"{INVALID_BURST_MINUTES} minutes.",
        now=now, manufacturer_id=None, area_id=area.area_id, scan_ids=[scan_id],
        snapshot={"area": area.city, "count": count},
    )  # fmt: skip


def on_pack_event(
    db: Session,
    th: Thresholds,
    *,
    unit: ProductUnit,
    event_id: uuid.UUID,
    event_type: LifecycleEventType,
    company_id: uuid.UUID,
    area_id: uuid.UUID | None,
    at: datetime,
    now: datetime,
) -> list[RiskAlert]:
    """A merchant or POS RECEIVED or SOLD of a single pack (never a carton event)."""
    if event_type not in (LifecycleEventType.RECEIVED, LifecycleEventType.SOLD):
        return []
    fired: list[RiskAlert] = []

    previous = db.exec(
        _standing(
            select(LifecycleEvent).where(
                LifecycleEvent.unit_id == unit.unit_id,
                LifecycleEvent.event_type.in_(
                    [LifecycleEventType.RECEIVED, LifecycleEventType.SOLD]
                ),
                LifecycleEvent.event_id != event_id,
                LifecycleEvent.occurred_at <= at,
            )
        ).order_by(LifecycleEvent.occurred_at.desc(), LifecycleEvent.recorded_at.desc())
    ).first()
    other = (previous.retailer_company_id or previous.actor_company_id) if previous else None
    if previous is not None and other is not None and other != company_id:
        transfer = db.exec(
            select(LifecycleEvent.event_id).where(
                LifecycleEvent.unit_id == unit.unit_id,
                LifecycleEvent.event_type == LifecycleEventType.TRANSFERRED,
                LifecycleEvent.actor_company_id == other,
                LifecycleEvent.to_company_id == company_id,
                LifecycleEvent.occurred_at >= previous.occurred_at,
                LifecycleEvent.occurred_at <= at,
            )
        ).first()
        if transfer is None:
            verb = {LifecycleEventType.RECEIVED: "receiving", LifecycleEventType.SOLD: "selling"}
            fired.append(
                _raise(
                    db,
                    RiskRule.R7_CUSTODY_CONFLICT,
                    AlertLevel.MEDIUM,
                    f"{_company_name(db, company_id)} recorded {verb[event_type]} this pack with "
                    f"no transfer from {_company_name(db, other)}, which recorded "
                    f"{verb[previous.event_type]} it on {_day(previous.occurred_at)}.",
                    now=now,
                    manufacturer_id=unit.manufacturer_id,
                    unit_id=unit.unit_id,
                    batch_id=unit.batch_id,
                    area_id=area_id,
                    event_ids=[previous.event_id, event_id],
                    snapshot={
                        "earlier": {
                            "company": _company_name(db, other),
                            "event": previous.event_type,
                            "at": previous.occurred_at.isoformat(),
                        },
                        "later": {
                            "company": _company_name(db, company_id),
                            "event": event_type,
                            "at": at.isoformat(),
                        },
                    },
                )  # fmt: skip
            )

    area = db.get(Area, area_id) if area_id else None
    if event_type == LifecycleEventType.SOLD and area is not None:
        travel = _rule2(db, th, unit, area, at, now=now, event_id=event_id)
        if travel is not None:
            fired.append(travel)
        _rule9(db, th, unit, area, now=now, event_id=event_id)
    return fired


def on_pos_refusal(
    db: Session,
    *,
    unit: ProductUnit,
    retailer: Company,
    till_ref: str,
    attempt: str,
    problem: str,
    now: datetime,
) -> RiskAlert | None:
    """Rule 5: a till looked up or tried to sell a pack that is sold, recalled, unreleased or
    voided. A lookup of the till's own retailer's standing sale is not a signal (D152)."""
    state = _POS_STATES.get(problem)
    if state is None:
        return None
    if (
        attempt == "LOOKUP"
        and unit.lifecycle_status == LifecycleStatus.SOLD
        and unit.last_sold_company_id == retailer.company_id
    ):
        return None
    action = "looked up" if attempt == "LOOKUP" else "tried to sell"
    return _raise(
        db, RiskRule.R5_POS_UNAVAILABLE_UNIT, AlertLevel.MEDIUM,
        f"A shop till ({retailer.display_name}, till {till_ref}) {action} this pack while it "
        f"was {state}.",
        now=now, manufacturer_id=unit.manufacturer_id, unit_id=unit.unit_id,
        batch_id=unit.batch_id,
        snapshot={"retailer": retailer.display_name, "till": till_ref, "attempt": attempt,
                  "state": state},
    )  # fmt: skip
