import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import CreatedAtMixin, TimestampMixin, enum_column, uuid_pk
from app.models.enums import AlertLevel, AlertStatus, RiskRule

_STILL_OPEN = "status IN ('OPEN', 'INVESTIGATING')"
_RULE_9 = "rule = 'R9_MORE_OBSERVED_THAN_ALLOCATED'"
_RULE_4 = "rule = 'R4_INVALID_BURST'"


class RiskAlert(TimestampMixin, table=True):
    """Explainable alert from a deterministic rule (D124, D125, D143): a signal, not a verdict.
    At most one open alert per (rule, unit), and per (rule, batch, area) for rule 9."""

    __tablename__ = "risk_alert"
    __table_args__ = (
        CheckConstraint(
            f"NOT ({_RULE_9}) OR (batch_id IS NOT NULL AND area_id IS NOT NULL)",
            name="rule_9_has_batch_and_area",
        ),
        Index(
            "uq_risk_alert_open_rule_unit",
            "rule",
            "unit_id",
            unique=True,
            postgresql_where=text(f"unit_id IS NOT NULL AND {_STILL_OPEN}"),
        ),
        Index(
            "uq_risk_alert_open_rule_batch_area",
            "rule",
            "batch_id",
            "area_id",
            unique=True,
            postgresql_where=text(f"{_RULE_9} AND {_STILL_OPEN}"),
        ),
        # Rule 4 has no unit: one open alert per area (D152).
        Index(
            "uq_risk_alert_open_rule_area",
            "rule",
            "area_id",
            unique=True,
            postgresql_where=text(f"{_RULE_4} AND {_STILL_OPEN}"),
        ),
        # Rule 8 on a voided carton code: one open alert per carton (D152).
        Index(
            "uq_risk_alert_open_rule_carton",
            "rule",
            "carton_id",
            unique=True,
            postgresql_where=text(f"carton_id IS NOT NULL AND unit_id IS NULL AND {_STILL_OPEN}"),
        ),
    )

    alert_id: uuid.UUID = uuid_pk()
    rule: RiskRule = Field(sa_type=enum_column(RiskRule, "risk_rule"))
    level: AlertLevel = Field(sa_type=enum_column(AlertLevel, "alert_level"))
    # Null means admin only (rule 4, invalid-code burst).
    manufacturer_id: uuid.UUID | None = Field(
        default=None, foreign_key="company.company_id", index=True
    )
    unit_id: uuid.UUID | None = Field(default=None, foreign_key="product_unit.unit_id", index=True)
    carton_id: uuid.UUID | None = Field(default=None, foreign_key="carton.carton_id")
    batch_id: uuid.UUID | None = Field(default=None, foreign_key="product_batch.batch_id")
    area_id: uuid.UUID | None = Field(default=None, foreign_key="area.area_id")
    # {event_ids, scan_ids, snapshot, explanation}; the snapshot survives the scan purge.
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    status: AlertStatus = Field(
        default=AlertStatus.OPEN, sa_type=enum_column(AlertStatus, "alert_status")
    )
    resolved_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.user_id")
    resolved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class RiskAlertNote(CreatedAtMixin, table=True):
    """An investigation note on an alert, with its author and time (D125, D152). Append-only
    through the service: notes are never edited or deleted."""

    __tablename__ = "risk_alert_note"
    __table_args__ = (CheckConstraint("btrim(body) <> ''", name="body_not_blank"),)

    note_id: uuid.UUID = uuid_pk()
    alert_id: uuid.UUID = Field(foreign_key="risk_alert.alert_id", index=True)
    author_user_id: uuid.UUID = Field(foreign_key="app_user.user_id")
    body: str = Field(sa_type=Text)
