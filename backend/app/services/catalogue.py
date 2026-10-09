"""Company catalogue: products and batches (docs/DECISIONS.md D61-D62, D81).

- Approved companies publish products and batches directly; they are live in lookups at once.
- Product codes and batch numbers are stored normalised so lookups match them exactly.
- A product carries the registration number printed on its pack. Companies cannot create or
  change register records; registration status comes only from the simulated register (D80).
- Editing published products is done through change notices, not here.
"""

import uuid

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Company, CompanyMember, Product, ProductBatch
from app.models.enums import CompanyReviewStatus, ProductStatus, ReviewStatus
from app.schemas.catalogue import (
    BatchCreateRequest,
    BatchRead,
    ProductCreateRequest,
    ProductRead,
)
from app.services import audit
from app.services.companies import CompanyNotApprovedError, NotFoundError, get_company
from app.services.lookup import normalize_code
from app.services.register import (
    is_valid_registration_number,
    normalize_registration_number,
)


class DuplicateCodeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRegistrationNumberError(Exception):
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


def clean_registration_number(value: str | None) -> str | None:
    """Normalise a company-entered registration number; reject malformed ones."""
    number = normalize_registration_number(value)
    if number is not None and not is_valid_registration_number(number):
        raise InvalidRegistrationNumberError
    return number


# --- Create ---------------------------------------------------------------------------------


def add_product(db: Session, member: CompanyMember, data: ProductCreateRequest) -> Product:
    _approved_company(db, member)
    code = normalize_code(data.product_code)
    registration_number = clean_registration_number(data.registration_number)
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
        registration_number=registration_number,
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
        new_values={
            "product_code": code,
            "name": product.name,
            "registration_number": registration_number,
        },
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


# --- Reads ----------------------------------------------------------------------------------


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
        result.append(
            ProductRead(
                **product.model_dump(),
                batches=[BatchRead.model_validate(b, from_attributes=True) for b in batches],
            )
        )
    return result
