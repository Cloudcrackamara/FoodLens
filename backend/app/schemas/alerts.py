"""Risk alert reads and the workflow requests (D125, D152). A request carries only the new status
or a note; resolver, times and evidence are decided by the server."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertLevel, AlertStatus, RiskRule

StatusFilter = Literal["OPEN", "INVESTIGATING", "RESOLVED", "ALL"]


class AlertNoteRead(BaseModel):
    author_name: str
    body: str
    created_at: datetime


class AlertRead(BaseModel):
    alert_id: uuid.UUID
    rule: RiskRule
    rule_name: str
    level: AlertLevel
    status: AlertStatus
    explanation: str
    occurrences: int
    manufacturer_name: str | None
    product_name: str | None
    batch_number: str | None
    carton_ref: str | None
    area: str | None
    created_at: datetime
    updated_at: datetime
    resolved_by_name: str | None
    resolved_at: datetime | None


class AlertDetailRead(AlertRead):
    # What was seen, oldest first; copied at the time, so it survives the scan purge.
    snapshot: list[dict[str, Any]]
    notes: list[AlertNoteRead]


class AlertStatusRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: AlertStatus


class AlertNoteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str = Field(max_length=1000)
