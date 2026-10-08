"""Consumer batch lookup against the fictional demo dataset.

Returns exactly one primary state, using the precedence in docs/DECISIONS.md Q4:
  1. INSUFFICIENT_OR_AMBIGUOUS  input missing, malformed, or matching several products
  2. BATCH_NOT_FOUND            no visible batch; DETAILS_MISMATCH (product_code) if the
                                batch number exists under a different product
  3. BATCH_EXPIRED              batch expiry date has passed
  4. CREDENTIAL_EXPIRED_OR_INACTIVE  approved credentials exist, none currently active
  5. DETAILS_MISMATCH (credential)   no approved credential for the product
  6. DEMO_RECORD_FOUND

Only published products of approved companies, approved batches, and approved credentials are
visible. Results never say "safe", "unsafe", or "fake" (non-negotiable rule 1).
"""

import re
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    BatchScan,
    Company,
    CredentialRecord,
    Product,
    ProductBatch,
    RegulatoryAgency,
)
from app.models.enums import (
    CompanyReviewStatus,
    CredentialStatus,
    LookupResult,
    ProductStatus,
    ReviewStatus,
)
from app.schemas.lookup import (
    CredentialDisplayStatus,
    LookupBatch,
    LookupCandidate,
    LookupCredential,
    LookupInput,
    LookupMismatch,
    LookupProduct,
    LookupResponse,
    LookupWarning,
)

MAX_CODE_LENGTH = 64
_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 ._/-]*$")

DISCLAIMER = (
    "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. FoodLens compares what you entered with "
    "fictional demonstration records. It is not a laboratory or food-safety test, it does not "
    "check the package in your hand, and it is not a NAFDAC or SON decision."
)
CREDENTIAL_SCOPE_NOTE = (
    "Credentials shown are product-level records in the demo data. They apply to the product "
    "in general, not to this batch, and are not a batch certificate or a test result."
)

TITLES = {
    LookupResult.DEMO_RECORD_FOUND: "Demo record found",
    LookupResult.BATCH_NOT_FOUND: "No match in demo data",
    LookupResult.BATCH_EXPIRED: "Batch expiry date has passed in demo data",
    LookupResult.DETAILS_MISMATCH: "Details do not match",
    LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE: (
        "Credential shown as expired or inactive in demo data"
    ),
    LookupResult.INSUFFICIENT_OR_AMBIGUOUS: "More details needed",
}

MESSAGES = {
    "found": (
        "A matching product and batch record was found in the FoodLens demonstration dataset, "
        "with at least one active product-level credential record."
    ),
    "not_found": (
        "No matching batch was found in the FoodLens demonstration dataset. This only means the "
        "batch is not in the demo data; it says nothing about the product itself. Check the "
        "numbers on the package and try again."
    ),
    "batch_expired": (
        "A matching record was found, but the expiry date stored for this batch in the demo "
        "data has passed."
    ),
    "mismatch_product_code": (
        "This batch number is recorded in the demo data under a different product code. Check "
        "the product code and batch number printed on the package."
    ),
    "mismatch_credential": (
        "The product and batch were found, but no credential record matches this product in "
        "the demo data."
    ),
    "credential_expired": (
        "The product and batch were found. The credential records stored for this product are "
        "expired or inactive in the demo data. This is the status of the stored demo record, "
        "not an official enforcement result."
    ),
    "missing": "Enter both the product code and the batch number as printed on the package.",
    "malformed": (
        "The product code or batch number contains characters that are not used in codes. "
        "Use only letters, numbers, spaces, and - . / _ as printed on the package."
    ),
    "choose_product": (
        "Enter the product code too. If your product is listed below, choose it to continue."
    ),
}

WARNING_CREDENTIALS_NOT_CURRENT = LookupWarning(
    code="CREDENTIAL_EXPIRED_OR_INACTIVE",
    message="One or more credential records for this product are expired or inactive in the "
    "demo data.",
)
WARNING_NO_CREDENTIAL = LookupWarning(
    code="NO_CREDENTIAL_RECORD",
    message="No credential record matches this product in the demo data.",
)


def normalize_code(value: str | None) -> str | None:
    """Trim, collapse inner whitespace, upper-case. Empty becomes None."""
    if value is None:
        return None
    normalized = " ".join(value.split()).upper()
    return normalized or None


def _is_valid_code(value: str) -> bool:
    return len(value) <= MAX_CODE_LENGTH and bool(_CODE_PATTERN.match(value))


def credential_status(credential: CredentialRecord, today: date) -> CredentialDisplayStatus:
    if credential.status == CredentialStatus.INACTIVE:
        return CredentialDisplayStatus.INACTIVE_IN_DEMO_DATA
    if credential.valid_until is not None and credential.valid_until < today:
        return CredentialDisplayStatus.EXPIRED_IN_DEMO_DATA
    if credential.valid_from is not None and credential.valid_from > today:
        return CredentialDisplayStatus.NOT_YET_VALID_IN_DEMO_DATA
    return CredentialDisplayStatus.ACTIVE_IN_DEMO_DATA


def _visible_batches():
    """Batches a consumer may see: approved batch, published product, approved company."""
    return (
        select(ProductBatch, Product, Company)
        .join(Product, Product.product_id == ProductBatch.product_id)
        .join(Company, Company.company_id == Product.company_id)
        .where(
            ProductBatch.review_status == ReviewStatus.APPROVED,
            Product.status == ProductStatus.PUBLISHED,
            Company.review_status == CompanyReviewStatus.APPROVED,
        )
    )


