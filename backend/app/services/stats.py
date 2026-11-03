"""Manufacturer stats, platform stats and the automated-scanning panel (D144, D154).

Everything is counted from events, scans, alerts and daily counters at request time; nothing is
stored. Days and weeks are in Nigeria time, and weeks start on Monday. No IP or other visitor
identifier exists in any table read here.
"""

import statistics
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Area,
    Company,
    ConsumerReport,
    LifecycleEvent,
    PosPartner,
    ProductUnit,
    RateLimitDaily,
    RiskAlert,
    ScanEvent,
)
from app.models.enums import (
    AlertLevel,
    CheckResult,
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    PosPartnerStatus,
    RateLimitBucket,
    ReportStatus,
    RiskRule,
)
from app.services.check import WAT
from app.services.risk import OPEN_STATUSES, RULE_NAMES, standing_only

TIMEZONE = "Africa/Lagos"  # the same as WAT: UTC+1 all year
TREND_WEEKS = 12
RECENT_DAYS = 30
HOT_SPOTS = 5
UNKNOWN_AREA = "Unknown area"
# POS hits come from partners rather than scanning, so they are in platform stats instead.
_SCANNING_BUCKETS = (RateLimitBucket.CHECK, RateLimitBucket.REPORT)


def _local(column):
    return func.timezone(TIMEZONE, column)


def _trend_start(now: datetime) -> datetime:
    """Monday 00:00, Nigeria time, of the first of the last TREND_WEEKS weeks."""
    today = now.astimezone(WAT).date()
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=TREND_WEEKS - 1)
    return datetime.combine(monday, time.min, tzinfo=WAT)


