"""Unit and carton codes: generation, one-time label file, release, void, allocations
(D110, D131, D138, D139, D142). The label file is the only place raw codes ever appear."""

import csv
import io
import logging
import os
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, func, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AppUser,
    AuditLog,
    BatchAllocation,
    Carton,
    Company,
    LifecycleEvent,
    ProductBatch,
    ProductUnit,
)
from app.models.enums import (
    CompanyReviewStatus,
    EventSource,
    LifecycleEventType,
    LifecycleStatus,
    MemberRole,
    ProductStatus,
    ReviewStatus,
)
from app.services import identity, labels
from tests import factories as f

PASSWORD = "correct-horse-battery"
BASE_URL = "https://labels.foodlens-demo.example"
SETTINGS = Settings(public_base_url=BASE_URL)


@dataclass
class Maker:
    client: TestClient
    user: AppUser
    company: Company
    batch: ProductBatch

    @property
    def url(self) -> str:
        return f"/api/companies/{self.company.company_id}/batches/{self.batch.batch_id}"


def sign_in(client: TestClient, session: Session, **overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **overrides)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user


@pytest.fixture
def maker_factory(make_client: Callable[..., TestClient], session: Session):
    """A signed-in member of a manufacturer with one published batch."""

    def build(
        role=MemberRole.OWNER, status=CompanyReviewStatus.APPROVED, company=None, **flags
    ) -> Maker:
        client = make_client(settings=SETTINGS)
        user = sign_in(client, session)
        if company is None:
            company = f.make_company(session, review_status=status, **flags)
        f.make_member(session, user, company, role=role)
        product = f.make_product(session, company, status=ProductStatus.PUBLISHED)
        batch = f.make_batch(
            session, product, batch_number="DEMO-LOT-9", review_status=ReviewStatus.APPROVED
        )
        return Maker(client, user, company, batch)

    return build


@pytest.fixture
def maker(maker_factory) -> Maker:
    return maker_factory()


def generate(maker: Maker, **body):
    return maker.client.post(f"{maker.url}/units", json={"quantity": 5} | body)


@dataclass
class LabelFile:
    names: list[str]
    units: list[dict]
    cartons: list[dict]
    pdf: bytes
    note: str

    @property
    def tokens(self) -> list[str]:
        return [row["token"] for row in self.cartons + self.units]


def read_zip(content: bytes) -> LabelFile:
    archive = zipfile.ZipFile(io.BytesIO(content))
    names = archive.namelist()

    def rows(name: str) -> list[dict]:
        if name not in names:
            return []
        return list(csv.DictReader(io.StringIO(archive.read(name).decode())))

    return LabelFile(
        names=names,
        units=rows("units.csv"),
        cartons=rows("cartons.csv"),
        pdf=archive.read("labels.pdf"),
        note=archive.read("READ-ME-FIRST.txt").decode(),
    )


# --- Generation -------------------------------------------------------------------------------


def test_owner_generates_units_cartons_and_issued_events(maker: Maker, session: Session) -> None:
    response = generate(maker, quantity=10, units_per_carton=4)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    file = read_zip(response.content)
    assert sorted(file.names) == ["READ-ME-FIRST.txt", "cartons.csv", "labels.pdf", "units.csv"]
    assert [row["carton_ref"] for row in file.cartons] == ["C001", "C002", "C003"]
    assert [row["carton_ref"] for row in file.units] == ["C001"] * 4 + ["C002"] * 4 + ["C003"] * 2

    units = session.exec(select(ProductUnit).where(ProductUnit.batch_id == maker.batch.batch_id))
    units = units.all()
    cartons = session.exec(select(Carton).where(Carton.batch_id == maker.batch.batch_id)).all()
    assert len(units) == 10 and len(cartons) == 3
    assert {u.lifecycle_status for u in units} == {LifecycleStatus.ISSUED}
    assert {u.current_holder_company_id for u in units} == {maker.company.company_id}
    by_carton = {}
    for unit in units:
        by_carton[unit.parent_carton_id] = by_carton.get(unit.parent_carton_id, 0) + 1
    assert sorted(by_carton.values()) == [2, 4, 4]

    events = session.exec(
        select(LifecycleEvent).where(LifecycleEvent.event_type == LifecycleEventType.ISSUED)
    ).all()
    assert len(events) == 13
    assert len({e.group_id for e in events}) == 1
    assert {e.source for e in events} == {EventSource.MANUFACTURER}
    assert {e.actor_user_id for e in events} == {maker.user.user_id}


