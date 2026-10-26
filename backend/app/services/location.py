"""Coarse area for a consumer check or report (D118).

The area comes from, in order:
  1. With SIMULATE_LOCATION_ENABLED (demo only, off in production), the city the person picked
     in the demo picker, so a demo through the tunnel can show checks in other cities (D148).
  2. Cloudflare's visitor-location headers (`cf-ipcity`, `cf-region`), trusted only when the
     request arrives through a trusted proxy. The Next.js server forwards them only from
     cloudflared under the D90 conditions and strips them otherwise.
  3. The offline DB-IP Lite city file at GEOIP_DB_PATH, when set.
With the flag off, a picked city is ignored and only steps 2 and 3 apply.

Only the seeded `area` row leaves this module. The IP is used in memory to look up the area and
is then discarded: it is never stored, logged or returned.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.rate_limit import RateLimiters, is_trusted_proxy
from app.models import Area

logger = logging.getLogger(__name__)

# Region names as Cloudflare and DB-IP spell them, where they differ from the seeded state.
_STATE_ALIASES = {"federal capital territory": "fct"}


def _clean(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value.removesuffix(" state").strip()


def area_by_city(db: Session, city: str | None) -> Area | None:
    name = _clean(city)
    if not name:
        return None
    return db.exec(select(Area).where(func.lower(Area.city) == name)).first()


def area_by_state(db: Session, state: str | None) -> Area | None:
    """The state's capital-named city if seeded (Kano, Kano), otherwise its first city."""
    name = _clean(state)
    name = _STATE_ALIASES.get(name, name)
    if not name:
        return None
    rows = db.exec(select(Area).where(func.lower(Area.state) == name).order_by(Area.city)).all()
    return next((a for a in rows if a.city.lower() == name), rows[0] if rows else None)


def _from_place(db: Session, city: str | None, region: str | None) -> Area | None:
    return area_by_city(db, city) or area_by_state(db, region)


@lru_cache(maxsize=4)
def _geoip_reader(path: str) -> Any | None:
    if not Path(path).is_file():
        logger.warning("GEOIP_DB_PATH is set but the file does not exist; skipping it.")
        return None
    import maxminddb

    return maxminddb.open_database(path)


def _geoip_place(path: str, ip: str) -> tuple[str | None, str | None]:
    """(city, region) from the DB-IP Lite file. Lookup errors give (None, None)."""
    reader = _geoip_reader(path)
    if reader is None:
        return None, None
    try:
        record = reader.get(ip) or {}
    except ValueError:
        return None, None
    city = (record.get("city") or {}).get("names", {}).get("en")
    subdivisions = record.get("subdivisions") or [{}]
    region = subdivisions[0].get("names", {}).get("en")
    return city, region


def resolve_area(
    db: Session, request: Request, settings: Settings, simulated_city: str | None = None
) -> Area | None:
    if settings.simulate_location_enabled and simulated_city:
        area = area_by_city(db, simulated_city)
        if area:
            return area

    if is_trusted_proxy(request):
        area = _from_place(db, request.headers.get("cf-ipcity"), request.headers.get("cf-region"))
        if area:
            return area

    if settings.geoip_db_path:
        limiters: RateLimiters = request.app.state.rate_limiters
        area = _from_place(db, *_geoip_place(settings.geoip_db_path, limiters.client_ip(request)))
        if area:
            return area
    return None


def demo_cities(db: Session) -> list[Area]:
    return list(db.exec(select(Area).order_by(Area.city)).all())
