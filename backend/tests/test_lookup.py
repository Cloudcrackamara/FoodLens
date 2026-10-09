"""Consumer registration lookup against the simulated register (D80-D85): one test per result,
order of checks, batch warnings, scan-friendly input, wording, and the anonymised scan log."""

import json
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, inspect, select

from app.demo_data import SEED_CASES, seed_demo_data
from app.models import BatchScan, Company, Product, RegulatorRegister, RegulatoryAgency
from app.models.enums import (
    CompanyReviewStatus,
    LookupResult,
    ProductStatus,
    RegisterStatus,
    ReviewStatus,
)
from app.services.lookup import lookup_registration
from app.services.register import normalize_registration_number
from tests import factories as f

TODAY = date(2026, 10, 9)
FUTURE = TODAY + timedelta(days=365)
PAST = TODAY - timedelta(days=30)
URL = "/api/lookups/registration"
BANNED = re.compile(r"\b(safe|unsafe|fake|genuine)\b|verified by nafdac", re.IGNORECASE)


@pytest.fixture
def nafdac(session: Session) -> RegulatoryAgency:
    return f.make_agency(
        session, name="NAFDAC (simulated)", scheme="Food product registration (demo)"
    )


def registered(session: Session, agency: RegulatoryAgency, number="DEMO-NAFDAC-0001", **kw):
    return f.make_register(
        session,
        agency,
        registration_number=number,
        expires_on=kw.pop("expires_on", FUTURE),
        **kw,
    )


def catalogue_product(
    session: Session,
    number: str | None = "DEMO-NAFDAC-0001",
    batch_number: str = "DEMO-LOT-1",
    *,
    name: str = "Sample Palm Oil",
    company_status=CompanyReviewStatus.APPROVED,
    product_status=ProductStatus.PUBLISHED,
    batch_status=ReviewStatus.APPROVED,
    expiry: date | None = FUTURE,
    code: str | None = None,
) -> tuple[Company, Product]:
    company = f.make_company(session, review_status=company_status)
    overrides = {"product_code": code} if code else {}
    product = f.make_product(
        session, company, name=name, registration_number=number, status=product_status,
        **overrides,
    )  # fmt: skip
    f.make_batch(
        session, product, batch_number=batch_number, expiry_date=expiry, review_status=batch_status
    )
    return company, product


def lookup(session: Session, number: str | None, batch: str | None = None):
    response, _ = lookup_registration(
        session, registration_number=number, batch_number=batch, today=TODAY
    )
    return response


# --- One test per result --------------------------------------------------------------------


def test_registered_active_number_only(session: Session, nafdac) -> None:
    registered(session, nafdac)

    response = lookup(session, "DEMO-NAFDAC-0001")

    assert response.result == LookupResult.REGISTERED_ACTIVE
    record = response.register_record
    assert record.agency == "NAFDAC (simulated)"
    assert record.registered_product_name == "Sample Palm Oil"
    assert record.status == "ACTIVE_IN_DEMO_REGISTER"
    assert record.data_mode == "DEMO"
    assert "simulated NAFDAC register (demo data)" in response.message
    assert response.product is None and response.batch is None


def test_registered_active_with_matching_batch(session: Session, nafdac) -> None:
    registered(session, nafdac)
    catalogue_product(session)

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTERED_ACTIVE
    assert response.product.name == "Sample Palm Oil"
    assert response.batch.batch_number == "DEMO-LOT-1"
    assert response.warnings == []


