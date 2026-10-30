"""Admin: POS partners, API keys, retailer links and tills (D121). Every route requires an admin.
Rules live in services/pos_admin.py."""

import uuid

from fastapi import APIRouter, HTTPException, Request

from app.core.auth import AdminUser
from app.core.db import DbSession
from app.models import PosPartnerKey
from app.schemas.pos import (
    KeyCreated,
    KeyRead,
    LinkCreateRequest,
    LinkRead,
    OneTimeCredentials,
    PartnerCreated,
    PartnerCreateRequest,
    PartnerRead,
    PartnerStatusRequest,
    RetailerLocationRead,
    RetailerOptionRead,
    TillCreateRequest,
    TillRead,
)
from app.services import pos_admin
from app.services.pos_auth import PosError

router = APIRouter(prefix="/api/admin/pos", tags=["admin"])


def _refuse(error: pos_admin.PosAdminError | PosError) -> HTTPException:
    return HTTPException(error.status_code, error.message)


def _key_read(key: PosPartnerKey) -> KeyRead:
    return KeyRead(
        key_id=key.key_id,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
    )


def _partner_read(found: pos_admin.PartnerDetail) -> PartnerRead:
    partner = found.partner
    return PartnerRead(
        partner_id=partner.partner_id,
        name=partner.name,
        status=partner.status,
        created_at=partner.created_at,
        keys=[_key_read(k) for k in found.keys],
        links=[
            LinkRead(
                link_id=link.link_id,
                retailer_id=company.company_id,
                retailer_name=company.display_name,
                status=link.status,
            )
            for link, company in found.links
        ],
        tills=[
            TillRead(
                till_id=till.till_id,
                retailer_id=company.company_id,
                retailer_name=company.display_name,
                till_ref=till.till_ref,
                location_name=location.name,
                area=location.area,
            )
            for till, company, location in found.tills
        ],
    )


@router.get("/partners")
def list_partners(admin: AdminUser, db: DbSession) -> list[PartnerRead]:
    return [_partner_read(p) for p in pos_admin.list_partners(db)]


@router.post("/partners", status_code=201)
def create_partner(
    body: PartnerCreateRequest, request: Request, admin: AdminUser, db: DbSession
) -> PartnerCreated:
    try:
        found, key, secret = pos_admin.create_partner(
            db, request.app.state.settings, admin, body.name
        )
    except PosError as error:
        raise _refuse(error) from None
    return PartnerCreated(
        partner=_partner_read(found),
        credentials=OneTimeCredentials(api_key=key, signing_secret=secret),
    )


@router.post("/partners/{partner_id}/status")
def set_status(
    partner_id: uuid.UUID, body: PartnerStatusRequest, admin: AdminUser, db: DbSession
) -> PartnerRead:
    try:
        return _partner_read(pos_admin.set_status(db, admin, partner_id, body.status))
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.post("/partners/{partner_id}/keys", status_code=201)
def add_key(partner_id: uuid.UUID, admin: AdminUser, db: DbSession) -> KeyCreated:
    try:
        key, raw = pos_admin.add_key(db, admin, partner_id)
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None
    return KeyCreated(key=_key_read(key), credentials=OneTimeCredentials(api_key=raw))


@router.post("/partners/{partner_id}/keys/{key_id}/revoke")
def revoke_key(
    partner_id: uuid.UUID, key_id: uuid.UUID, admin: AdminUser, db: DbSession
) -> KeyRead:
    try:
        return _key_read(pos_admin.revoke_key(db, admin, partner_id, key_id))
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.post("/partners/{partner_id}/retailers")
def link_retailer(
    partner_id: uuid.UUID, body: LinkCreateRequest, admin: AdminUser, db: DbSession
) -> PartnerRead:
    try:
        return _partner_read(pos_admin.link_retailer(db, admin, partner_id, body.retailer_id))
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.post("/partners/{partner_id}/retailers/{link_id}/revoke")
def revoke_link(
    partner_id: uuid.UUID, link_id: uuid.UUID, admin: AdminUser, db: DbSession
) -> PartnerRead:
    try:
        return _partner_read(pos_admin.revoke_link(db, admin, partner_id, link_id))
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.post("/partners/{partner_id}/tills")
def add_till(
    partner_id: uuid.UUID, body: TillCreateRequest, admin: AdminUser, db: DbSession
) -> PartnerRead:
    try:
        return _partner_read(
            pos_admin.add_till(
                db, admin, partner_id, body.retailer_id, body.till_ref, body.location_id
            )
        )
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.delete("/partners/{partner_id}/tills/{till_id}")
def remove_till(
    partner_id: uuid.UUID, till_id: uuid.UUID, admin: AdminUser, db: DbSession
) -> PartnerRead:
    try:
        return _partner_read(pos_admin.remove_till(db, admin, partner_id, till_id))
    except pos_admin.PosAdminError as error:
        raise _refuse(error) from None


@router.get("/retailers")
def retailer_options(admin: AdminUser, db: DbSession) -> list[RetailerOptionRead]:
    return [
        RetailerOptionRead(
            retailer_id=company.company_id,
            display_name=company.display_name,
            locations=[
                RetailerLocationRead(location_id=loc.location_id, name=loc.name, area=loc.area)
                for loc in locations
            ],
        )
        for company, locations in pos_admin.retailer_options(db)
    ]
