"""Company catalogue: products, batches, and claimed credentials (docs/DECISIONS.md D61-D64).

- Approved companies publish products and batches directly; they are live in lookups at once.
- Codes are stored normalised (trimmed, upper-case) so lookups match them exactly.
- Credentials are claims: PENDING_REVIEW and invisible to lookups until an admin approves.
- Editing published products is done through change notices (next phase), not here.
"""

import uuid
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    AppUser,
    Company,
    CompanyMember,
    CredentialRecord,
    Product,
    ProductBatch,
    RegulatoryAgency,
)
from app.models.base import utc_now
from app.models.enums import (
    CompanyReviewStatus,
    CredentialStatus,
    ProductStatus,
    ReviewStatus,
)
from app.schemas.catalogue import (
    AdminCredentialRead,
    BatchCreateRequest,
    BatchRead,
    CredentialCreateRequest,
    CredentialDecision,
    CredentialRead,
    ProductCreateRequest,
    ProductRead,
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
from app.services.lookup import normalize_code

COMPANY_CLAIM_PROVENANCE = (
    "Entered by the company as a claim. Reviewed by a FoodLens admin for the demo database only; "
    "not checked with any regulator."
)


class DuplicateCodeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownAgencyError(Exception):
    pass


def _approved_company(db: Session, member: CompanyMember) -> Company:
    company = get_company(db, member.company_id)
    if company.review_status != CompanyReviewStatus.APPROVED:
        raise CompanyNotApprovedError
    return company


def _own_product(db: Session, member: CompanyMember, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.company_id != member.company_id:
        raise NotFoundError  # another company's product looks the same as a missing one
    return product


# --- Create ---------------------------------------------------------------------------------


def add_product(db: Session, member: CompanyMember, data: ProductCreateRequest) -> Product:
    _approved_company(db, member)
    code = normalize_code(data.product_code)
    taken = db.exec(select(Product).where(func.upper(Product.product_code) == code)).first()
    if taken is not None:
        raise DuplicateCodeError("This product code is already in the FoodLens demo catalogue")

    product = Product(
        company_id=member.company_id,
        product_code=code,
        name=data.name,
        brand=data.brand,
        category=data.category,
        package_size=data.package_size or None,
        manufacturer_name=data.manufacturer_name,
        label_information=data.label_information or None,
        status=ProductStatus.PUBLISHED,  # live at once for approved companies (D61)
    )
    db.add(product)
    db.flush()
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product",
        entity_id=product.product_id,
        action="published",
        new_values={"product_code": code, "name": product.name},
    )
    db.commit()
    db.refresh(product)
    return product


def add_batch(
    db: Session, member: CompanyMember, product_id: uuid.UUID, data: BatchCreateRequest
) -> ProductBatch:
    _approved_company(db, member)
    product = _own_product(db, member, product_id)
    number = normalize_code(data.batch_number)
    taken = db.exec(
        select(ProductBatch).where(
            ProductBatch.product_id == product.product_id,
            func.upper(ProductBatch.batch_number) == number,
        )
    ).first()
    if taken is not None:
        raise DuplicateCodeError("This batch number already exists for this product")

    # APPROVED with no reviewer means "published by the company" (D62).
    batch = ProductBatch(
        product_id=product.product_id,
        batch_number=number,
        production_date=data.production_date,
        expiry_date=data.expiry_date,
        review_status=ReviewStatus.APPROVED,
    )
    db.add(batch)
    db.flush()
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="product_batch",
        entity_id=batch.batch_id,
        action="published",
        new_values={"product_code": product.product_code, "batch_number": number},
    )
    db.commit()
    db.refresh(batch)
    return batch


def add_credential(
    db: Session,
    member: CompanyMember,
    product_id: uuid.UUID,
    data: CredentialCreateRequest,
    today: date,
) -> CredentialRecord:
    """Record a credential claim: INACTIVE and PENDING_REVIEW, hidden from lookups. Only admin
    approval makes it ACTIVE."""
    _approved_company(db, member)
    product = _own_product(db, member, product_id)
    if db.get(RegulatoryAgency, data.agency_id) is None:
        raise UnknownAgencyError
    reference = normalize_code(data.reference_number)
    taken = db.exec(
        select(CredentialRecord).where(
            CredentialRecord.agency_id == data.agency_id,
            func.upper(CredentialRecord.reference_number) == reference,
        )
    ).first()
    if taken is not None:
        raise DuplicateCodeError("This reference number is already recorded for that agency")

    credential = CredentialRecord(
        product_id=product.product_id,
        agency_id=data.agency_id,
        reference_number=reference,
        # A claim is never active until an admin approves it (D67).
        status=CredentialStatus.INACTIVE,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        provenance=COMPANY_CLAIM_PROVENANCE,
        checked_on=today,
        submitted_by_user_id=member.user_id,
        review_status=ReviewStatus.PENDING_REVIEW,
    )
    db.add(credential)
    db.flush()
    audit.record(
        db,
        actor_user_id=member.user_id,
        entity_type="credential_record",
        entity_id=credential.credential_id,
        action="claimed",
        new_values={"reference_number": reference, "review_status": credential.review_status},
    )
    db.commit()
    db.refresh(credential)
    return credential