def test_stored_hashes_match_the_printed_tokens(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=3, units_per_carton=3).content)

    unit_hashes = set(session.exec(select(ProductUnit.qr_token_hash)).all())
    carton_hashes = set(session.exec(select(Carton.qr_token_hash)).all())
    assert {identity.token_hash(r["token"]) for r in file.units} == unit_hashes
    assert {identity.token_hash(r["token"]) for r in file.cartons} == carton_hashes


def test_csv_has_four_columns_and_verification_urls(maker: Maker) -> None:
    content = generate(maker, quantity=2).content
    archive = zipfile.ZipFile(io.BytesIO(content))
    header = archive.read("units.csv").decode().splitlines()[0]
    file = read_zip(content)

    assert header == "batch,carton_ref,token,verification_url"
    assert "cartons.csv" not in file.names  # no cartons requested
    for row in file.units:
        assert row["batch"] == "DEMO-LOT-9"
        assert row["carton_ref"] == ""
        assert re.fullmatch(r"[0-9ABCDEFGHJKMNPQRSTVWXYZ]{26}", row["token"])
        assert row["verification_url"] == f"{BASE_URL}/p/{row['token']}"


def test_pdf_prints_grouped_token_check_host_and_base_url(maker: Maker) -> None:
    file = read_zip(generate(maker, quantity=2, units_per_carton=2).content)

    for token in file.tokens:
        first, second = labels.printed_lines(token)
        assert f"{first} {second}" == identity.grouped(token)
        assert first.encode() in file.pdf and second.encode() in file.pdf
    assert b"Type the code at labels.foodlens-demo.example/check" in file.pdf
    assert BASE_URL.encode() in file.pdf
    assert b"CARTON C001" in file.pdf


def test_qr_uses_error_correction_m_and_the_verification_url() -> None:
    qr = labels.make_qr(BASE_URL, "7Q2M8KD3XH4N9VBT6C1RZJ5WAE")

    assert qr.error == "M"
    assert qr.designator.endswith("-M")


def test_warning_note_says_the_file_holds_every_code(maker: Maker) -> None:
    note = read_zip(generate(maker).content).note

    assert "holds every raw code" in note
    assert "Delete every copy after printing" in note


@pytest.mark.parametrize(("size", "warned"), [(12, True), (14.9, True), (15, False), (25, False)])
def test_small_qr_size_is_allowed_with_a_warning(maker: Maker, size: float, warned: bool) -> None:
    response = generate(maker, qr_size_mm=size)

    assert response.status_code == 200
    assert ("x-foodlens-label-warning" in response.headers) is warned


@pytest.mark.parametrize(
    "body",
    [
        {"quantity": 0},
        {"quantity": 2001},
        {"quantity": 5, "qr_size_mm": 9},
        {"quantity": 5, "units_per_carton": 0},
        {"quantity": 5, "units_per_carton": 6},
    ],
)
def test_invalid_generation_requests_are_refused(maker: Maker, session: Session, body) -> None:
    response = maker.client.post(f"{maker.url}/units", json=body)

    assert response.status_code == 422
    assert session.exec(select(func.count()).select_from(ProductUnit)).one() == 0


def test_client_cannot_choose_tokens_status_or_holder(maker: Maker, session: Session) -> None:
    other = f.make_company(session)
    response = generate(
        maker,
        quantity=1,
        token="0" * 26,
        qr_token_hash="0" * 64,
        lifecycle_status="SOLD",
        current_holder_company_id=str(other.company_id),
    )

    [row] = read_zip(response.content).units
    unit = session.exec(select(ProductUnit)).one()
    assert row["token"] != "0" * 26
    assert unit.lifecycle_status == LifecycleStatus.ISSUED
    assert unit.current_holder_company_id == maker.company.company_id


# --- Raw codes never stored or logged ---------------------------------------------------------


def test_raw_tokens_never_reach_the_database(maker: Maker, session: Session, engine) -> None:
    file = read_zip(generate(maker, quantity=20, units_per_carton=5).content)
    maker.client.post(f"{maker.url}/release", json={})
    maker.client.post(
        f"{maker.url}/void", json={"reason": "test", "codes": [file.units[0]["token"]]}
    )

    dump = []
    for table in inspect(engine).get_table_names():
        dump += [row[0] for row in session.execute(text(f"SELECT CAST(t AS text) FROM {table} t"))]
    everything = "\n".join(dump).upper()
    assert identity.token_hash(file.tokens[0]) in "\n".join(dump)  # the hash is stored
    for token in file.tokens:
        assert token not in everything
        assert identity.grouped(token) not in everything


