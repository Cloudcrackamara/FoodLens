"""Fictional demo dataset for the consumer lookup.

Every name is invented and labelled "(fictional)"; every code starts with DEMO-; every agency is
"(simulated)"; every credential has data_mode DEMO. Dates are set relative to the seeding day so
each lookup state stays reproducible. SEED_CASES lists one lookup per state and is used by the
tests and the README.

Seeding is idempotent: rows are found by natural key and never overwritten.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import (
    Company,
    CredentialRecord,
    Product,
    ProductBatch,
    RegulatoryAgency,
)
from app.models.base import utc_now
from app.models.enums import (
    CompanyReviewStatus,
    CompanyType,
    CredentialStatus,
    LookupResult,
    ProductStatus,
    ReviewStatus,
)

SEED_NOTE = "Seeded fictional demo record"
PROVENANCE = "Fictional record created for the FoodLens capstone demo. Not from any regulator."


@dataclass(frozen=True)
class SeedCase:
    description: str
    product_code: str | None
    batch_number: str | None
    expected: LookupResult


SEED_CASES: list[SeedCase] = [
    SeedCase("Active NAFDAC and SON credentials", "DEMO-PC-0001", "DEMO-LOT-101", LookupResult.DEMO_RECORD_FOUND),
    SeedCase("Second product, active credential", "DEMO-PC-0002", "DEMO-LOT-201", LookupResult.DEMO_RECORD_FOUND),
    SeedCase("Batch number not in demo data", "DEMO-PC-0001", "DEMO-LOT-999", LookupResult.BATCH_NOT_FOUND),
    SeedCase("Batch awaiting review is hidden", "DEMO-PC-0001", "DEMO-LOT-102", LookupResult.BATCH_NOT_FOUND),
    SeedCase("Draft product is hidden", "DEMO-PC-0007", "DEMO-LOT-701", LookupResult.BATCH_NOT_FOUND),
    SeedCase("Company awaiting review is hidden", "DEMO-PC-0008", "DEMO-LOT-801", LookupResult.BATCH_NOT_FOUND),
    SeedCase("Batch expiry date has passed", "DEMO-PC-0005", "DEMO-LOT-501", LookupResult.BATCH_EXPIRED),
    SeedCase("Batch belongs to another product", "DEMO-PC-0001", "DEMO-LOT-201", LookupResult.DETAILS_MISMATCH),
    SeedCase("Product has no approved credential", "DEMO-PC-0006", "DEMO-LOT-601", LookupResult.DETAILS_MISMATCH),
    SeedCase("Credential expired", "DEMO-PC-0003", "DEMO-LOT-301", LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE),
    SeedCase("Credential inactive", "DEMO-PC-0004", "DEMO-LOT-401", LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE),
    SeedCase("Batch number on two products, no product code", None, "DEMO-LOT-001", LookupResult.INSUFFICIENT_OR_AMBIGUOUS),
    SeedCase("Nothing entered", None, None, LookupResult.INSUFFICIENT_OR_AMBIGUOUS),
]  # fmt: skip


def _get_or_create(db: Session, model, lookup: dict, values: dict):
    row = db.exec(select(model).filter_by(**lookup)).first()
    if row is None:
        row = model(**lookup, **values)
        db.add(row)
        db.flush()
    return row


def _reviewed(status) -> dict:
    return {"review_status": status, "reviewed_at": utc_now(), "review_note": SEED_NOTE}


def seed_demo_data(db: Session, today: date | None = None) -> None:
    today = today or date.today()
    future = today + timedelta(days=400)
    past = today - timedelta(days=60)
    long_ago = today - timedelta(days=500)

    def company(identifier: str, name: str, status=CompanyReviewStatus.APPROVED) -> Company:
        return _get_or_create(
            db,
            Company,
            {"claimed_business_identifier": identifier},
            {
                "company_type": CompanyType.MANUFACTURER,
                "display_name": name,
                "contact_email": f"contact@{identifier.lower()}.example",
                "claimed_legal_name": f"{name} Ltd",
                "claimed_address": "1 Example Street, Demo Industrial Estate (fictional)",
                **_reviewed(status),
            },
        )

    harvest = company("DEMO-RC-0001", "Demo Harvest Foods (fictional)")
    springs = company("DEMO-RC-0002", "Sample Springs Beverages (fictional)")
    mills = company("DEMO-RC-0003", "Example Grain Mills (fictional)")
    pending = company(
        "DEMO-RC-0004", "Pending Demo Snacks (fictional)", CompanyReviewStatus.PENDING_REVIEW
    )

    def product(company_row: Company, code: str, name: str, category: str, size: str,
                status=ProductStatus.PUBLISHED) -> Product:  # fmt: skip
        return _get_or_create(
            db,
            Product,
            {"product_code": code},
            {
                "company_id": company_row.company_id,
                "name": name,
                "brand": company_row.display_name.replace(" (fictional)", ""),
                "category": category,
                "package_size": size,
                "manufacturer_name": company_row.claimed_legal_name,
                "status": status,
                "reviewed_at": utc_now(),
                "review_note": SEED_NOTE,
            },
        )

    palm_oil = product(harvest, "DEMO-PC-0001", "Sample Palm Oil", "Oils", "1 L")
    groundnut_oil = product(harvest, "DEMO-PC-0002", "Sample Groundnut Oil", "Oils", "1 L")
    water = product(springs, "DEMO-PC-0003", "Sample Table Water", "Beverages", "75 cl")
    flour = product(mills, "DEMO-PC-0004", "Sample Maize Flour", "Flour", "2 kg")
    paste = product(harvest, "DEMO-PC-0005", "Sample Tomato Paste", "Canned foods", "400 g")
    honey = product(harvest, "DEMO-PC-0006", "Sample Honey", "Spreads", "500 g")
    draft = product(mills, "DEMO-PC-0007", "Sample Semolina (draft)", "Flour", "1 kg",
                    ProductStatus.DRAFT)  # fmt: skip
    snack = product(pending, "DEMO-PC-0008", "Sample Plantain Chips", "Snacks", "100 g")

    def batch(product_row: Product, number: str, expiry: date,
              status=ReviewStatus.APPROVED) -> ProductBatch:  # fmt: skip
        return _get_or_create(
            db,
            ProductBatch,
            {"product_id": product_row.product_id, "batch_number": number},
            {
                "production_date": expiry - timedelta(days=540),
                "expiry_date": expiry,
                **_reviewed(status),
            },
        )

    batch(palm_oil, "DEMO-LOT-101", future)
    batch(palm_oil, "DEMO-LOT-102", future, ReviewStatus.PENDING_REVIEW)
    batch(palm_oil, "DEMO-LOT-001", future)  # shared lot number: ambiguous without product code
    batch(groundnut_oil, "DEMO-LOT-201", future)
    batch(groundnut_oil, "DEMO-LOT-001", future)
    batch(water, "DEMO-LOT-301", future)
    batch(flour, "DEMO-LOT-401", future)
    batch(paste, "DEMO-LOT-501", past)
    batch(honey, "DEMO-LOT-601", future)
    batch(draft, "DEMO-LOT-701", future)
    batch(snack, "DEMO-LOT-801", future)

    nafdac = _get_or_create(
        db,
        RegulatoryAgency,
        {"name": "NAFDAC (simulated)", "scheme": "Food product registration (demo)"},
        {},
    )
    son = _get_or_create(
        db,
        RegulatoryAgency,
        {
            "name": "SON MANCAP (simulated)",
            "scheme": "Mandatory Conformity Assessment Programme (demo)",
        },
        {},
    )

    def credential(product_row: Product, agency: RegulatoryAgency, reference: str,
                   valid_until: date, status=CredentialStatus.ACTIVE,
                   review=ReviewStatus.APPROVED) -> None:  # fmt: skip
        _get_or_create(
            db,
            CredentialRecord,
            {"agency_id": agency.agency_id, "reference_number": reference},
            {
                "product_id": product_row.product_id,
                "status": status,
                "valid_from": long_ago,
                "valid_until": valid_until,
                "provenance": PROVENANCE,
                "checked_on": today,
                **_reviewed(review),
            },
        )

    credential(palm_oil, nafdac, "DEMO-NAFDAC-0001", future)
    credential(palm_oil, son, "DEMO-MANCAP-0001", future)
    credential(groundnut_oil, nafdac, "DEMO-NAFDAC-0002", future)
    credential(water, nafdac, "DEMO-NAFDAC-0003", past)  # expired
    credential(flour, son, "DEMO-MANCAP-0004", future, CredentialStatus.INACTIVE)
    credential(paste, nafdac, "DEMO-NAFDAC-0005", future)
    # Company-entered, not yet reviewed: must not make Sample Honey look credentialed.
    credential(honey, nafdac, "DEMO-NAFDAC-0006", future, review=ReviewStatus.PENDING_REVIEW)
    credential(snack, nafdac, "DEMO-NAFDAC-0008", future)

    db.commit()
