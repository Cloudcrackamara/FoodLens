"""Consumer batch lookup: one test per state, precedence, visibility, anonymised scan log,
and wording rules (non-negotiable rules 1-3)."""

import json
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, inspect, select

from app.demo_data import SEED_CASES, seed_demo_data
from app.models import BatchScan, Company, Product, ProductBatch
from app.models.enums import (
    CompanyReviewStatus,
    CredentialStatus,
    LookupResult,
    ProductStatus,
    ReviewStatus,
)
from app.services.lookup import lookup_batch
from tests import factories as f

TODAY = date(2026, 10, 8)
FUTURE = TODAY + timedelta(days=365)
PAST = TODAY - timedelta(days=30)
BANNED_WORDS = re.compile(r"\b(safe|unsafe|fake)\b", re.IGNORECASE)


def visible_product(
    session: Session,
    code: str = "DEMO-PC-1",
    *,
    company_status=CompanyReviewStatus.APPROVED,
    product_status=ProductStatus.PUBLISHED,
) -> Product:
    company = f.make_company(session, review_status=company_status)
    return f.make_product(session, company, product_code=code, status=product_status)


def approved_batch(
    session: Session,
    product: Product,
    number: str = "DEMO-LOT-1",
    *,
    expiry: date | None = FUTURE,
    status=ReviewStatus.APPROVED,
) -> ProductBatch:
    return f.make_batch(
        session, product, batch_number=number, expiry_date=expiry, review_status=status
    )


def credential(session: Session, product: Product, **overrides) -> None:
    values = {
        "review_status": ReviewStatus.APPROVED,
        "valid_from": TODAY - timedelta(days=365),
        "valid_until": FUTURE,
    } | overrides
    f.make_credential(session, product, f.make_agency(session), **values)


def lookup(session: Session, product_code: str | None, batch_number: str | None):
    response, _ = lookup_batch(
        session, product_code=product_code, batch_number=batch_number, today=TODAY
    )
    return response


def found_setup(session: Session) -> Product:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product)
    return product


# --- One test per state ------------------------------------------------------------------


def test_demo_record_found(session: Session) -> None:
    found_setup(session)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.DEMO_RECORD_FOUND
    assert response.title == "Demo record found"
    assert response.product.product_code == "DEMO-PC-1"
    assert response.batch.batch_number == "DEMO-LOT-1"
    assert [c.status for c in response.credentials] == ["ACTIVE_IN_DEMO_DATA"]
    assert response.warnings == []


def test_batch_not_found(session: Session) -> None:
    found_setup(session)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-404")

    assert response.result == LookupResult.BATCH_NOT_FOUND
    assert response.product is None
    assert "says nothing about the product itself" in response.message


def test_batch_expired(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product, expiry=PAST)
    credential(session, product)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.BATCH_EXPIRED
    assert "expiry date stored for this batch" in response.message


def test_details_mismatch_when_batch_belongs_to_another_product(session: Session) -> None:
    found_setup(session)
    other = visible_product(session, "DEMO-PC-2")
    approved_batch(session, other, "DEMO-LOT-2")

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-2")

    assert response.result == LookupResult.DETAILS_MISMATCH
    assert response.mismatch.field == "product_code"
    assert response.product is None  # does not reveal the other product


