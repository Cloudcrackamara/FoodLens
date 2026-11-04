"""Admin management of POS partners, API keys, retailer links and tills (D121).

Only platform admins reach these (routers/pos_admin.py). Raw API keys and signing secrets are
returned once, at creation, and never stored or logged. Every change writes an audit entry.
"""

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import Settings
from app.models import (
    AppUser,
    Company,
    PosPartner,
    PosPartnerKey,
    PosPartnerRetailer,
    PosTill,
    SupplierLocation,
)
from app.models.base import utc_now
from app.models.enums import CompanyReviewStatus, PosLinkStatus, PosPartnerStatus, ReviewStatus
from app.services import audit, pos_auth

MSG_NOT_FOUND = "Not found"
MSG_BAD_RETAILER = "Choose an approved retailer company."
MSG_ALREADY_LINKED = "This retailer is already linked to the partner."
MSG_LINK_FIRST = "Link the retailer to this partner first."
MSG_BAD_LOCATION = "Choose a reviewed location of this retailer that has an area."
MSG_TILL_EXISTS = "This till is already registered for the retailer."
MSG_KEY_REVOKED = "This key is already revoked."
MSG_LINK_REVOKED = "This link is already revoked."


class PosAdminError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class PartnerDetail:
    partner: PosPartner
    keys: list[PosPartnerKey]
    links: list[tuple[PosPartnerRetailer, Company]]
    tills: list[tuple[PosTill, Company, SupplierLocation]]


def _partner(db: Session, partner_id: uuid.UUID) -> PosPartner:
    partner = db.get(PosPartner, partner_id)
    if partner is None:
        raise PosAdminError(MSG_NOT_FOUND, 404)
    return partner


def _retailer(db: Session, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if (
        company is None
        or company.review_status != CompanyReviewStatus.APPROVED
        or not company.is_retailer
    ):
        raise PosAdminError(MSG_BAD_RETAILER, 422)
    return company


def detail(db: Session, partner: PosPartner) -> PartnerDetail:
    pid = partner.partner_id
    keys = list(
        db.exec(
            select(PosPartnerKey)
            .where(PosPartnerKey.partner_id == pid)
            .order_by(PosPartnerKey.created_at)
        )
    )
    links = list(
        db.exec(
            select(PosPartnerRetailer, Company)
            .join(Company, Company.company_id == PosPartnerRetailer.retailer_company_id)
            .where(PosPartnerRetailer.partner_id == pid)
            .order_by(Company.display_name)
        ).all()
    )
    tills = list(
        db.exec(
            select(PosTill, Company, SupplierLocation)
            .join(Company, Company.company_id == PosTill.retailer_company_id)
            .join(SupplierLocation, SupplierLocation.location_id == PosTill.location_id)
            .where(PosTill.partner_id == pid)
            .order_by(Company.display_name, PosTill.till_ref)
        ).all()
    )
    return PartnerDetail(partner, keys, links, tills)


def list_partners(db: Session) -> list[PartnerDetail]:
    partners = db.exec(select(PosPartner).order_by(PosPartner.created_at)).all()
    return [detail(db, p) for p in partners]


def get_partner(db: Session, partner_id: uuid.UUID) -> PartnerDetail:
    return detail(db, _partner(db, partner_id))


def _new_key(db: Session, partner: PosPartner) -> tuple[PosPartnerKey, str]:
    raw = pos_auth.new_api_key()
    key = PosPartnerKey(
        partner_id=partner.partner_id, key_prefix=raw[:8], key_hash=pos_auth.key_hash(raw)
    )
    db.add(key)
    db.flush()
    return key, raw


def create_partner(
    db: Session, settings: Settings, admin: AppUser, name: str
) -> tuple[PartnerDetail, str, str]:
    """Returns the partner with its first API key and its signing secret, both raw, once."""
    raw_secret = pos_auth.new_signing_secret()
    partner = PosPartner(
        name=name,
        signing_secret_encrypted=pos_auth.encrypt_secret(settings, raw_secret),
        created_by_user_id=admin.user_id,
    )
    db.add(partner)
    db.flush()
    key, raw_key = _new_key(db, partner)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner",
        entity_id=partner.partner_id,
        action="create",
        new_values={"name": name, "key_prefix": key.key_prefix},
    )
    db.commit()
    return detail(db, partner), raw_key, raw_secret


def set_status(
    db: Session, admin: AppUser, partner_id: uuid.UUID, status: PosPartnerStatus
) -> PartnerDetail:
    partner = _partner(db, partner_id)
    old = partner.status
    partner.status = status
    partner.updated_at = utc_now()
    db.add(partner)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner",
        entity_id=partner.partner_id,
        action="set_status",
        old_values={"status": old},
        new_values={"status": status},
    )
    db.commit()
    return detail(db, partner)


def add_key(db: Session, admin: AppUser, partner_id: uuid.UUID) -> tuple[PosPartnerKey, str]:
    partner = _partner(db, partner_id)
    key, raw = _new_key(db, partner)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner_key",
        entity_id=key.key_id,
        action="create",
        new_values={"partner_id": str(partner.partner_id), "key_prefix": key.key_prefix},
    )
    db.commit()
    db.refresh(key)
    return key, raw


