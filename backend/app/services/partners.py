"""A manufacturer's partners (D144): companies that recorded its packs, derived from events, with
the POS partners those companies are linked to. Nothing is stored or reviewed here."""

import uuid
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import (
    Area,
    Company,
    LifecycleEvent,
    PosPartner,
    PosPartnerRetailer,
    ProductUnit,
)
from app.models.enums import LifecycleEventType, PosLinkStatus
from app.services.risk import standing_only


@dataclass
class _Seen:
    places: set[str] = field(default_factory=set)
    received: set[uuid.UUID] = field(default_factory=set)
    sold: set[uuid.UUID] = field(default_factory=set)


@dataclass(frozen=True)
class Partner:
    company: Company
    places: list[str]
    received: int
    sold: int
    pos_partners: list[str]


def partners(db: Session, company_id: uuid.UUID) -> list[Partner]:
    events = db.exec(
        standing_only(
            select(LifecycleEvent)
            .join(ProductUnit, ProductUnit.unit_id == LifecycleEvent.unit_id)
            .where(
                ProductUnit.manufacturer_id == company_id,
                LifecycleEvent.event_type.in_(
                    [
                        LifecycleEventType.RECEIVED,
                        LifecycleEventType.SOLD,
                        LifecycleEventType.TRANSFERRED,
                    ]
                ),
            )
        )
    ).all()
    seen: dict[uuid.UUID, _Seen] = {}
    for event in events:
        if event.event_type == LifecycleEventType.TRANSFERRED:
            # A transfer names both sides; the receiver may not have recorded anything yet.
            for party in (event.actor_company_id, event.to_company_id):
                if party and party != company_id:
                    seen.setdefault(party, _Seen())
            continue
        party = event.retailer_company_id or event.actor_company_id
        if party is None or party == company_id:
            continue
        row = seen.setdefault(party, _Seen())
        area = db.get(Area, event.area_id) if event.area_id else None
        if area:
            row.places.add(area.city)
        if event.event_type == LifecycleEventType.RECEIVED:
            row.received.add(event.unit_id)
        else:
            row.sold.add(event.unit_id)

    result = []
    for party, row in seen.items():
        links = db.exec(
            select(PosPartner.name)
            .join(PosPartnerRetailer, PosPartnerRetailer.partner_id == PosPartner.partner_id)
            .where(
                PosPartnerRetailer.retailer_company_id == party,
                PosPartnerRetailer.status == PosLinkStatus.ACTIVE,
            )
            .order_by(PosPartner.name)
        ).all()
        result.append(
            Partner(
                company=db.get(Company, party),
                places=sorted(row.places),
                received=len(row.received),
                sold=len(row.sold),
                pos_partners=list(links),
            )
        )
    return sorted(result, key=lambda p: p.company.display_name)
