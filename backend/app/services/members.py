"""Staff management for the owner (D106). One company per user (D6): an owner can add only an
existing registered user who has no company, or re-activate their own earlier staff member."""

import uuid

from sqlmodel import Session, select

from app.models import AppUser, CompanyMember
from app.models.enums import MemberRole, MembershipStatus
from app.services import audit
from app.services.auth import normalize_email

MSG_NO_USER = "No FoodLens account uses that email. Ask them to create an account first."
MSG_HAS_COMPANY = "That person already belongs to a company."
MSG_ALREADY_STAFF = "That person is already on your team."
MSG_NOT_FOUND = "Team member not found."
MSG_OWNER = "The owner can't be deactivated."


class MemberError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_members(db: Session, owner: CompanyMember) -> list[tuple[CompanyMember, AppUser]]:
    rows = db.exec(
        select(CompanyMember, AppUser)
        .join(AppUser, AppUser.user_id == CompanyMember.user_id)
        .where(CompanyMember.company_id == owner.company_id)
        .order_by(CompanyMember.created_at)
    ).all()
    return list(rows)


def add_staff(db: Session, owner: CompanyMember, email: str) -> tuple[CompanyMember, AppUser]:
    user = db.exec(select(AppUser).where(AppUser.email == normalize_email(email))).first()
    if user is None:
        raise MemberError(MSG_NO_USER, 404)
    existing = db.exec(select(CompanyMember).where(CompanyMember.user_id == user.user_id)).first()
    if existing is not None:
        if existing.company_id != owner.company_id:
            raise MemberError(MSG_HAS_COMPANY, 409)
        if existing.membership_status == MembershipStatus.ACTIVE:
            raise MemberError(MSG_ALREADY_STAFF, 409)
        existing.membership_status = MembershipStatus.ACTIVE
        member = existing
        action = "REACTIVATE_STAFF"
    else:
        member = CompanyMember(
            user_id=user.user_id, company_id=owner.company_id, role=MemberRole.STAFF
        )
        action = "ADD_STAFF"
    db.add(member)
    db.flush()
    audit.record(
        db,
        actor_user_id=owner.user_id,
        entity_type="company_member",
        entity_id=member.member_id,
        action=action,
        new_values={"membership_status": MembershipStatus.ACTIVE},
    )
    db.commit()
    return member, user


def deactivate_staff(
    db: Session, owner: CompanyMember, member_id: uuid.UUID
) -> tuple[CompanyMember, AppUser]:
    member = db.get(CompanyMember, member_id)
    if member is None or member.company_id != owner.company_id:
        raise MemberError(MSG_NOT_FOUND, 404)
    if member.role == MemberRole.OWNER:
        raise MemberError(MSG_OWNER, 409)
    old = member.membership_status
    member.membership_status = MembershipStatus.INACTIVE
    db.add(member)
    audit.record(
        db,
        actor_user_id=owner.user_id,
        entity_type="company_member",
        entity_id=member.member_id,
        action="DEACTIVATE_STAFF",
        old_values={"membership_status": old},
        new_values={"membership_status": MembershipStatus.INACTIVE},
    )
    db.commit()
    return member, db.get(AppUser, member.user_id)
