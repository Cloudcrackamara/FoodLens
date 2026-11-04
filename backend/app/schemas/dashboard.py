"""Manufacturer and admin dashboard reads (D144, D154). Only the alert id and report id leave the
server, for the dashboards that act on them; never a unit or carton id, token or hash, and nothing
about any consumer."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AlertLevel,
    ConcernType,
    LifecycleEventType,
    LifecycleStatus,
    ReportStatus,
    RiskRule,
)


class FromService(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InventoryRowRead(FromService):
    company_name: str | None
    area: str | None
    not_allocated: bool
    allocated: int
    received: int
    in_stock: int
    sold: int
    returned: int


class TimelineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=100)


class TimelineEntryRead(FromService):
    at: datetime
    event_type: LifecycleEventType
    text: str
    note: str | None


class TimelineAlertRead(FromService):
    alert_id: uuid.UUID
    rule_name: str
    level: AlertLevel


class TimelineRead(FromService):
    subject: str
    code_last4: str | None
    product_name: str
    size: str | None
    batch_number: str
    expiry_date: date | None
    status: LifecycleStatus
    entries: list[TimelineEntryRead]
    open_alerts: list[TimelineAlertRead]


class PartnerRead(BaseModel):
    display_name: str
    is_manufacturer: bool
    is_distributor: bool
    is_retailer: bool
    places: list[str]
    received: int
    sold: int
    pos_partners: list[str]


class ReportRead(BaseModel):
    report_id: uuid.UUID
    concern_type: ConcernType
    description: str
    status: ReportStatus
    manufacturer_name: str | None
    product_name: str | None
    batch_number: str | None
    area: str | None
    created_at: datetime


class ReportStatusRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: ReportStatus


class CityWeekRead(FromService):
    week_start: date
    city: str
    checks: int


class HotSpotRead(FromService):
    city: str
    open_alerts: int
    checks: int


class AlertCountRead(FromService):
    rule: RiskRule
    rule_name: str
    level: AlertLevel
    raised: int
    resolved: int


class ManufacturerStatsRead(FromService):
    issued: int
    released: int
    sale_coverage_pct: float | None
    pos_sales: int
    merchant_sales: int
    pos_share_pct: float | None
    merchant_share_pct: float | None
    checks_by_city_week: list[CityWeekRead]
    hot_spots: list[HotSpotRead]
    alerts: list[AlertCountRead]
    alerts_raised: int
    alerts_resolved: int
    median_hours_to_resolve: float | None


class PlatformStatsRead(FromService):
    companies: int
    approved_companies: int
    packs_issued: int
    checks_last_30_days: int
    pos_partners: int
    open_alerts: int
    new_reports: int
    pos_rate_limit_hits_last_30_days: int


class ScanningRowRead(FromService):
    day: date
    area: str
    rate_limit_hits: int
    invalid_codes: int
    burst_alerts: int