def test_registration_not_found(session: Session, nafdac) -> None:
    registered(session, nafdac)

    response = lookup(session, "DEMO-NAFDAC-9999", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTRATION_NOT_FOUND
    assert response.register_record is None
    assert "does not show what the real regulator holds" in response.message


def test_registration_expired(session: Session, nafdac) -> None:
    registered(session, nafdac, expires_on=PAST)

    response = lookup(session, "DEMO-NAFDAC-0001")

    assert response.result == LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE
    assert response.register_record.status == "EXPIRED_IN_DEMO_REGISTER"
    assert "not an official enforcement result" in response.message


def test_registration_inactive(session: Session, nafdac) -> None:
    registered(session, nafdac, status=RegisterStatus.INACTIVE)

    response = lookup(session, "DEMO-NAFDAC-0001")

    assert response.result == LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE
    assert response.register_record.status == "INACTIVE_IN_DEMO_REGISTER"


def test_mismatch_when_batch_belongs_to_product_with_other_number(session: Session, nafdac) -> None:
    registered(session, nafdac)
    catalogue_product(session, number="DEMO-NAFDAC-0002")

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTRATION_MISMATCH
    assert response.mismatch.reason == "different_registration_number"


def test_mismatch_when_registered_names_differ(session: Session, nafdac) -> None:
    registered(
        session, nafdac, registered_product_name="Sample Chin Chin",
        registered_company_name="Northern Snacks (fictional) Ltd",
    )  # fmt: skip
    catalogue_product(session, name="Sample Honey")  # copies the number

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTRATION_MISMATCH
    assert response.mismatch.reason == "registered_names_differ"
    assert response.register_record.registered_product_name == "Sample Chin Chin"


def test_insufficient_without_registration_number(session: Session, nafdac) -> None:
    registered(session, nafdac)
    catalogue_product(session)

    assert lookup(session, None, "DEMO-LOT-1").result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS
    assert lookup(session, "   ").result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS


@pytest.mark.parametrize(
    ("number", "batch"), [("<script>", None), ("A" * 65, None), ("DEMO-NAFDAC-0001", "<lot>")]
)
def test_malformed_input_is_insufficient(session: Session, number, batch) -> None:
    assert lookup(session, number, batch).result == LookupResult.INSUFFICIENT_OR_AMBIGUOUS


# --- Order of checks and warnings -------------------------------------------------------------


def test_names_compared_ignoring_capitals_and_spaces(session: Session, nafdac) -> None:
    registered(
        session, nafdac, registered_product_name="SAMPLE  PALMOIL",
        registered_company_name="demo harvest foods ltd (fictional)",
    )  # fmt: skip
    catalogue_product(session)

    assert (
        lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1").result == LookupResult.REGISTERED_ACTIVE
    )


def test_expired_record_takes_precedence_over_mismatch(session: Session, nafdac) -> None:
    registered(session, nafdac, expires_on=PAST)
    catalogue_product(session, number="DEMO-NAFDAC-0002")

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTRATION_EXPIRED_OR_INACTIVE
    assert [w.code for w in response.warnings] == ["REGISTRATION_MISMATCH"]
    assert response.mismatch is None


def test_batch_not_in_catalogue_is_a_warning(session: Session, nafdac) -> None:
    registered(session, nafdac)

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-404")

    assert response.result == LookupResult.REGISTERED_ACTIVE
    assert [w.code for w in response.warnings] == ["BATCH_NOT_IN_CATALOGUE"]


def test_expired_batch_is_a_warning(session: Session, nafdac) -> None:
    registered(session, nafdac)
    catalogue_product(session, expiry=PAST)

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTERED_ACTIVE
    assert [w.code for w in response.warnings] == ["BATCH_EXPIRED"]


def test_record_expiring_today_is_still_active(session: Session, nafdac) -> None:
    registered(session, nafdac, expires_on=TODAY)

    assert lookup(session, "DEMO-NAFDAC-0001").result == LookupResult.REGISTERED_ACTIVE


def test_shared_lot_number_resolved_by_registration_number(session: Session, nafdac) -> None:
    registered(session, nafdac)
    catalogue_product(session, number="DEMO-NAFDAC-0002", batch_number="LOT-SHARED", code="A")
    catalogue_product(session, number="DEMO-NAFDAC-0001", batch_number="LOT-SHARED", code="B")

    response = lookup(session, "DEMO-NAFDAC-0001", "LOT-SHARED")

    assert response.result == LookupResult.REGISTERED_ACTIVE


@pytest.mark.parametrize(
    "setup",
    [
        {"batch_status": ReviewStatus.PENDING_REVIEW},
        {"product_status": ProductStatus.DRAFT},
        {"company_status": CompanyReviewStatus.SUSPENDED},
    ],
)
def test_hidden_catalogue_data_is_ignored(session: Session, nafdac, setup: dict) -> None:
    registered(session, nafdac)
    catalogue_product(session, number="DEMO-NAFDAC-0002", **setup)  # would be a mismatch

    response = lookup(session, "DEMO-NAFDAC-0001", "DEMO-LOT-1")

    assert response.result == LookupResult.REGISTERED_ACTIVE
    assert [w.code for w in response.warnings] == ["BATCH_NOT_IN_CATALOGUE"]


# --- Scan-friendly input ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DEMO-NAFDAC-0001", "DEMO-NAFDAC-0001"),
        ("  demo-nafdac-0001 ", "DEMO-NAFDAC-0001"),
        ("NAFDAC Reg No: DEMO-NAFDAC-0001", "DEMO-NAFDAC-0001"),
        ("NAFDAC NO. demo-nafdac-0001", "DEMO-NAFDAC-0001"),
        ("Reg. No #DEMO-NAFDAC-0001", "DEMO-NAFDAC-0001"),
        ("DEMO - NAFDAC - 0001", "DEMO-NAFDAC-0001"),
        ("NAFDAC", "NAFDAC"),  # nothing else left: keep the text
        ("", None),
    ],
)
def test_registration_number_normalisation(raw: str, expected: str | None) -> None:
    assert normalize_registration_number(raw) == expected


