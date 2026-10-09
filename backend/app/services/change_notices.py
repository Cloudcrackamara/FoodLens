"""Change notices: proposed edits to a company's published products and batches.

Rules (CLAUDE.md rule 5, docs/DECISIONS.md D68-D74):
- A notice records structured field changes with a snapshot of each current value.
  Submitting it never touches published data.
- Admins approve, reject, or request clarification; never on their own company.
- Approval re-checks that live values still match the snapshots, then applies every change
  in one transaction and stores the replaced values (applied_old_value) plus an audit entry.
- Attachments: PDF/PNG/JPEG checked by extension and file signature, max 5 MB, max 5 per
  notice, stored under random keys in a private folder (never served statically).
"""

import re
import secrets
import uuid
from datetime import date
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError
from sqlmodel import Session, select

from app.models import (
    AppUser,
    ChangeNotice,
    ChangeNoticeField,
    Company,
    CompanyMember,
    NoticeAttachment,
    Product,
    ProductBatch,
)
from app.models.base import utc_now
from app.models.change import MAX_ATTACHMENT_BYTES
from app.models.enums import AttachmentMimeType, ChangeNoticeStatus
from app.schemas.change_notice import (
    AdminChangeNoticeRead,
    AttachmentRead,
    BatchChanges,
    ChangeNoticeCreateRequest,
    ChangeNoticeRead,
    NoticeDecision,
    NoticeFieldRead,
    ProductChanges,
)
from app.services import audit
from app.services.auth import active_membership
from app.services.companies import (
    ConflictOfInterestError,
    InvalidTransitionError,
    NotFoundError,
)
from app.services.register import is_valid_registration_number, normalize_registration_number

MAX_ATTACHMENTS_PER_NOTICE = 5
OPEN_STATUSES = {ChangeNoticeStatus.PENDING_REVIEW, ChangeNoticeStatus.CLARIFICATION_REQUESTED}

# Extension -> (mime type, file signature). The file must match both.
_ALLOWED_FILES = {
    ".pdf": (AttachmentMimeType.PDF, b"%PDF-"),
    ".png": (AttachmentMimeType.PNG, b"\x89PNG\r\n\x1a\n"),
    ".jpg": (AttachmentMimeType.JPEG, b"\xff\xd8\xff"),
    ".jpeg": (AttachmentMimeType.JPEG, b"\xff\xd8\xff"),
}


class InvalidChangesError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class StaleNoticeError(Exception):
    """The live record changed after the notice was submitted."""


class InvalidAttachmentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AttachmentTooLargeError(Exception):
    pass


# --- Values are stored as text: strings as-is, dates as ISO, empty as None -------------------


def _to_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _from_text(field: str, value: str | None) -> object:
    if value is None:
        return None
    if field in BatchChanges.model_fields:
        return date.fromisoformat(value)
    return value


# --- Submit ---------------------------------------------------------------------------------


def _target(
    db: Session, member: CompanyMember, data: ChangeNoticeCreateRequest
) -> tuple[Product, ProductBatch | None]:
    if data.batch_id is not None:
        batch = db.get(ProductBatch, data.batch_id)
        product = db.get(Product, batch.product_id) if batch else None
    else:
        batch = None
        product = db.get(Product, data.product_id)
    if product is None or product.company_id != member.company_id:
        raise NotFoundError  # another company's record looks the same as a missing one
    return product, batch