def test_details_mismatch_when_product_has_no_credential(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.DETAILS_MISMATCH
    assert response.mismatch.field == "credential"
    assert response.credentials == []


def test_credential_expired(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product, valid_until=PAST)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE
    assert [c.status for c in response.credentials] == ["EXPIRED_IN_DEMO_DATA"]
    assert "not an official enforcement result" in response.message


def test_credential_inactive(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product, status=CredentialStatus.INACTIVE)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE
    assert [c.status for c in response.credentials] == ["INACTIVE_IN_DEMO_DATA"]


def test_insufficient_when_nothing_entered(session: Session) -> None:
    response = lookup(session, None, "   ")

    assert response.result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert response.candidates == []


def test_ambiguous_batch_number_offers_candidates_without_details(session: Session) -> None:
    for code in ("DEMO-PC-1", "DEMO-PC-2"):
        approved_batch(session, visible_product(session, code), "DEMO-LOT-SHARED")

    response = lookup(session, None, "demo-lot-shared")

    assert response.result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert [c.product_code for c in response.candidates] == ["DEMO-PC-1", "DEMO-PC-2"]
    assert response.product is None and response.batch is None


def test_batch_number_alone_never_shows_a_record(session: Session) -> None:
    found_setup(session)

    response = lookup(session, None, "DEMO-LOT-1")

    assert response.result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert [c.product_code for c in response.candidates] == ["DEMO-PC-1"]
    assert response.product is None


def test_malformed_input_is_insufficient(session: Session) -> None:
    response = lookup(session, "DEMO-PC-1", "<script>")

    assert response.result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert "characters" in response.message


def test_overlong_input_is_insufficient(session: Session) -> None:
    response = lookup(session, "DEMO-PC-1", "A" * 65)

    assert response.result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert len(response.input.batch_number) == 64


# --- Precedence and warnings (docs/DECISIONS.md Q4) ----------------------------------------


def test_expired_batch_takes_precedence_and_warns_about_credential(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product, expiry=PAST)
    credential(session, product, valid_until=PAST)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.BATCH_EXPIRED
    assert [w.code for w in response.warnings] == ["CREDENTIAL_EXPIRED_OR_INACTIVE"]


def test_expired_batch_without_credential_warns(session: Session) -> None:
    approved_batch(session, visible_product(session), expiry=PAST)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.BATCH_EXPIRED
    assert [w.code for w in response.warnings] == ["NO_CREDENTIAL_RECORD"]


def test_one_active_credential_is_enough_but_others_are_warned(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product)
    credential(session, product, valid_until=PAST)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.DEMO_RECORD_FOUND
    assert [w.code for w in response.warnings] == ["CREDENTIAL_EXPIRED_OR_INACTIVE"]


def test_batch_expiring_today_is_not_expired(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product, expiry=TODAY)
    credential(session, product, valid_until=TODAY)

    assert lookup(session, "DEMO-PC-1", "DEMO-LOT-1").result == LookupResult.DEMO_RECORD_FOUND


def test_credential_not_yet_valid_does_not_count_as_active(session: Session) -> None:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product, valid_from=TODAY + timedelta(days=1))

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.CREDENTIAL_EXPIRED_OR_INACTIVE
    assert [c.status for c in response.credentials] == ["NOT_YET_VALID_IN_DEMO_DATA"]


# --- Visibility: only reviewed, published data -------------------------------------------


@pytest.mark.parametrize(
    "setup",
    [
        {"batch_status": ReviewStatus.PENDING_REVIEW},
        {"batch_status": ReviewStatus.REJECTED},
        {"product_status": ProductStatus.DRAFT},
        {"product_status": ProductStatus.PENDING_REVIEW},
        {"product_status": ProductStatus.WITHDRAWN},
        {"company_status": CompanyReviewStatus.PENDING_REVIEW},
        {"company_status": CompanyReviewStatus.SUSPENDED},
    ],
)
def test_unreviewed_or_unpublished_records_are_not_found(session: Session, setup: dict) -> None:
    product = visible_product(
        session,
        company_status=setup.get("company_status", CompanyReviewStatus.APPROVED),
        product_status=setup.get("product_status", ProductStatus.PUBLISHED),
    )
    approved_batch(session, product, status=setup.get("batch_status", ReviewStatus.APPROVED))
    credential(session, product)

    assert lookup(session, "DEMO-PC-1", "DEMO-LOT-1").result == LookupResult.BATCH_NOT_FOUND


@pytest.mark.parametrize("review", [ReviewStatus.PENDING_REVIEW, ReviewStatus.REJECTED])
def test_unreviewed_credentials_are_ignored(session: Session, review: ReviewStatus) -> None:
    product = visible_product(session)
    approved_batch(session, product)
    credential(session, product, review_status=review)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert response.result == LookupResult.DETAILS_MISMATCH
    assert response.mismatch.field == "credential"


# --- Normalisation and response shape ------------------------------------------------------


def test_input_is_normalised(session: Session) -> None:
    found_setup(session)

    response = lookup(session, "  demo-pc-1 ", "demo-lot-1")

    assert response.result == LookupResult.DEMO_RECORD_FOUND
    assert response.input.product_code == "DEMO-PC-1"
    assert response.input.batch_number == "DEMO-LOT-1"