def test_raw_tokens_never_reach_the_logs(maker: Maker, caplog) -> None:
    caplog.set_level(logging.DEBUG)

    file = read_zip(generate(maker, quantity=5, units_per_carton=5).content)

    for token in file.tokens:
        assert token not in caplog.text
        assert identity.grouped(token) not in caplog.text


def test_tokens_do_not_depend_on_unit_ids(maker: Maker, session: Session, monkeypatch) -> None:
    # The token is exactly the encoded random bytes, whatever IDs the rows get.
    supplied = [os.urandom(16) for _ in range(6)]
    feed = iter(supplied)
    monkeypatch.setattr(identity.secrets, "token_bytes", lambda n: next(feed))

    file = read_zip(generate(maker, quantity=6).content)

    assert sorted(file.tokens) == sorted(identity.encode(b) for b in supplied)
    unit_ids = [u.hex.upper() for u in session.exec(select(ProductUnit.unit_id)).all()]
    for token in file.tokens:
        assert not any(uid[:8] in token or uid[-8:] in token for uid in unit_ids)


def test_tokens_share_no_prefix_or_sequence(maker: Maker) -> None:
    tokens = read_zip(generate(maker, quantity=50).content).tokens

    assert len(os.path.commonprefix(tokens)) < 2
    assert len({t[:6] for t in tokens}) == 50


# --- One-time download ------------------------------------------------------------------------


def test_label_file_cannot_be_downloaded_again(maker: Maker, session: Session) -> None:
    first = read_zip(generate(maker, quantity=3, units_per_carton=2).content)
    summary = maker.client.get(f"{maker.url}/units")
    second = read_zip(generate(maker, quantity=3, units_per_carton=2).content)

    assert summary.status_code == 200
    assert summary.headers["content-type"].startswith("application/json")
    for token in first.tokens:
        assert token not in summary.text
        assert identity.token_hash(token) not in summary.text
    # Generating again makes new codes and carries on the carton numbers.
    assert set(first.tokens).isdisjoint(second.tokens)
    assert [r["carton_ref"] for r in second.cartons] == ["C003", "C004"]
    assert summary.json()["units"] == {"ISSUED": 3}
    assert session.exec(select(func.count()).select_from(ProductUnit)).one() == 6


def test_generation_is_audited_without_codes(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=2).content)

    entry = session.exec(select(AuditLog).where(AuditLog.action == "codes_generated")).one()
    assert entry.actor_user_id == maker.user.user_id
    assert entry.new_values["units"] == 2
    assert not any(t in str(entry.new_values) for t in file.tokens)


# --- Who may generate -------------------------------------------------------------------------


def test_staff_cannot_generate(maker_factory, session: Session) -> None:
    staff = maker_factory(role=MemberRole.STAFF)

    assert generate(staff).status_code == 403
    assert session.exec(select(func.count()).select_from(ProductUnit)).one() == 0


def test_pending_manufacturer_cannot_generate(maker_factory) -> None:
    pending = maker_factory(status=CompanyReviewStatus.PENDING_REVIEW)

    assert generate(pending).status_code == 409


def test_non_manufacturer_cannot_generate(maker_factory) -> None:
    distributor = maker_factory(is_manufacturer=False, is_distributor=True)

    assert generate(distributor).status_code == 403


def test_other_company_cannot_generate_for_a_batch(maker: Maker, maker_factory) -> None:
    outsider = maker_factory()

    # Through the victim's company path: not a member.
    forbidden = outsider.client.post(f"{maker.url}/units", json={"quantity": 1})
    # Through its own company path with the victim's batch: looks missing.
    own_path = f"/api/companies/{outsider.company.company_id}/batches/{maker.batch.batch_id}/units"
    missing = outsider.client.post(own_path, json={"quantity": 1})

    assert forbidden.status_code == 403
    assert missing.status_code == 404


def test_signed_out_user_cannot_generate(maker: Maker, client: TestClient) -> None:
    assert client.post(f"{maker.url}/units", json={"quantity": 1}).status_code == 401


def test_unpublished_batch_cannot_get_codes(maker: Maker, session: Session) -> None:
    maker.batch.review_status = ReviewStatus.PENDING_REVIEW
    session.add(maker.batch)
    session.flush()

    assert generate(maker).status_code == 409