def submit_notice(
    db: Session, member: CompanyMember, data: ChangeNoticeCreateRequest
) -> ChangeNotice:
    product, batch = _target(db, member, data)
    target = batch if batch is not None else product
    schema = BatchChanges if batch is not None else ProductChanges
    try:
        changes = schema.model_validate(data.proposed_changes)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "proposed_changes"
        raise InvalidChangesError(f"{where}: {first['msg']}") from None

    if "registration_number" in changes.model_fields_set:
        number = normalize_registration_number(changes.registration_number)
        if number is not None and not is_valid_registration_number(number):
            raise InvalidChangesError("registration_number: use letters, numbers, and - . / _")
        changes.registration_number = number

    rows = []
    for field in sorted(changes.model_fields_set):
        current = _to_text(getattr(target, field))
        proposed = _to_text(getattr(changes, field))
        if current != proposed:
            rows.append((field, current, proposed))
    if not rows:
        raise InvalidChangesError("The proposed values are the same as the current ones")
    if batch is not None:
        merged = {f: getattr(batch, f) for f in ("production_date", "expiry_date")}
        merged |= {f: getattr(changes, f) for f in changes.model_fields_set}
        if merged["production_date"] and merged["expiry_date"]:
            if merged["expiry_date"] < merged["production_date"]:
                raise InvalidChangesError("Expiry date cannot be before the production date")

    notice = ChangeNotice(
        company_id=member.company_id,
        product_id=product.product_id if batch is None else None,
        batch_id=batch.batch_id if batch is not None else None,
        change_type=data.change_type,
        reason=data.reason,
        effective_date=data.effective_date,
        submitted_by_user_id=member.user_id,
    )
    db.add(notice)
    db.flush()
    for field, current, proposed in rows:
        db.add(
            ChangeNoticeField(
                notice_id=notice.notice_id,
                field_name=field,
                current_value=current,
                proposed_value=proposed,
            )
        )
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="change_notice",
        entity_id=notice.notice_id,
        action="submitted",
        new_values={"fields": [r[0] for r in rows], "review_status": notice.review_status},
    )
    db.commit()
    db.refresh(notice)
    return notice


def respond_to_clarification(
    db: Session, member: CompanyMember, notice_id: uuid.UUID, message: str
) -> ChangeNotice:
    """The company answers a clarification request; the notice returns to PENDING_REVIEW.
    To change the proposed values, submit a new notice instead."""
    notice = _own_notice(db, member, notice_id)
    if notice.review_status != ChangeNoticeStatus.CLARIFICATION_REQUESTED:
        raise InvalidTransitionError("Only notices awaiting clarification can be answered.")
    notice.reason = (
        f"{notice.reason}\n\nResponse to clarification ({utc_now():%Y-%m-%d}): {message}"
    )
    notice.review_status = ChangeNoticeStatus.PENDING_REVIEW
    db.add(notice)
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="change_notice",
        entity_id=notice.notice_id,
        action="clarification_answered",
        old_values={"review_status": ChangeNoticeStatus.CLARIFICATION_REQUESTED},
        new_values={"review_status": ChangeNoticeStatus.PENDING_REVIEW},
    )
    db.commit()
    db.refresh(notice)
    return notice


# --- Attachments ----------------------------------------------------------------------------


def _safe_filename(name: str | None) -> str:
    base = Path(name or "attachment").name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip(" .") or "attachment"
    return cleaned[:100]