# --- API ------------------------------------------------------------------------------------


def post(client: TestClient, number: str | None, batch: str | None = None):
    return client.post(URL, json={"registration_number": number, "batch_number": batch})


def test_api_needs_no_sign_in_and_sets_no_cookie(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    response = post(client, "DEMO-NAFDAC-0001", "DEMO-LOT-101")

    assert response.status_code == 200
    assert response.json()["result"] == "REGISTERED_ACTIVE"
    assert "set-cookie" not in response.headers


def test_api_ignores_product_code(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    response = client.post(URL, json={"product_code": "DEMO-PC-0001"})

    assert response.json()["result"] == "INSUFFICIENT_OR_AMBIGUOUS"


@pytest.mark.parametrize("case", SEED_CASES, ids=lambda c: c.description)
def test_every_seed_case_returns_its_documented_result(
    client: TestClient, session: Session, case
) -> None:
    seed_demo_data(session)

    body = post(client, case.registration_number, case.batch_number).json()

    assert body["result"] == case.expected
    assert tuple(w["code"] for w in body["warnings"]) == case.warnings
    assert body["data_mode"] == "DEMO"


def test_seed_covers_every_lookup_result() -> None:
    assert {case.expected for case in SEED_CASES} == set(LookupResult)


def test_no_response_says_safe_genuine_fake_or_verified(
    client: TestClient, session: Session
) -> None:
    seed_demo_data(session)

    for case in SEED_CASES:
        text = json.dumps(post(client, case.registration_number, case.batch_number).json())
        assert not BANNED.search(text), (case.description, text)


def test_every_response_is_labelled_demo(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    for case in SEED_CASES:
        body = post(client, case.registration_number, case.batch_number).json()
        assert body["data_mode"] == "DEMO"
        assert body["disclaimer"].startswith("DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE")
        assert "not NAFDAC's or SON's own system" in body["disclaimer"]
        if body["register_record"]:
            assert body["register_record"]["data_mode"] == "DEMO"


def test_register_cannot_be_written_through_the_api(client: TestClient) -> None:
    paths = list(client.app.openapi()["paths"])

    assert not any("register" in path and path != "/api/auth/register" for path in paths)
    assert not any("credential" in path for path in paths)


# --- Anonymised scan log ------------------------------------------------------------------


def test_each_lookup_logs_an_anonymised_scan(client: TestClient, session: Session) -> None:
    seed_demo_data(session)

    post(client, "nafdac reg no: demo-nafdac-0001", "demo-lot-101")
    post(client, "DEMO-NAFDAC-9999")

    scans = session.exec(select(BatchScan).order_by(BatchScan.created_at)).all()
    assert [s.result for s in scans] == ["REGISTERED_ACTIVE", "REGISTRATION_NOT_FOUND"]
    assert scans[0].input_registration_number == "DEMO-NAFDAC-0001"
    assert scans[0].matched_batch_id is not None
    assert scans[1].matched_batch_id is None


def test_scan_log_has_no_identifying_columns(engine) -> None:
    columns = {c["name"] for c in inspect(engine).get_columns("batch_scan")}

    assert columns == {
        "scan_id",
        "created_at",
        "input_registration_number",
        "input_batch_number",
        "matched_batch_id",
        "result",
    }


def test_lookups_are_rate_limited(make_client) -> None:
    client = make_client(client_ip="203.0.113.77")

    statuses = [post(client, "DEMO-NAFDAC-0001").status_code for _ in range(21)]

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_seed_is_idempotent(session: Session) -> None:
    seed_demo_data(session)
    seed_demo_data(session)

    assert len(session.exec(select(Company)).all()) == 4
    assert len(session.exec(select(RegulatorRegister)).all()) == 7
