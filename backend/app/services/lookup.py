"""Consumer registration lookup against the simulated NAFDAC/SON register (D80-D85).

Input: the registration number printed on the pack (required) and the batch number (optional).
Exactly one primary result, checked in this order:
  1. INSUFFICIENT_OR_AMBIGUOUS         number missing or malformed (or batch malformed)
  2. REGISTRATION_NOT_FOUND            number not in the simulated register
  3. REGISTRATION_EXPIRED_OR_INACTIVE  record inactive or past its expiry date
  4. REGISTRATION_MISMATCH             the entered batch belongs to a FoodLens product whose
                                       number differs, or whose product/company names differ
                                       from the register record
  5. REGISTERED_ACTIVE                 matches an active record
Batch findings (not in the catalogue, expired) are warnings, not results. A mismatch found
alongside an expired record is also a warning.

Wording never says "safe", "genuine", or "verified by NAFDAC"; every response carries
data_mode DEMO and the disclaimer (rules 1-2).
"""

import re
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import BatchScan, Company, Product, ProductBatch
from app.models.enums import (
    CompanyReviewStatus,
    LookupResult,
    ProductStatus,
    ReviewStatus,
)
from app.schemas.lookup import (
    LookupBatch,
    LookupInput,
    LookupMismatch,
    LookupProduct,
    LookupResponse,
    LookupWarning,
    RegisterRecordStatus,
)
from app.services import announcements, register

MAX_CODE_LENGTH = 64
_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 ._/-]*$")

DISCLAIMER = (
    "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. FoodLens compares the number you entered "
    "with a simulated, fictional register held by FoodLens. It is not NAFDAC's or SON's own "
    "system, it is not a laboratory or food-safety test, and a matching number cannot rule out "
    "a copied number on the pack."
)

TITLES = {
    LookupResult.REGISTERED_ACTIVE: "Matches an active record in the simulated register",
    LookupResult.REGISTRATION_NOT_FOUND: "Number not found in the simulated register",
    LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE: (
        "Registration expired or inactive in the simulated register"
    ),
    LookupResult.REGISTRATION_MISMATCH: "Number belongs to a different product or company",
    LookupResult.INSUFFICIENT_OR_AMBIGUOUS: "More details needed",
}

MISSING = "Enter the NAFDAC or SON registration number printed on the pack."
MALFORMED = (
    "The registration or batch number contains characters that are not used in these numbers. "
    "Use only letters, numbers, and - . / _ as printed on the pack."
)
MISMATCH_MESSAGES = {
    "different_registration_number": (
        "The batch number you entered belongs to a product listed in FoodLens under a different "
        "registration number. Check both numbers on the pack."
    ),
    "registered_names_differ": (
        "This number is recorded in the {register} (demo data) for a different product or "
        "company than the product the batch belongs to. Compare the registered names below "
        "with the pack."
    ),
}


def normalize_code(value: str | None) -> str | None:
    """Batch numbers and product codes: trim, collapse inner whitespace, upper-case."""
    if value is None:
        return None
    normalized = " ".join(value.split()).upper()
    return normalized or None


def _is_valid_code(value: str) -> bool:
    return len(value) <= MAX_CODE_LENGTH and bool(_CODE_PATTERN.match(value))


def _visible_batches(batch_number: str):
    """Batches a consumer may see: approved batch, published product, approved company."""
    return (
        select(ProductBatch, Product, Company)
        .join(Product, Product.product_id == ProductBatch.product_id)
        .join(Company, Company.company_id == Product.company_id)
        .where(
            ProductBatch.review_status == ReviewStatus.APPROVED,
            Product.status == ProductStatus.PUBLISHED,
            Company.review_status == CompanyReviewStatus.APPROVED,
            func.upper(ProductBatch.batch_number) == batch_number,
        )
        .order_by(Product.product_code)
    )


def _response(result: LookupResult, message: str, lookup_input: LookupInput, **fields):
    return LookupResponse(
        result=result,
        disclaimer=DISCLAIMER,
        title=TITLES[result],
        message=message,
        input=lookup_input,
        **fields,
    )


