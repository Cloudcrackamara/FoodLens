"""Anonymous consumer data (D118, D120, D144). No table here has an IP, user agent, cookie,
device, GPS, user or session column; tests check the exact column lists."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import (
    CheckResult,
    ConcernType,
    IdentifierType,
    RateLimitBucket,
    ReportStatus,
)


class ScanEvent(CreatedAtMixin, table=True):
    """Consumer check log. Append-only (a trigger refuses UPDATE); rows are deleted after
    12 months by the purge job."""

    __tablename__ = "scan_event"
    __table_args__ = (
        CheckConstraint(
            "result <> 'CARTON_CODE' OR (carton_id IS NOT NULL AND unit_id IS NULL)",
            name="carton_code_has_carton",
        ),
    )

    scan_id: uuid.UUID = uuid_pk()
    identifier_type: IdentifierType = Field(sa_type=enum_column(IdentifierType, "identifier_type"))
    # Null for identifiers FoodLens does not recognise.
    unit_id: uuid.UUID | None = Field(default=None, foreign_key="product_unit.unit_id", index=True)
    carton_id: uuid.UUID | None = Field(default=None, foreign_key="carton.carton_id", index=True)
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id", index=True)
    result: CheckResult = Field(sa_type=enum_column(CheckResult, "check_result"))


class RateLimitDaily(TimestampMixin, table=True):
    """Rate-limit hits per coarse area, day and bucket, for the admin panel. No IP."""

    __tablename__ = "rate_limit_daily"
    __table_args__ = (
        # An unknown area (NULL) is one row per day and bucket, not one row per hit.
        UniqueConstraint("area_id", "day", "bucket", postgresql_nulls_not_distinct=True),
        CheckConstraint("count >= 0", name="count_not_negative"),
    )

    rate_limit_id: uuid.UUID = uuid_pk()
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id")
    day: date
    bucket: RateLimitBucket = Field(sa_type=enum_column(RateLimitBucket, "rate_limit_bucket"))
    count: int = Field(default=0)


class ConsumerReport(TimestampMixin, table=True):
    """Anonymous concern report, private to the unit's manufacturer and admins. No contact
    field (D120)."""

    __tablename__ = "consumer_report"
    __table_args__ = (
        CheckConstraint("char_length(description) <= 1000", name="description_length"),
    )

    report_id: uuid.UUID = uuid_pk()
    unit_id: uuid.UUID | None = Field(default=None, foreign_key="product_unit.unit_id", index=True)
    manufacturer_id: uuid.UUID | None = Field(
        default=None, foreign_key="company.company_id", index=True
    )
    concern_type: ConcernType = Field(sa_type=enum_column(ConcernType, "concern_type"))
    description: str = Field(sa_type=Text)
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id")
    status: ReportStatus = Field(
        default=ReportStatus.NEW, sa_type=enum_column(ReportStatus, "report_status")
    )
