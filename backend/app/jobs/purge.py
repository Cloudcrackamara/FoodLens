"""Delete consumer scan logs older than 12 months (D118). Run daily: uv run python -m app.jobs.purge

Alert evidence keeps its own snapshot, so alerts still read after their scans are gone. Scheduling
the daily run is part of deployment (Phase 9).
"""

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session

from app.core.db import get_engine
from app.models import ScanEvent
from app.models.base import utc_now

RETENTION = timedelta(days=365)


def purge_scans(db: Session, now: datetime | None = None) -> int:
    """Delete scan_event rows older than the retention period. Returns how many were deleted."""
    cutoff = (now or utc_now()) - RETENTION
    result = db.execute(delete(ScanEvent).where(ScanEvent.created_at < cutoff))
    db.commit()
    return result.rowcount or 0


def main() -> None:
    with Session(get_engine()) as db:
        deleted = purge_scans(db)
    print(f"Deleted {deleted} scan log rows older than 12 months.")


if __name__ == "__main__":
    main()