def lookup_registration(
    db: Session,
    *,
    registration_number: str | None,
    batch_number: str | None,
    today: date,
) -> tuple[LookupResponse, ProductBatch | None]:
    """Returns the response plus the matched batch (for the anonymised scan log)."""
    number = register.normalize_registration_number(registration_number)
    batch_no = normalize_code(batch_number)
    lookup_input = LookupInput(
        registration_number=number[:MAX_CODE_LENGTH] if number else None,
        batch_number=batch_no[:MAX_CODE_LENGTH] if batch_no else None,
    )
    insufficient = LookupResult.INSUFFICIENT_OR_AMBIGUOUS

    if number is None:
        return _response(insufficient, MISSING, lookup_input), None
    if not register.is_valid_registration_number(number) or (
        batch_no is not None and not _is_valid_code(batch_no)
    ):
        return _response(insufficient, MALFORMED, lookup_input), None

    found = register.find_record(db, number)
    if found is None:
        message = (
            "This number is not in the simulated NAFDAC/SON register (demo data). The demo "
            "register is small and fictional, so this does not show what the real regulator "
            "holds. Check the number on the pack."
        )
        return _response(LookupResult.REGISTRATION_NOT_FOUND, message, lookup_input), None

    record, agency = found
    register_name = register.register_label(agency)
    record_read = register.record_read(record, agency, today)
    warnings: list[LookupWarning] = []

    # --- Batch: which FoodLens product does it belong to? -----------------------------------
    product = company = batch = None
    mismatch_reason = None
    if batch_no is not None:
        rows = db.exec(_visible_batches(batch_no)).all()
        same_number = [
            row for row in rows if (row[1].registration_number or "") == record.registration_number
        ]
        if not rows:
            warnings.append(
                LookupWarning(
                    code="BATCH_NOT_IN_CATALOGUE",
                    message="This batch number is not in the FoodLens demo catalogue.",
                )
            )
        elif not same_number:
            mismatch_reason = "different_registration_number"
            batch, product, company = rows[0]
        else:
            batch, product, company = same_number[0]
            names_match = register.normalize_name(product.name) == register.normalize_name(
                record.registered_product_name
            ) and register.normalize_name(company.claimed_legal_name) == register.normalize_name(
                record.registered_company_name
            )
            if not names_match:
                mismatch_reason = "registered_names_differ"
        if batch is not None and batch.expiry_date is not None and batch.expiry_date < today:
            warnings.append(
                LookupWarning(
                    code="BATCH_EXPIRED",
                    message="The expiry date recorded for this batch in the demo data has passed.",
                )
            )

    # --- Primary result -------------------------------------------------------------------
    if record_read.status != RegisterRecordStatus.ACTIVE_IN_DEMO_REGISTER:
        result = LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE
        state = "expired" if record_read.status.startswith("EXPIRED") else "inactive"
        message = (
            f"This number is in the {register_name} (demo data), but the record is {state}. "
            "This is the status of the demo record, not an official enforcement result."
        )
        if mismatch_reason:
            warnings.append(
                LookupWarning(
                    code="REGISTRATION_MISMATCH",
                    message="The batch also belongs to a different product or company than "
                    "this record.",
                )
            )
    elif mismatch_reason:
        result = LookupResult.REGISTRATION_MISMATCH
        message = MISMATCH_MESSAGES[mismatch_reason].format(register=register_name)
    else:
        result = LookupResult.REGISTERED_ACTIVE
        message = (
            f"This number matches an active record in the {register_name} (demo data). "
            "Compare the registered product and company names below with the pack. A matching "
            "number cannot rule out a copied number."
        )

    response = _response(
        result,
        message,
        lookup_input,
        warnings=warnings,
        register_record=record_read,
        mismatch=LookupMismatch(reason=mismatch_reason)
        if mismatch_reason and result == LookupResult.REGISTRATION_MISMATCH
        else None,
        product=LookupProduct(
            name=product.name,
            brand=product.brand,
            category=product.category,
            package_size=product.package_size,
            manufacturer_name=product.manufacturer_name,
            company_display_name=company.display_name,
            registration_number=product.registration_number,
        )
        if product is not None
        else None,
        batch=LookupBatch(
            batch_number=batch.batch_number,
            production_date=batch.production_date,
            expiry_date=batch.expiry_date,
        )
        if batch is not None
        else None,
        announcements=announcements.for_lookup(db, product.product_id) if product else [],
    )
    return response, batch


def record_scan(db: Session, response: LookupResponse, batch: ProductBatch | None) -> None:
    """Store an anonymised scan: normalised input, matched batch, result, time. Nothing that
    identifies the person (no IP, session, user, or device details)."""
    db.add(
        BatchScan(
            input_registration_number=response.input.registration_number,
            input_batch_number=response.input.batch_number,
            matched_batch_id=batch.batch_id if batch is not None else None,
            result=response.result,
        )
    )
    db.commit()
