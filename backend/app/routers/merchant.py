"""Merchant page routes and staff management. Thin: rules live in services/lifecycle.py,
services/merchant.py and services/members.py.

Every route takes the path company from require_company_member, so a signed-in user can only act
for their own company. Staff management is owner only (D106); merchant events are for owner and
staff of an approved distributor or retailer.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_company_member
from app.core.db import DbSession
from app.models import CompanyMember
from app.models.enums import MemberRole
from app.schemas.merchant import (
    AddStaffRequest,
    DestinationRead,
    EventRequest,
    EventResponse,
    LookupRequest,
    LookupResponse,
    MemberRead,
)
from app.services import lifecycle, members, merchant

router = APIRouter(prefix="/api/companies/{company_id}", tags=["merchant"])

Member = Annotated[CompanyMember, Depends(require_company_member())]
Owner = Annotated[CompanyMember, Depends(require_company_member(MemberRole.OWNER))]


def _refuse(error: lifecycle.MerchantError | members.MemberError) -> HTTPException:
    return HTTPException(error.status_code, error.message)


@router.post("/merchant/lookup")
def lookup(
    company_id: uuid.UUID, body: LookupRequest, member: Member, db: DbSession
) -> LookupResponse:
    try:
        subject, last4, details = merchant.lookup(db, member, body.code)
    except lifecycle.MerchantError as error:
        raise _refuse(error) from None
    return LookupResponse(
        subject=subject.kind,
        code_last4=last4,
        product_name=subject.product.name,
        brand=subject.product.brand,
        size=subject.product.size,
        batch_number=subject.batch.batch_number,
        expiry_date=subject.batch.expiry_date,
        packs=len(subject.units),
        recalled=subject.recalled,
        **details,
    )


@router.post("/merchant/events")
def record_event(
    company_id: uuid.UUID, body: EventRequest, member: Member, db: DbSession
) -> EventResponse:
    try:
        result = lifecycle.record_merchant_event(
            db,
            member,
            body.code,
            body.event_type,
            to_company_id=body.to_company_id,
            reason=body.reason,
        )
    except lifecycle.MerchantError as error:
        raise _refuse(error) from None
    return EventResponse(
        event_type=result.event_type,
        subject=result.subject,
        packs=result.units,
        status_after=result.status_after,
        notes=result.notes,
    )


@router.get("/merchant/destinations")
def destinations(company_id: uuid.UUID, member: Member, db: DbSession) -> list[DestinationRead]:
    try:
        found = merchant.destinations(db, member)
    except lifecycle.MerchantError as error:
        raise _refuse(error) from None
    return [DestinationRead(company_id=c.company_id, display_name=c.display_name) for c in found]


def _member_read(member: CompanyMember, user) -> MemberRead:
    return MemberRead(
        member_id=member.member_id,
        email=user.email,
        display_name=user.display_name,
        role=member.role,
        membership_status=member.membership_status,
    )


@router.get("/members")
def list_members(company_id: uuid.UUID, owner: Owner, db: DbSession) -> list[MemberRead]:
    return [_member_read(m, u) for m, u in members.list_members(db, owner)]


@router.post("/members", status_code=201)
def add_staff(
    company_id: uuid.UUID, body: AddStaffRequest, owner: Owner, db: DbSession
) -> MemberRead:
    try:
        return _member_read(*members.add_staff(db, owner, body.email))
    except members.MemberError as error:
        raise _refuse(error) from None


@router.post("/members/{member_id}/deactivate")
def deactivate_staff(
    company_id: uuid.UUID, member_id: uuid.UUID, owner: Owner, db: DbSession
) -> MemberRead:
    try:
        return _member_read(*members.deactivate_staff(db, owner, member_id))
    except members.MemberError as error:
        raise _refuse(error) from None
