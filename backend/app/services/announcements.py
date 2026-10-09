"""Product announcements ("POPs", CLAUDE.md rule 5 exception, docs/DECISIONS.md D75-D79).

- Approved companies post short messages on their own products; they go live at once.
- Shown on lookup results labelled "Message from the company — not reviewed by FoodLens".
- Never change product data. The company can withdraw its own; admins can hide any.
- Text with the whole words "safe" or "unsafe" is refused, so a company cannot claim its
  product is safe or unsafe (rule 1). Warnings such as "beware of fake versions" are allowed.
"""

import re
import uuid

from sqlmodel import Session, select

from app.models import AppUser, Company, CompanyMember, Product, ProductAnnouncement
from app.models.base import utc_now
from app.models.enums import AnnouncementStatus, CompanyReviewStatus
from app.schemas.announcement import (
    AdminAnnouncementRead,
    AnnouncementCreateRequest,
    AnnouncementRead,
    LookupAnnouncement,
)
from app.services import audit
from app.services.auth import active_membership
from app.services.companies import (
    CompanyNotApprovedError,
    ConflictOfInterestError,
    InvalidTransitionError,
    NotFoundError,
    get_company,
)

MAX_SHOWN_IN_LOOKUP = 3
# Whole words only: "safety", "safely", "fake", "counterfeit" are allowed (D77).
_BANNED_WORDS = re.compile(r"\b(safe|unsafe)\b", re.IGNORECASE)


class SafetyClaimError(Exception):
    pass


def post_announcement(
    db: Session, member: CompanyMember, product_id: uuid.UUID, data: AnnouncementCreateRequest
) -> ProductAnnouncement:
    company = get_company(db, member.company_id)
    if company.review_status != CompanyReviewStatus.APPROVED:
        raise CompanyNotApprovedError
    product = db.get(Product, product_id)
    if product is None or product.company_id != member.company_id:
        raise NotFoundError
    if _BANNED_WORDS.search(data.title) or _BANNED_WORDS.search(data.message):
        raise SafetyClaimError

    announcement = ProductAnnouncement(
        product_id=product.product_id,
        title=data.title,
        message=data.message,
        status=AnnouncementStatus.LIVE,
        created_by_user_id=member.user_id,
    )
    db.add(announcement)
    db.flush()
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product_announcement",
        entity_id=announcement.announcement_id,
        action="posted",
        new_values={"title": announcement.title, "product_code": product.product_code},
    )
    db.commit()
    db.refresh(announcement)
    return announcement


def _hide(db: Session, announcement: ProductAnnouncement, actor: AppUser | CompanyMember,
          action: str, reason: str | None) -> ProductAnnouncement:  # fmt: skip
    if announcement.status != AnnouncementStatus.LIVE:
        raise InvalidTransitionError("This announcement is already hidden.")
    announcement.status = AnnouncementStatus.HIDDEN
    announcement.hidden_by_user_id = actor.user_id
    announcement.hidden_at = utc_now()
    db.add(announcement)
    audit.record(
        db,
        actor_user_id=actor.user_id,
        entity_type="product_announcement",
        entity_id=announcement.announcement_id,
        action=action,
        old_values={"status": AnnouncementStatus.LIVE},
        new_values={"status": AnnouncementStatus.HIDDEN, "reason": reason},
    )
    db.commit()
    db.refresh(announcement)
    return announcement


def withdraw_announcement(
    db: Session, member: CompanyMember, announcement_id: uuid.UUID
) -> ProductAnnouncement:
    announcement = db.get(ProductAnnouncement, announcement_id)
    product = db.get(Product, announcement.product_id) if announcement else None
    if product is None or product.company_id != member.company_id:
        raise NotFoundError
    return _hide(db, announcement, member, "withdrawn", None)


def admin_hide_announcement(
    db: Session, admin: AppUser, announcement_id: uuid.UUID, reason: str | None
) -> ProductAnnouncement:
    announcement = db.get(ProductAnnouncement, announcement_id)
    if announcement is None:
        raise NotFoundError
    product = db.get(Product, announcement.product_id)
    if active_membership(db, user_id=admin.user_id, company_id=product.company_id):
        raise ConflictOfInterestError
    return _hide(db, announcement, admin, "hidden_by_admin", reason)


# --- Reads ----------------------------------------------------------------------------------


def for_lookup(db: Session, product_id: uuid.UUID) -> list[LookupAnnouncement]:
    rows = db.exec(
        select(ProductAnnouncement)
        .where(
            ProductAnnouncement.product_id == product_id,
            ProductAnnouncement.status == AnnouncementStatus.LIVE,
        )
        .order_by(ProductAnnouncement.created_at.desc())
        .limit(MAX_SHOWN_IN_LOOKUP)
    ).all()
    return [
        LookupAnnouncement(title=a.title, message=a.message, posted_at=a.created_at) for a in rows
    ]


def announcement_read(db: Session, announcement: ProductAnnouncement) -> AnnouncementRead:
    product = db.get(Product, announcement.product_id)
    return AnnouncementRead(
        announcement_id=announcement.announcement_id,
        product_id=product.product_id,
        product_code=product.product_code,
        product_name=product.name,
        title=announcement.title,
        message=announcement.message,
        status=announcement.status,
        created_at=announcement.created_at,
        hidden_at=announcement.hidden_at,
    )


def company_announcements(db: Session, company_id: uuid.UUID) -> list[ProductAnnouncement]:
    return list(
        db.exec(
            select(ProductAnnouncement)
            .join(Product, Product.product_id == ProductAnnouncement.product_id)
            .where(Product.company_id == company_id)
            .order_by(ProductAnnouncement.created_at.desc())
        ).all()
    )


def list_announcements(
    db: Session, status: AnnouncementStatus | None
) -> list[AdminAnnouncementRead]:
    statement = (
        select(ProductAnnouncement, Product, Company)
        .join(Product, Product.product_id == ProductAnnouncement.product_id)
        .join(Company, Company.company_id == Product.company_id)
        .order_by(ProductAnnouncement.created_at.desc())
    )
    if status is not None:
        statement = statement.where(ProductAnnouncement.status == status)
    result = []
    for announcement, _, company in db.exec(statement).all():
        author = db.get(AppUser, announcement.created_by_user_id)
        hider = (
            db.get(AppUser, announcement.hidden_by_user_id)
            if announcement.hidden_by_user_id
            else None
        )
        result.append(
            AdminAnnouncementRead(
                **announcement_read(db, announcement).model_dump(),
                company_id=company.company_id,
                company_display_name=company.display_name,
                created_by_display_name=author.display_name if author else None,
                hidden_by_display_name=hider.display_name if hider else None,
            )
        )
    return result