def add_attachment(
    db: Session,
    member: CompanyMember,
    notice_id: uuid.UUID,
    filename: str | None,
    stream: BinaryIO,
    storage_dir: Path,
) -> NoticeAttachment:
    notice = _own_notice(db, member, notice_id)
    if notice.review_status not in OPEN_STATUSES:
        raise InvalidTransitionError("Attachments can only be added while the notice is open.")
    count = len(
        db.exec(select(NoticeAttachment).where(NoticeAttachment.notice_id == notice_id)).all()
    )
    if count >= MAX_ATTACHMENTS_PER_NOTICE:
        raise InvalidAttachmentError(
            f"A notice can have at most {MAX_ATTACHMENTS_PER_NOTICE} attachments"
        )

    extension = Path(filename or "").suffix.lower()
    if extension not in _ALLOWED_FILES:
        raise InvalidAttachmentError("Only PDF, PNG, or JPG files are accepted")
    mime_type, signature = _ALLOWED_FILES[extension]

    content = stream.read(MAX_ATTACHMENT_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise AttachmentTooLargeError
    if not content:
        raise InvalidAttachmentError("The file is empty")
    if not content.startswith(signature):
        raise InvalidAttachmentError("The file content does not match its PDF, PNG, or JPG type")

    storage_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(16)
    path = storage_dir / key
    path.write_bytes(content)
    try:
        attachment = NoticeAttachment(
            notice_id=notice.notice_id,
            storage_key=key,
            original_filename=_safe_filename(filename),
            mime_type=mime_type,
            size_bytes=len(content),
        )
        db.add(attachment)
        audit.record(
            db,
            actor_user_id=member.user_id,
            entity_type="change_notice",
            entity_id=notice.notice_id,
            action="attachment_added",
            new_values={"mime_type": mime_type, "size_bytes": len(content)},
        )
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


def attachment_for_member(
    db: Session, member: CompanyMember, attachment_id: uuid.UUID
) -> NoticeAttachment:
    attachment = db.get(NoticeAttachment, attachment_id)
    if attachment is None:
        raise NotFoundError
    _own_notice(db, member, attachment.notice_id)
    return attachment


def attachment_for_admin(db: Session, attachment_id: uuid.UUID) -> NoticeAttachment:
    attachment = db.get(NoticeAttachment, attachment_id)
    if attachment is None:
        raise NotFoundError
    return attachment


def attachment_path(storage_dir: Path, attachment: NoticeAttachment) -> Path:
    path = (storage_dir / attachment.storage_key).resolve()
    if path.parent != storage_dir.resolve() or not path.is_file():
        raise NotFoundError
    return path


# --- Admin decision -------------------------------------------------------------------------


def decide_notice(
    db: Session,
    admin: AppUser,
    notice_id: uuid.UUID,
    decision: NoticeDecision,
    note: str | None,
) -> ChangeNotice:
    notice = db.get(ChangeNotice, notice_id)
    if notice is None:
        raise NotFoundError
    if active_membership(db, user_id=admin.user_id, company_id=notice.company_id):
        raise ConflictOfInterestError

    allowed = {
        NoticeDecision.APPROVE: {ChangeNoticeStatus.PENDING_REVIEW},
        NoticeDecision.REQUEST_CLARIFICATION: {ChangeNoticeStatus.PENDING_REVIEW},
        NoticeDecision.REJECT: OPEN_STATUSES,
    }[decision]
    if notice.review_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot {decision.lower().replace('_', ' ')} a notice that is {notice.review_status}."
        )
    if decision == NoticeDecision.REQUEST_CLARIFICATION and not note:
        raise InvalidChangesError("Say what needs clarifying in the note")

    old_status = notice.review_status
    try:
        if decision == NoticeDecision.APPROVE:
            _apply(db, admin, notice)
        notice.review_status = {
            NoticeDecision.APPROVE: ChangeNoticeStatus.APPROVED,
            NoticeDecision.REJECT: ChangeNoticeStatus.REJECTED,
            NoticeDecision.REQUEST_CLARIFICATION: ChangeNoticeStatus.CLARIFICATION_REQUESTED,
        }[decision]
        notice.reviewed_by_user_id = admin.user_id
        notice.reviewed_at = utc_now()
        notice.review_note = note or None
        db.add(notice)
        audit.record(
            db,
            actor_user_id=admin.user_id,
            entity_type="change_notice",
            entity_id=notice.notice_id,
            action=f"review:{decision.lower()}",
            old_values={"review_status": old_status},
            new_values={"review_status": notice.review_status, "review_note": notice.review_note},
        )
        db.commit()  # the change and the decision are saved together, or not at all
    except Exception:
        db.rollback()
        raise
    db.refresh(notice)
    return notice