# --- Release ----------------------------------------------------------------------------------


def _statuses(session: Session, batch: ProductBatch) -> dict:
    rows = session.exec(
        select(ProductUnit.lifecycle_status, func.count())
        .where(ProductUnit.batch_id == batch.batch_id)
        .group_by(ProductUnit.lifecycle_status)
    ).all()
    return dict(rows)


def test_release_whole_batch_writes_events_and_sets_status(maker: Maker, session: Session) -> None:
    generate(maker, quantity=4, units_per_carton=2)

    response = maker.client.post(f"{maker.url}/release", json={})

    assert response.json() == {"units": 4}
    assert _statuses(session, maker.batch) == {LifecycleStatus.RELEASED: 4}
    released = session.exec(
        select(LifecycleEvent).where(LifecycleEvent.event_type == LifecycleEventType.RELEASED)
    ).all()
    assert len(released) == 6  # 4 units + 2 cartons
    assert {c.lifecycle_status for c in session.exec(select(Carton)).all()} == {
        LifecycleStatus.RELEASED
    }
    session.refresh(maker.batch)
    assert maker.batch.released_at is not None
    assert maker.client.post(f"{maker.url}/release", json={}).status_code == 409


def test_release_one_carton(maker: Maker, session: Session) -> None:
    generate(maker, quantity=4, units_per_carton=2)

    response = maker.client.post(f"{maker.url}/release", json={"carton_ref": "c002"})

    assert response.json() == {"units": 2}
    summary = maker.client.get(f"{maker.url}/units").json()
    assert summary["units"] == {"ISSUED": 2, "RELEASED": 2}
    assert [(c["carton_ref"], c["status"]) for c in summary["cartons"]] == [
        ("C001", "ISSUED"),
        ("C002", "RELEASED"),
    ]
    session.refresh(maker.batch)
    assert maker.batch.released_at is None
    unknown = maker.client.post(f"{maker.url}/release", json={"carton_ref": "C999"})
    assert unknown.status_code == 422


def test_staff_can_release(maker: Maker, maker_factory) -> None:
    generate(maker, quantity=2)
    staff = maker_factory(role=MemberRole.STAFF, company=maker.company)

    assert staff.client.post(f"{maker.url}/release", json={}).json() == {"units": 2}


def test_new_codes_reopen_a_released_batch(maker: Maker, session: Session) -> None:
    generate(maker, quantity=2)
    maker.client.post(f"{maker.url}/release", json={})
    generate(maker, quantity=1)

    session.refresh(maker.batch)
    assert maker.batch.released_at is None


# --- Void -------------------------------------------------------------------------------------


def test_void_before_release_needs_a_reason_and_records_who(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=3).content)
    token = file.units[0]["token"]

    blank = maker.client.post(f"{maker.url}/void", json={"reason": " ", "codes": [token]})
    response = maker.client.post(
        f"{maker.url}/void", json={"reason": "Label file lost", "codes": [token.lower()]}
    )

    assert blank.status_code == 422
    assert response.json() == {"units": 1}
    [event] = session.exec(
        select(LifecycleEvent).where(LifecycleEvent.event_type == LifecycleEventType.VOIDED)
    ).all()
    assert event.reason == "Label file lost"
    assert event.actor_user_id == maker.user.user_id
    assert event.occurred_at is not None
    assert _statuses(session, maker.batch) == {
        LifecycleStatus.VOIDED: 1,
        LifecycleStatus.ISSUED: 2,
    }
    entry = session.exec(select(AuditLog).where(AuditLog.action == "units_voided")).one()
    assert entry.new_values["reason"] == "Label file lost"
    assert token not in str(entry.new_values)


def test_void_after_release_is_refused(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=2, units_per_carton=2).content)
    maker.client.post(f"{maker.url}/release", json={})

    by_code = maker.client.post(
        f"{maker.url}/void", json={"reason": "x", "codes": [file.units[0]["token"]]}
    )
    by_carton = maker.client.post(
        f"{maker.url}/void", json={"reason": "x", "carton_refs": ["C001"]}
    )
    whole = maker.client.post(f"{maker.url}/void", json={"reason": "x", "whole_batch": True})

    assert by_code.status_code == 409
    assert "recall" in by_code.json()["detail"]
    assert by_carton.status_code == 409
    assert whole.status_code == 409
    assert _statuses(session, maker.batch) == {LifecycleStatus.RELEASED: 2}