# --- Reads ----------------------------------------------------------------------------------


def list_agencies(db: Session) -> list[RegulatoryAgency]:
    return list(db.exec(select(RegulatoryAgency).order_by(RegulatoryAgency.name)).all())


def _credential_read(credential: CredentialRecord, agency: RegulatoryAgency) -> CredentialRead:
    return CredentialRead(
        credential_id=credential.credential_id,
        agency=agency.name,
        scheme=agency.scheme,
        reference_number=credential.reference_number,
        status=credential.status,
        valid_from=credential.valid_from,
        valid_until=credential.valid_until,
        data_mode=credential.data_mode,
        review_status=credential.review_status,
        reviewed_at=credential.reviewed_at,
        review_note=credential.review_note,
    )


def company_catalogue(db: Session, company_id: uuid.UUID) -> list[ProductRead]:
    products = db.exec(
        select(Product).where(Product.company_id == company_id).order_by(Product.product_code)
    ).all()
    result = []
    for product in products:
        batches = db.exec(
            select(ProductBatch)
            .where(ProductBatch.product_id == product.product_id)
            .order_by(ProductBatch.batch_number)
        ).all()
        credentials = db.exec(
            select(CredentialRecord, RegulatoryAgency)
            .join(RegulatoryAgency, RegulatoryAgency.agency_id == CredentialRecord.agency_id)
            .where(CredentialRecord.product_id == product.product_id)
            .order_by(CredentialRecord.reference_number)
        ).all()
        result.append(
            ProductRead(
                **product.model_dump(),
                batches=[BatchRead.model_validate(b, from_attributes=True) for b in batches],
                credentials=[_credential_read(c, a) for c, a in credentials],
            )
        )
    return result


def list_credentials(db: Session, status: ReviewStatus | None) -> list[AdminCredentialRead]:
    statement = (
        select(CredentialRecord, RegulatoryAgency, Product, Company)
        .join(RegulatoryAgency, RegulatoryAgency.agency_id == CredentialRecord.agency_id)
        .join(Product, Product.product_id == CredentialRecord.product_id)
        .join(Company, Company.company_id == Product.company_id)
        .order_by(CredentialRecord.created_at)
    )
    if status is not None:
        statement = statement.where(CredentialRecord.review_status == status)
    rows = db.exec(statement).all()
    return [admin_credential_read(db, *row) for row in rows]


def admin_credential_read(
    db: Session,
    credential: CredentialRecord,
    agency: RegulatoryAgency,
    product: Product,
    company: Company,
) -> AdminCredentialRead:
    submitter = (
        db.get(AppUser, credential.submitted_by_user_id)
        if credential.submitted_by_user_id
        else None
    )
    return AdminCredentialRead(
        **_credential_read(credential, agency).model_dump(),
        company_id=company.company_id,
        company_display_name=company.display_name,
        product_code=product.product_code,
        product_name=product.name,
        submitted_by_display_name=submitter.display_name if submitter else None,
        created_at=credential.created_at,
    )


# --- Admin decision -------------------------------------------------------------------------


def decide_credential(
    db: Session,
    admin: AppUser,
    credential_id: uuid.UUID,
    decision: CredentialDecision,
    note: str | None,
) -> AdminCredentialRead:
    credential = db.get(CredentialRecord, credential_id)
    if credential is None:
        raise NotFoundError
    product = db.get(Product, credential.product_id)
    company = get_company(db, product.company_id)
    if active_membership(db, user_id=admin.user_id, company_id=company.company_id):
        raise ConflictOfInterestError
    if credential.review_status != ReviewStatus.PENDING_REVIEW:
        raise InvalidTransitionError(
            f"Cannot {decision.lower()} a credential that is {credential.review_status}."
        )

    new_status = (
        ReviewStatus.APPROVED if decision == CredentialDecision.APPROVE else ReviewStatus.REJECTED
    )
    credential.review_status = new_status
    if new_status == ReviewStatus.APPROVED:
        credential.status = CredentialStatus.ACTIVE
    credential.reviewed_by_user_id = admin.user_id
    credential.reviewed_at = utc_now()
    credential.review_note = note or None
    db.add(credential)
    audit.record(
        db,
        actor_user_id=admin.user_id,
        entity_type="credential_record",
        entity_id=credential.credential_id,
        action=f"review:{decision.lower()}",
        old_values={"review_status": ReviewStatus.PENDING_REVIEW},
        new_values={"review_status": new_status, "review_note": credential.review_note},
    )
    db.commit()
    db.refresh(credential)
    agency = db.get(RegulatoryAgency, credential.agency_id)
    return admin_credential_read(db, credential, agency, product, company)