def _percent(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def _area_names(db: Session, area_ids) -> dict[uuid.UUID, str]:
    ids = {area_id for area_id in area_ids if area_id}
    if not ids:
        return {}
    return dict(db.exec(select(Area.area_id, Area.city).where(Area.area_id.in_(ids))).all())


@dataclass(frozen=True)
class CityWeek:
    week_start: date
    city: str
    checks: int


@dataclass(frozen=True)
class HotSpot:
    city: str
    open_alerts: int
    checks: int


@dataclass(frozen=True)
class AlertCount:
    rule: RiskRule
    rule_name: str
    level: AlertLevel
    raised: int
    resolved: int


@dataclass(frozen=True)
class ManufacturerStats:
    issued: int
    released: int
    sale_coverage_pct: float | None
    pos_sales: int
    merchant_sales: int
    pos_share_pct: float | None
    merchant_share_pct: float | None
    checks_by_city_week: list[CityWeek]
    hot_spots: list[HotSpot]
    alerts: list[AlertCount]
    alerts_raised: int
    alerts_resolved: int
    median_hours_to_resolve: float | None


def _checks_by_city_week(db: Session, company_id: uuid.UUID, start: datetime) -> list[CityWeek]:
    week = func.date_trunc("week", _local(ScanEvent.created_at))
    rows = db.exec(
        select(week, ScanEvent.area_id, func.count())
        .join(ProductUnit, ProductUnit.unit_id == ScanEvent.unit_id)
        .where(ProductUnit.manufacturer_id == company_id, ScanEvent.created_at >= start)
        .group_by(week, ScanEvent.area_id)
    ).all()
    names = _area_names(db, [row[1] for row in rows])
    result = [
        CityWeek(when.date(), names.get(area_id, UNKNOWN_AREA), count)
        for when, area_id, count in rows
    ]
    return sorted(result, key=lambda r: (r.week_start, r.city))


def _hot_spots(db: Session, company_id: uuid.UUID, now: datetime) -> list[HotSpot]:
    open_alerts = dict(
        db.exec(
            select(RiskAlert.area_id, func.count())
            .where(
                RiskAlert.manufacturer_id == company_id,
                RiskAlert.status.in_(OPEN_STATUSES),
                RiskAlert.area_id.is_not(None),
            )
            .group_by(RiskAlert.area_id)
        ).all()
    )
    checks = dict(
        db.exec(
            select(ScanEvent.area_id, func.count())
            .join(ProductUnit, ProductUnit.unit_id == ScanEvent.unit_id)
            .where(
                ProductUnit.manufacturer_id == company_id,
                ScanEvent.area_id.is_not(None),
                ScanEvent.created_at >= now - timedelta(days=RECENT_DAYS),
            )
            .group_by(ScanEvent.area_id)
        ).all()
    )
    names = _area_names(db, [*open_alerts, *checks])
    spots = [
        HotSpot(names[area_id], open_alerts.get(area_id, 0), checks.get(area_id, 0))
        for area_id in {*open_alerts, *checks}
    ]
    spots.sort(key=lambda s: (-s.open_alerts, -s.checks, s.city))
    return spots[:HOT_SPOTS]


def manufacturer_stats(db: Session, company_id: uuid.UUID, now: datetime) -> ManufacturerStats:
    issued = db.exec(
        select(func.count())
        .select_from(ProductUnit)
        .where(
            ProductUnit.manufacturer_id == company_id,
            ProductUnit.lifecycle_status != LifecycleStatus.VOIDED,
        )
    ).one()
    released = set(
        db.exec(
            select(LifecycleEvent.unit_id)
            .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
            .where(
                ProductUnit.manufacturer_id == company_id,
                LifecycleEvent.event_type == LifecycleEventType.RELEASED,
            )
            .distinct()
        ).all()
    )
    sales = db.exec(
        standing_only(
            select(LifecycleEvent.unit_id, LifecycleEvent.source)
            .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
            .where(
                ProductUnit.manufacturer_id == company_id,
                LifecycleEvent.event_type == LifecycleEventType.SOLD,
            )
        )
    ).all()
    pos_sales = sum(1 for _, source in sales if source == EventSource.POS_API)
    merchant_sales = sum(1 for _, source in sales if source == EventSource.MERCHANT_APP)
    channel_total = pos_sales + merchant_sales

    start = _trend_start(now)
    alerts = db.exec(
        select(RiskAlert).where(
            RiskAlert.manufacturer_id == company_id,
        )
    ).all()
    counts: dict[tuple[RiskRule, AlertLevel], list[int]] = {}
    durations = []
    for alert in alerts:
        row = counts.setdefault((alert.rule, alert.level), [0, 0])
        if alert.created_at >= start:
            row[0] += 1
        if alert.resolved_at is not None and alert.resolved_at >= start:
            row[1] += 1
            durations.append((alert.resolved_at - alert.created_at).total_seconds() / 3600)
    alert_rows = [
        AlertCount(rule, RULE_NAMES[rule], level, raised, resolved)
        for (rule, level), (raised, resolved) in sorted(counts.items())
        if raised or resolved
    ]

    return ManufacturerStats(
        issued=issued,
        released=len(released),
        sale_coverage_pct=_percent(len(released & {unit for unit, _ in sales}), len(released)),
        pos_sales=pos_sales,
        merchant_sales=merchant_sales,
        pos_share_pct=_percent(pos_sales, channel_total),
        merchant_share_pct=_percent(merchant_sales, channel_total),
        checks_by_city_week=_checks_by_city_week(db, company_id, start),
        hot_spots=_hot_spots(db, company_id, now),
        alerts=alert_rows,
        alerts_raised=sum(row.raised for row in alert_rows),
        alerts_resolved=sum(row.resolved for row in alert_rows),
        median_hours_to_resolve=round(statistics.median(durations), 1) if durations else None,
    )


# --- Admin ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlatformStats:
    companies: int
    approved_companies: int
    packs_issued: int
    checks_last_30_days: int
    pos_partners: int
    open_alerts: int
    new_reports: int
    pos_rate_limit_hits_last_30_days: int


def _count(db: Session, model, *where) -> int:
    return db.exec(select(func.count()).select_from(model).where(*where)).one()


def platform_stats(db: Session, now: datetime) -> PlatformStats:
    since = now - timedelta(days=RECENT_DAYS)
    pos_hits = db.exec(
        select(func.coalesce(func.sum(RateLimitDaily.count), 0)).where(
            RateLimitDaily.bucket == RateLimitBucket.POS,
            RateLimitDaily.day >= since.astimezone(WAT).date(),
        )
    ).one()
    return PlatformStats(
        companies=_count(db, Company),
        approved_companies=_count(
            db, Company, Company.review_status == CompanyReviewStatus.APPROVED
        ),
        packs_issued=_count(
            db, ProductUnit, ProductUnit.lifecycle_status != LifecycleStatus.VOIDED
        ),
        checks_last_30_days=_count(db, ScanEvent, ScanEvent.created_at >= since),
        pos_partners=_count(db, PosPartner, PosPartner.status == PosPartnerStatus.ACTIVE),
        open_alerts=_count(db, RiskAlert, RiskAlert.status.in_(OPEN_STATUSES)),
        new_reports=_count(db, ConsumerReport, ConsumerReport.status == ReportStatus.NEW),
        pos_rate_limit_hits_last_30_days=int(pos_hits),
    )


@dataclass(frozen=True)
class ScanningRow:
    day: date
    area: str
    rate_limit_hits: int
    invalid_codes: int
    burst_alerts: int


def scanning_panel(db: Session, now: datetime) -> list[ScanningRow]:
    """Per area and day, for the last 30 days. Only counts: there is nothing about any visitor."""
    since = now - timedelta(days=RECENT_DAYS)
    totals: dict[tuple[date, uuid.UUID | None], list[int]] = {}

    def add(day: date, area_id: uuid.UUID | None, index: int, count: int) -> None:
        totals.setdefault((day, area_id), [0, 0, 0])[index] += count

    for area_id, day, count in db.exec(
        select(RateLimitDaily.area_id, RateLimitDaily.day, func.sum(RateLimitDaily.count))
        .where(
            RateLimitDaily.bucket.in_(_SCANNING_BUCKETS),
            RateLimitDaily.day >= since.astimezone(WAT).date(),
        )
        .group_by(RateLimitDaily.area_id, RateLimitDaily.day)
    ).all():
        add(day, area_id, 0, int(count))

    scan_day = func.date(_local(ScanEvent.created_at))
    for area_id, day, count in db.exec(
        select(ScanEvent.area_id, scan_day, func.count())
        .where(
            ScanEvent.result == CheckResult.INVALID_IDENTITY,
            ScanEvent.created_at >= since,
        )
        .group_by(ScanEvent.area_id, scan_day)
    ).all():
        add(day, area_id, 1, count)

    alert_day = func.date(_local(RiskAlert.created_at))
    for area_id, day, count in db.exec(
        select(RiskAlert.area_id, alert_day, func.count())
        .where(RiskAlert.rule == RiskRule.R4_INVALID_BURST, RiskAlert.created_at >= since)
        .group_by(RiskAlert.area_id, alert_day)
    ).all():
        add(day, area_id, 2, count)

    names = _area_names(db, [area_id for _, area_id in totals])
    rows = [
        ScanningRow(day, names.get(area_id, UNKNOWN_AREA), *counts)
        for (day, area_id), counts in totals.items()
    ]
    return sorted(rows, key=lambda r: (-r.day.toordinal(), r.area))
