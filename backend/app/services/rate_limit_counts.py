"""Daily rate-limit hit counts per coarse area, for the admin automated-scanning panel (D144).

The limiter's own counters stay in memory (core/rate_limit.py). This table holds only
(area, day, bucket, count): no IP or other visitor identifier.
"""

import uuid
from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.models import RateLimitDaily
from app.models.enums import RateLimitBucket


def count_hit(db: Session, area_id: uuid.UUID | None, bucket: RateLimitBucket, day: date) -> None:
    statement = insert(RateLimitDaily).values(
        rate_limit_id=uuid.uuid4(), area_id=area_id, day=day, bucket=bucket, count=1
    )
    db.execute(
        statement.on_conflict_do_update(
            constraint="uq_rate_limit_daily_area_id_day_bucket",
            set_={"count": RateLimitDaily.count + 1, "updated_at": func.now()},
        )
    )
    db.commit()