def test_void_whole_batch_then_regenerate(maker: Maker, session: Session) -> None:
    generate(maker, quantity=4, units_per_carton=2)
    maker.client.post(f"{maker.url}/release", json={"carton_ref": "C001"})

    response = maker.client.post(
        f"{maker.url}/void", json={"reason": "Printer lost the file", "whole_batch": True}
    )
    again = generate(maker, quantity=2, units_per_carton=2)

    assert response.json() == {"units": 2}  # only the unreleased carton
    summary = maker.client.get(f"{maker.url}/units").json()
    assert summary["units"] == {"RELEASED": 2, "VOIDED": 2, "ISSUED": 2}
    assert [(c["carton_ref"], c["status"]) for c in summary["cartons"]] == [
        ("C001", "RELEASED"),
        ("C002", "VOIDED"),
        ("C003", "ISSUED"),
    ]
    assert again.status_code == 200


def test_already_voided_code_cannot_be_voided_again(maker: Maker) -> None:
    token = read_zip(generate(maker, quantity=1).content).units[0]["token"]
    maker.client.post(f"{maker.url}/void", json={"reason": "x", "codes": [token]})

    again = maker.client.post(f"{maker.url}/void", json={"reason": "x", "codes": [token]})

    assert again.status_code == 409


def test_staff_cannot_void_and_unknown_codes_are_refused(maker: Maker, maker_factory) -> None:
    generate(maker, quantity=1)
    staff = maker_factory(role=MemberRole.STAFF, company=maker.company)

    assert (
        staff.client.post(f"{maker.url}/void", json={"reason": "x", "whole_batch": True})
    ).status_code == 403
    unknown = maker.client.post(f"{maker.url}/void", json={"reason": "x", "codes": ["0" * 26]})
    assert unknown.status_code == 422
    assert "0000" in unknown.json()["detail"]


def test_voided_units_release_nothing(maker: Maker) -> None:
    generate(maker, quantity=2)
    maker.client.post(f"{maker.url}/void", json={"reason": "x", "whole_batch": True})

    assert maker.client.post(f"{maker.url}/release", json={}).status_code == 409


# --- Allocations ------------------------------------------------------------------------------


def _allocate(maker: Maker, session: Session, city: str = "Lagos", **body):
    payload = {"destination_area_id": str(f.area(session, city).area_id)} | body
    return maker.client.post(f"{maker.url}/allocations", json=payload)


def test_allocate_by_quantity_cartons_and_units(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=10, units_per_carton=4).content)
    retailer = f.make_company(
        session, is_manufacturer=False, is_retailer=True, review_status=CompanyReviewStatus.APPROVED
    )
    loose = [r["token"] for r in file.units if r["carton_ref"] == "C003"]

    by_carton = _allocate(maker, session, carton_refs=["C001"], planned_date="2026-11-01")
    by_units = _allocate(
        maker,
        session,
        "Kano",
        unit_codes=loose,
        destination_company_id=str(retailer.company_id),
    )
    by_quantity = _allocate(maker, session, "Abuja", quantity=3)

    assert by_carton.status_code == 201
    assert by_carton.json()["quantity"] == 4
    assert by_carton.json()["carton_refs"] == ["C001"]
    assert by_units.json()["quantity"] == 2
    assert by_units.json()["units_listed"] == 2
    assert by_units.json()["destination_company"]["display_name"] == retailer.display_name
    assert by_quantity.json()["quantity"] == 3
    listed = maker.client.get(f"{maker.url}/allocations").json()
    assert [a["destination_area"]["city"] for a in listed] == ["Lagos", "Kano", "Abuja"]
    assert "token" not in str(listed).lower() and file.tokens[0] not in str(listed)


def test_allocated_total_never_exceeds_live_units(maker: Maker, session: Session) -> None:
    generate(maker, quantity=5)
    _allocate(maker, session, quantity=4)

    over = _allocate(maker, session, "Kano", quantity=2)

    assert over.status_code == 422
    assert "1 of this batch's 5" in over.json()["detail"]