def _apply(db: Session, admin: AppUser, notice: ChangeNotice) -> None:
    """Apply the notice's fields to the live record. The caller commits."""
    if notice.batch_id is not None:
        target = db.get(ProductBatch, notice.batch_id, with_for_update=True)
        entity_type = "product_batch"
    else:
        target = db.get(Product, notice.product_id, with_for_update=True)
        entity_type = "product"
    fields = db.exec(
        select(ChangeNoticeField).where(ChangeNoticeField.notice_id == notice.notice_id)
    ).all()

    old_values, new_values = {}, {}
    for row in fields:
        live = _to_text(getattr(target, row.field_name))
        if live != row.current_value:
            raise StaleNoticeError
        setattr(target, row.field_name, _from_text(row.field_name, row.proposed_value))
        row.applied_old_value = live
        old_values[row.field_name] = live
        new_values[row.field_name] = row.proposed_value
        db.add(row)

    if isinstance(target, ProductBatch) and target.production_date and target.expiry_date:
        if target.expiry_date < target.production_date:
            raise InvalidChangesError("Expiry date cannot be before the production date")

    db.add(target)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type=entity_type,
        entity_id=target.batch_id if entity_type == "product_batch" else target.product_id,
        action="change_notice_applied",
        old_values=old_values,
        new_values=new_values | {"notice_id": str(notice.notice_id)},
    )


# --- Reads ----------------------------------------------------------------------------------


def _own_notice(db: Session, member: CompanyMember, notice_id: uuid.UUID) -> ChangeNotice:
    notice = db.get(ChangeNotice, notice_id)
    if notice is None or notice.company_id != member.company_id:
        raise NotFoundError
    return notice


def notice_read(db: Session, notice: ChangeNotice) -> ChangeNoticeRead:
    batch = db.get(ProductBatch, notice.batch_id) if notice.batch_id else None
    product = db.get(Product, batch.product_id if batch else notice.product_id)
    fields = db.exec(
        select(ChangeNoticeField)
        .where(ChangeNoticeField.notice_id == notice.notice_id)
        .order_by(ChangeNoticeField.field_name)
    ).all()
    attachments = db.exec(
        select(NoticeAttachment)
        .where(NoticeAttachment.notice_id == notice.notice_id)
        .order_by(NoticeAttachment.created_at)
    ).all()
    return ChangeNoticeRead(
        notice_id=notice.notice_id,
        company_id=notice.company_id,
        target_type="batch" if batch else "product",
        product_id=product.product_id,
        product_code=product.product_code,
        product_name=product.name,
        batch_id=batch.batch_id if batch else None,
        batch_number=batch.batch_number if batch else None,
        change_type=notice.change_type,
        reason=notice.reason,
        effective_date=notice.effective_date,
        review_status=notice.review_status,
        reviewed_at=notice.reviewed_at,
        review_note=notice.review_note,
        created_at=notice.created_at,
        fields=[NoticeFieldRead.model_validate(f, from_attributes=True) for f in fields],
        attachments=[AttachmentRead.model_validate(a, from_attributes=True) for a in attachments],
    )


def admin_notice_read(db: Session, notice: ChangeNotice) -> AdminChangeNoticeRead:
    company = db.get(Company, notice.company_id)
    submitter = db.get(AppUser, notice.submitted_by_user_id)
    reviewer = db.get(AppUser, notice.reviewed_by_user_id) if notice.reviewed_by_user_id else None
    return AdminChangeNoticeRead(
        **notice_read(db, notice).model_dump(),
        company_display_name=company.display_name,
        submitted_by_display_name=submitter.display_name if submitter else None,
        reviewed_by_display_name=reviewer.display_name if reviewer else None,
    )


def company_notices(db: Session, company_id: uuid.UUID) -> list[ChangeNotice]:
    return list(
        db.exec(
            select(ChangeNotice)
            .where(ChangeNotice.company_id == company_id)
            .order_by(ChangeNotice.created_at.desc())
        ).all()
    )


def list_notices(db: Session, status: ChangeNoticeStatus | None) -> list[ChangeNotice]:
    statement = select(ChangeNotice).order_by(ChangeNotice.created_at)
    if status is not None:
        statement = statement.where(ChangeNotice.review_status == status)
    return list(db.exec(statement).all())
