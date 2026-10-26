"""Public consumer check and report shapes (D115, D120, D138, D141).

Responses carry public fields only: no unit, carton, batch, product or company IDs, and at most
the last 4 characters of the code. Every response carries data_mode DEMO and the disclaimer.
The page banner shows "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE", so the disclaimer does
not repeat those words.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CheckResult, ConcernType, DataMode, IdentifierType

DISCLAIMER = (
    "FoodLens shows what has been recorded for this code in a demonstration database with "
    "fictional companies and products. It is not NAFDAC's or SON's service, it is not a "
    "laboratory test, and it cannot prove anything about the item in your hand. No QR system "
    "catches every copied code."
)

COPY_HELP = (
    "A copied QR carries the same code. FoodLens spots copies by whether the code was sold, "
    "where it is checked, how often, and where the stock was sent, not by the QR alone. "
    "No QR system catches every copied code."
)

ANNOUNCEMENT_LABEL = "Message from the company — not reviewed by FoodLens"


class CheckRequest(BaseModel):
    """`code` is the token from the QR link or the code printed under it, as typed."""

    code: str = Field(min_length=1, max_length=100)
    identifier_type: IdentifierType
    # Used only when SIMULATE_LOCATION_ENABLED is true (demo); ignored otherwise.
    simulated_city: str | None = Field(default=None, max_length=80)


class CheckProduct(BaseModel):
    name: str
    brand: str
    size: str | None
    manufacturer_name: str
    # As printed on the pack, information only; never checked against a register (D107).
    registration_number: str | None


class CheckBatch(BaseModel):
    batch_number: str
    expiry_date: date | None
    expired: bool


class CheckSale(BaseModel):
    retailer_name: str | None
    area: str | None
    sold_at: datetime


class CheckNotice(BaseModel):
    kind: Literal["NOTICE", "RECALL"]
    title: str
    message: str
    posted_at: datetime
    label: str = ANNOUNCEMENT_LABEL


class CheckResponse(BaseModel):
    data_mode: DataMode = DataMode.DEMO
    disclaimer: str = DISCLAIMER
    result: CheckResult
    identifier_type: IdentifierType
    subject: Literal["PACK", "CARTON"] | None
    code_last4: str
    title: str
    message: str
    tip: str | None = None
    advice: str | None = None
    just_sold_window_hours: int
    product: CheckProduct | None = None
    batch: CheckBatch | None = None
    sale: CheckSale | None = None
    # Recorded facts and possible patterns are kept apart (CLAUDE.md rule 1).
    recorded_facts: list[str] = []
    possible_patterns: list[str] = []
    warnings: list[str] = []
    notices: list[CheckNotice] = []
    # "I've bought this" is offered only when no sale is recorded; it changes nothing.
    can_note_purchase: bool = False
    copy_help: str = COPY_HELP
    can_report: bool = True


class ReportRequest(BaseModel):
    """Anonymous: no contact field (D120). `code` lets FoodLens route the report to the
    manufacturer; it is hashed and never stored."""

    code: str | None = Field(default=None, max_length=100)
    concern_type: ConcernType
    description: str = Field(min_length=1, max_length=1000)
    simulated_city: str | None = Field(default=None, max_length=80)


class ReportResponse(BaseModel):
    data_mode: DataMode = DataMode.DEMO
    disclaimer: str = DISCLAIMER
    message: str


class DemoCity(BaseModel):
    city: str
    state: str