def test_carton_and_unit_sit_in_one_allocation_only(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=6, units_per_carton=3).content)
    in_c001 = [r["token"] for r in file.units if r["carton_ref"] == "C001"]
    in_c002 = [r["token"] for r in file.units if r["carton_ref"] == "C002"]
    _allocate(maker, session, carton_refs=["C001"])
    _allocate(maker, session, unit_codes=in_c002[:1])

    carton_again = _allocate(maker, session, "Kano", carton_refs=["C001"])
    unit_of_listed_carton = _allocate(maker, session, "Kano", unit_codes=in_c001[:1])
    unit_again = _allocate(maker, session, "Kano", unit_codes=in_c002[:1])
    carton_and_own_unit = _allocate(
        maker, session, "Kano", carton_refs=["C002"], unit_codes=in_c002[1:2]
    )

    assert carton_again.status_code == 409
    assert unit_of_listed_carton.status_code == 409
    assert unit_again.status_code == 409
    assert carton_and_own_unit.status_code == 409
    assert session.exec(select(func.count()).select_from(BatchAllocation)).one() == 2


def test_allocation_quantity_must_match_listed_units(maker: Maker, session: Session) -> None:
    generate(maker, quantity=4, units_per_carton=2)

    mismatch = _allocate(maker, session, carton_refs=["C001"], quantity=3)
    nothing = _allocate(maker, session)

    assert mismatch.status_code == 422
    assert nothing.status_code == 422


def test_allocation_destination_must_be_approved_distributor_or_retailer(
    maker: Maker, session: Session
) -> None:
    generate(maker, quantity=2)
    pending = f.make_company(session, is_manufacturer=False, is_distributor=True)
    manufacturer_only = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)

    for company in (pending, manufacturer_only):
        response = _allocate(
            maker, session, quantity=1, destination_company_id=str(company.company_id)
        )
        assert response.status_code == 422


def test_allocation_only_for_own_batch_cartons_and_units(
    maker: Maker, maker_factory, session: Session
) -> None:
    other = maker_factory()
    other_file = read_zip(generate(other, quantity=2, units_per_carton=2).content)
    generate(maker, quantity=2)
    area_id = str(f.area(session).area_id)

    foreign_path = maker.client.post(
        f"{other.url}/allocations", json={"destination_area_id": area_id, "quantity": 1}
    )
    foreign_unit = _allocate(maker, session, unit_codes=[other_file.units[0]["token"]])
    foreign_batch = maker.client.post(
        f"/api/companies/{maker.company.company_id}/batches/{other.batch.batch_id}/allocations",
        json={"destination_area_id": area_id, "quantity": 1},
    )

    assert foreign_path.status_code == 403
    assert foreign_unit.status_code == 422
    assert foreign_batch.status_code == 404


def test_voided_units_are_not_allocated(maker: Maker, session: Session) -> None:
    file = read_zip(generate(maker, quantity=3).content)
    token = file.units[0]["token"]
    maker.client.post(f"{maker.url}/void", json={"reason": "x", "codes": [token]})

    assert _allocate(maker, session, unit_codes=[token]).status_code == 422
    assert _allocate(maker, session, quantity=3).status_code == 422
    assert _allocate(maker, session, quantity=2).status_code == 201


def test_deleting_an_allocation_frees_its_cartons(maker: Maker, session: Session) -> None:
    generate(maker, quantity=2, units_per_carton=2)
    allocation_id = _allocate(maker, session, carton_refs=["C001"]).json()["allocation_id"]

    deleted = maker.client.delete(f"{maker.url}/allocations/{allocation_id}")

    assert deleted.status_code == 204
    assert _allocate(maker, session, "Kano", carton_refs=["C001"]).status_code == 201


def test_staff_can_allocate(maker: Maker, maker_factory, session: Session) -> None:
    generate(maker, quantity=2)
    staff = maker_factory(role=MemberRole.STAFF, company=maker.company)
    area_id = str(f.area(session).area_id)

    response = staff.client.post(
        f"{maker.url}/allocations", json={"destination_area_id": area_id, "quantity": 2}
    )

    assert response.status_code == 201


def test_areas_and_destinations_are_listed(maker: Maker, session: Session) -> None:
    retailer = f.make_company(
        session,
        display_name="Demo Corner Shop (fictional)",
        is_manufacturer=False,
        is_retailer=True,
        review_status=CompanyReviewStatus.APPROVED,
    )

    areas = maker.client.get("/api/areas").json()
    destinations = maker.client.get(
        f"/api/companies/{maker.company.company_id}/allocation-destinations"
    ).json()

    assert "Lagos" in {a["city"] for a in areas}
    assert [d["company_id"] for d in destinations] == [str(retailer.company_id)]