def revoke_key(
    db: Session, admin: AppUser, partner_id: uuid.UUID, key_id: uuid.UUID
) -> PosPartnerKey:
    key = db.get(PosPartnerKey, key_id)
    if key is None or key.partner_id != partner_id:
        raise PosAdminError(MSG_NOT_FOUND, 404)
    if key.revoked_at is not None:
        raise PosAdminError(MSG_KEY_REVOKED, 409)
    key.revoked_at = utc_now()
    db.add(key)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner_key",
        entity_id=key.key_id,
        action="revoke",
        new_values={"key_prefix": key.key_prefix},
    )
    db.commit()
    db.refresh(key)
    return key


def link_retailer(
    db: Session, admin: AppUser, partner_id: uuid.UUID, retailer_id: uuid.UUID
) -> PartnerDetail:
    """A revoked link is made active again rather than duplicated."""
    partner = _partner(db, partner_id)
    _retailer(db, retailer_id)
    link = db.exec(
        select(PosPartnerRetailer).where(
            PosPartnerRetailer.partner_id == partner_id,
            PosPartnerRetailer.retailer_company_id == retailer_id,
        )
    ).first()
    if link is not None and link.status == PosLinkStatus.ACTIVE:
        raise PosAdminError(MSG_ALREADY_LINKED, 409)
    if link is None:
        link = PosPartnerRetailer(
            partner_id=partner_id, retailer_company_id=retailer_id, created_by_user_id=admin.user_id
        )
    link.status = PosLinkStatus.ACTIVE
    link.updated_at = utc_now()
    db.add(link)
    db.flush()
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner_retailer",
        entity_id=link.link_id,
        action="link",
        new_values={"partner_id": str(partner_id), "retailer_company_id": str(retailer_id)},
    )
    db.commit()
    return detail(db, partner)


def revoke_link(
    db: Session, admin: AppUser, partner_id: uuid.UUID, link_id: uuid.UUID
) -> PartnerDetail:
    partner = _partner(db, partner_id)
    link = db.get(PosPartnerRetailer, link_id)
    if link is None or link.partner_id != partner_id:
        raise PosAdminError(MSG_NOT_FOUND, 404)
    if link.status == PosLinkStatus.REVOKED:
        raise PosAdminError(MSG_LINK_REVOKED, 409)
    link.status = PosLinkStatus.REVOKED
    link.updated_at = utc_now()
    db.add(link)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_partner_retailer",
        entity_id=link.link_id,
        action="revoke",
        old_values={"status": PosLinkStatus.ACTIVE},
        new_values={"status": PosLinkStatus.REVOKED},
    )
    db.commit()
    return detail(db, partner)


def add_till(
    db: Session,
    admin: AppUser,
    partner_id: uuid.UUID,
    retailer_id: uuid.UUID,
    till_ref: str,
    location_id: uuid.UUID,
) -> PartnerDetail:
    partner = _partner(db, partner_id)
    _retailer(db, retailer_id)
    link = db.exec(
        select(PosPartnerRetailer).where(
            PosPartnerRetailer.partner_id == partner_id,
            PosPartnerRetailer.retailer_company_id == retailer_id,
            PosPartnerRetailer.status == PosLinkStatus.ACTIVE,
        )
    ).first()
    if link is None:
        raise PosAdminError(MSG_LINK_FIRST, 422)
    location = db.get(SupplierLocation, location_id)
    if (
        location is None
        or location.company_id != retailer_id
        or location.review_status != ReviewStatus.APPROVED
        or location.area_id is None
    ):
        raise PosAdminError(MSG_BAD_LOCATION, 422)
    exists = db.exec(
        select(PosTill.till_id).where(
            PosTill.partner_id == partner_id,
            PosTill.retailer_company_id == retailer_id,
            PosTill.till_ref == till_ref,
        )
    ).first()
    if exists is not None:
        raise PosAdminError(MSG_TILL_EXISTS, 409)
    till = PosTill(
        partner_id=partner_id,
        retailer_company_id=retailer_id,
        till_ref=till_ref,
        location_id=location_id,
    )
    db.add(till)
    db.flush()
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_till",
        entity_id=till.till_id,
        action="create",
        new_values={
            "partner_id": str(partner_id),
            "retailer_company_id": str(retailer_id),
            "till_ref": till_ref,
            "location_id": str(location_id),
        },
    )
    db.commit()
    return detail(db, partner)


def remove_till(
    db: Session, admin: AppUser, partner_id: uuid.UUID, till_id: uuid.UUID
) -> PartnerDetail:
    """Events keep their till_ref text, so removing a till leaves the history intact."""
    partner = _partner(db, partner_id)
    till = db.get(PosTill, till_id)
    if till is None or till.partner_id != partner_id:
        raise PosAdminError(MSG_NOT_FOUND, 404)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="pos_till",
        entity_id=till.till_id,
        action="remove",
        old_values={
            "till_ref": till.till_ref,
            "retailer_company_id": str(till.retailer_company_id),
        },
    )
    db.delete(till)
    db.commit()
    return detail(db, partner)


def retailer_options(db: Session) -> list[tuple[Company, list[SupplierLocation]]]:
    """Approved retailers with their reviewed locations that have an area: the only valid
    choices for links and tills."""
    retailers = db.exec(
        select(Company)
        .where(
            Company.review_status == CompanyReviewStatus.APPROVED,
            Company.is_retailer.is_(True),
        )
        .order_by(Company.display_name)
    ).all()
    options = []
    for company in retailers:
        locations = db.exec(
            select(SupplierLocation)
            .where(
                SupplierLocation.company_id == company.company_id,
                SupplierLocation.review_status == ReviewStatus.APPROVED,
                SupplierLocation.area_id.is_not(None),
            )
            .order_by(SupplierLocation.name)
        ).all()
        options.append((company, list(locations)))
    return options