def test_inner_whitespace_is_collapsed(session: Session) -> None:
    product = visible_product(session, "DEMO PC 1")
    approved_batch(session, product, "LOT 1")
    credential(session, product)

    assert lookup(session, "demo   pc 1", " lot  1").result == LookupResult.DEMO_RECORD_FOUND


def test_credentials_are_product_level_only(session: Session) -> None:
    found_setup(session)

    response = lookup(session, "DEMO-PC-1", "DEMO-LOT-1")

    assert {c.scope for c in response.credentials} == {"PRODUCT"}
    assert {c.data_mode for c in response.credentials} == {"DEMO"}
    assert "not to this batch" in response.credential_scope_note
    assert "not a batch certificate" in response.credential_scope_note


# --- API ------------------------------------------------------------------------------------


def post(client: TestClient, product_code: str | None, batch_number: str | None):
    return client.post(
        "/api/lookups/batch",
        json={"product_code": product_code, "batch_number": batch_number},
    )


def test_api_needs_no_sign_in_and_sets_no_cookie(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    response = post(client, "DEMO-PC-0001", "DEMO-LOT-101")

    assert response.status_code == 200
    assert response.json()["result"] == "DEMO_RECORD_FOUND"
    assert "set-cookie" not in response.headers


def test_api_accepts_empty_body(client: TestClient) -> None:
    response = client.post("/api/lookups/batch", json={})

    assert response.status_code == 200
    assert response.json()["result"] == "INSUFFICIENT_OR_AMBIGUOUS"


@pytest.mark.parametrize("case", SEED_CASES, ids=lambda c: c.description)
def test_every_seed_case_returns_its_documented_state(
    client: TestClient, session: Session, case
) -> None:
    seed_demo_data(session)

    body = post(client, case.product_code, case.batch_number).json()

    assert body["result"] == case.expected
    assert body["data_mode"] == "DEMO"
    assert body["disclaimer"].startswith("DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE")


def test_seed_covers_every_lookup_state() -> None:
    assert {case.expected for case in SEED_CASES} == set(LookupResult)


def test_no_response_ever_says_safe_unsafe_or_fake(client: TestClient, session: Session) -> None:
    seed_demo_data(session)
    extra_inputs = [("DEMO-PC-0001", "<bad>"), ("x" * 70, "DEMO-LOT-101"), (None, None)]
    inputs = [(c.product_code, c.batch_number) for c in SEED_CASES] + extra_inputs

    for product_code, batch_number in inputs:
        text = json.dumps(post(client, product_code, batch_number).json())
        assert not BANNED_WORDS.search(text), (product_code, batch_number, text)


def test_every_response_has_data_mode_and_disclaimer(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    for case in SEED_CASES:
        body = post(client, case.product_code, case.batch_number).json()
        assert body["data_mode"] == "DEMO"
        assert "not a NAFDAC or SON decision" in body["disclaimer"]


# --- Anonymised scan log ------------------------------------------------------------------


def test_each_lookup_logs_an_anonymised_scan(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    post(client, "demo-pc-0001", "demo-lot-101")
    post(client, "DEMO-PC-0001", "DEMO-LOT-999")

    scans = session.exec(select(BatchScan).order_by(BatchScan.created_at)).all()
    assert [s.result for s in scans] == ["DEMO_RECORD_FOUND", "BATCH_NOT_FOUND"]
    assert scans[0].input_product_code == "DEMO-PC-0001"
    assert scans[0].matched_batch_id is not None
    assert scans[1].matched_batch_id is None


def test_scan_log_has_no_identifying_columns(engine) -> None:
    columns = {c["name"] for c in inspect(engine).get_columns("batch_scan")}

    assert columns == {
        "scan_id",
        "created_at",
        "input_product_code",
        "input_batch_number",
        "matched_batch_id",
        "result",
    }


def test_lookups_are_rate_limited(make_client, session: Session) -> None:
    client = make_client(client_ip="203.0.113.77")

    statuses = [post(client, "DEMO-PC-0001", "DEMO-LOT-101").status_code for _ in range(21)]

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_seed_is_idempotent(session: Session) -> None:
    seed_demo_data(session)
    seed_demo_data(session)

    assert len(session.exec(select(Company)).all()) == 4
    assert len(session.exec(select(Product)).all()) == 8