def _response(
    result: LookupResult,
    message: str,
    lookup_input: LookupInput,
    **fields,
) -> LookupResponse:
    return LookupResponse(
        result=result,
        disclaimer=DISCLAIMER,
        title=TITLES[result],
        message=message,
        input=lookup_input,
        credential_scope_note=CREDENTIAL_SCOPE_NOTE,
        **fields,
    )


def lookup_batch(
    db: Session,
    *,
    product_code: str | None,
    batch_number: str | None,
    today: date,
) -> tuple[LookupResponse, ProductBatch | None]:
    """Look up a product code + batch number. Returns the response and the matched batch
    (for the anonymised scan log), or None if no batch was resolved."""
    code = normalize_code(product_code)
    batch_no = normalize_code(batch_number)
    lookup_input = LookupInput(
        product_code=code[:MAX_CODE_LENGTH] if code else None,
        batch_number=batch_no[:MAX_CODE_LENGTH] if batch_no else None,
    )
    insufficient = LookupResult.INSUFFICIENT_OR_AMBIGUOUS

    if batch_no is None:
        return _response(insufficient, MESSAGES["missing"], lookup_input), None
    if not _is_valid_code(batch_no) or (code is not None and not _is_valid_code(code)):
        return _response(insufficient, MESSAGES["malformed"], lookup_input), None

    same_batch_number = func.upper(ProductBatch.batch_number) == batch_no

    if code is None:
        rows = db.exec(_visible_batches().where(same_batch_number)).all()
        candidates = sorted(
            (
                LookupCandidate(product_code=p.product_code, name=p.name, brand=p.brand)
                for _, p, _ in rows
            ),
            key=lambda c: c.product_code,
        )
        message = MESSAGES["choose_product"] if candidates else MESSAGES["missing"]
        return _response(insufficient, message, lookup_input, candidates=candidates), None

    row = db.exec(
        _visible_batches().where(same_batch_number, func.upper(Product.product_code) == code)
    ).first()

    if row is None:
        elsewhere = db.exec(_visible_batches().where(same_batch_number)).first()
        if elsewhere is not None:
            return (
                _response(
                    LookupResult.DETAILS_MISMATCH,
                    MESSAGES["mismatch_product_code"],
                    lookup_input,
                    mismatch=LookupMismatch(field="product_code"),
                ),
                None,
            )
        return _response(LookupResult.BATCH_NOT_FOUND, MESSAGES["not_found"], lookup_input), None

    batch, product, company = row
    credentials = _approved_credentials(db, product, today)
    statuses = [c.status for c in credentials]
    any_active = CredentialDisplayStatus.ACTIVE_IN_DEMO_DATA in statuses
    some_not_active = any(s != CredentialDisplayStatus.ACTIVE_IN_DEMO_DATA for s in statuses)
    batch_expired = batch.expiry_date is not None and batch.expiry_date < today

    warnings: list[LookupWarning] = []
    mismatch = None
    if batch_expired:
        result, message = LookupResult.BATCH_EXPIRED, MESSAGES["batch_expired"]
        if not credentials:
            warnings.append(WARNING_NO_CREDENTIAL)
        elif some_not_active:
            warnings.append(WARNING_CREDENTIALS_NOT_CURRENT)
    elif credentials and not any_active:
        result, message = (
            LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE,
            MESSAGES["credential_expired"],
        )
    elif not credentials:
        result, message = LookupResult.DETAILS_MISMATCH, MESSAGES["mismatch_credential"]
        mismatch = LookupMismatch(field="credential")
    else:
        result, message = LookupResult.DEMO_RECORD_FOUND, MESSAGES["found"]
        if some_not_active:
            warnings.append(WARNING_CREDENTIALS_NOT_CURRENT)

    response = _response(
        result,
        message,
        lookup_input,
        warnings=warnings,
        mismatch=mismatch,
        product=LookupProduct(
            product_code=product.product_code,
            name=product.name,
            brand=product.brand,
            category=product.category,
            package_size=product.package_size,
            manufacturer_name=product.manufacturer_name,
            company_display_name=company.display_name,
        ),
        batch=LookupBatch(
            batch_number=batch.batch_number,
            production_date=batch.production_date,
            expiry_date=batch.expiry_date,
        ),
        credentials=credentials,
    )
    return response, batch


def _approved_credentials(db: Session, product: Product, today: date) -> list[LookupCredential]:
    rows = db.exec(
        select(CredentialRecord, RegulatoryAgency)
        .join(RegulatoryAgency, RegulatoryAgency.agency_id == CredentialRecord.agency_id)
        .where(
            CredentialRecord.product_id == product.product_id,
            CredentialRecord.review_status == ReviewStatus.APPROVED,
        )
        .order_by(RegulatoryAgency.name, CredentialRecord.reference_number)
    ).all()
    return [
        LookupCredential(
            agency=agency.name,
            scheme=agency.scheme,
            reference_number=credential.reference_number,
            status=credential_status(credential, today),
            valid_from=credential.valid_from,
            valid_until=credential.valid_until,
            data_mode=credential.data_mode,
            provenance=credential.provenance,
            checked_on=credential.checked_on,
        )
        for credential, agency in rows
    ]


def record_scan(db: Session, response: LookupResponse, batch: ProductBatch | None) -> None:
    """Store an anonymised scan: normalised input, matched batch, result, time. Nothing that
    identifies the person (no IP, session, user, or device details)."""
    db.add(
        BatchScan(
            input_product_code=response.input.product_code,
            input_batch_number=response.input.batch_number,
            matched_batch_id=batch.batch_id if batch is not None else None,
            result=response.result,
        )
    )
    db.commit()
