import uuid
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedAtMixin, uuid_pk


class Area(CreatedAtMixin, table=True):
    """Coarse area (city and state). Seeded reference data, read-only through the API (D118).
    The point is the city centre, never a person's location."""

    __tablename__ = "area"
    __table_args__ = (UniqueConstraint("city", "state"),)

    area_id: uuid.UUID = uuid_pk()
    city: str
    state: str
    latitude: Decimal = Field(max_digits=9, decimal_places=6)
    longitude: Decimal = Field(max_digits=9, decimal_places=6)
