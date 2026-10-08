import uuid

from sqlmodel import Field

from app.models.base import CreatedAtMixin, enum_column, uuid_pk
from app.models.enums import LookupResult


class BatchScan(CreatedAtMixin, table=True):
    """Anonymised lookup log. Append-only. Deliberately has no user, session, IP address,
    user agent, or location column: a scan cannot be traced to a person."""

    __tablename__ = "batch_scan"

    scan_id: uuid.UUID = uuid_pk()
    # Normalised input as entered, truncated to 64 characters.
    input_product_code: str | None = None
    input_batch_number: str | None = None
    matched_batch_id: uuid.UUID | None = Field(
        default=None, foreign_key="product_batch.batch_id", index=True
    )
    result: LookupResult = Field(sa_type=enum_column(LookupResult, "lookup_result"))
