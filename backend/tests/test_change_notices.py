"""Change notices: pending notices change nothing, approval applies changes atomically with
history, attachments are type- and size-checked and stored privately (D68-D74)."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AppUser,
    AuditLog,
    ChangeNotice,
    ChangeNoticeField,
    Company,
    NoticeAttachment,
    Product,
    ProductBatch,
)
from app.models.enums import CompanyReviewStatus, MemberRole, ProductStatus, ReviewStatus
from tests import factories as f

PASSWORD = "correct-horse-battery"
PDF = b"%PDF-1.4\n% fictional demo document\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture
def upload_dir(tmp_path: Path) -> Path:
    return tmp_path / "notices"


@pytest.fixture
def clients(make_client: Callable[..., TestClient], upload_dir: Path):
    """Factory for clients sharing a temporary private upload folder."""
    counter = iter(range(1, 100))

    def build() -> TestClient:
        return make_client(
            settings=Settings(upload_dir=str(upload_dir)), client_ip=f"203.0.113.{next(counter)}"
        )

    return build


def sign_in(client: TestClient, session: Session, **overrides) -> AppUser:
    user = f.make_user(session, password_hash=hash_password(PASSWORD), **overrides)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return user


def setup_company(client: TestClient, session: Session) -> tuple[Company, Product, ProductBatch]:
    user = sign_in(client, session)
    company = f.make_company(session, review_status=CompanyReviewStatus.APPROVED)
    f.make_member(session, user, company, role=MemberRole.OWNER)
    product = f.make_product(
        session,
        company,
        product_code="DEMO-PC-7001",
        registration_number="DEMO-NAFDAC-7001",
        name="Old Name",
        status=ProductStatus.PUBLISHED,
    )
    batch = f.make_batch(
        session, product, batch_number="LOT-7", review_status=ReviewStatus.APPROVED
    )
    f.make_register(session, f.make_agency(session), registration_number="DEMO-NAFDAC-7001")
    return company, product, batch


def submit(client: TestClient, company: Company, **body):
    payload = {"change_type": "PRODUCT_DETAILS", "reason": "Rebranding"} | body
    return client.post(f"/api/companies/{company.company_id}/change-notices", json=payload)


def decide(admin: TestClient, notice_id: str, decision: str, note: str | None = None):
    return admin.post(
        f"/api/admin/change-notices/{notice_id}/decision", json={"decision": decision, "note": note}
    )


def upload(
    client: TestClient,
    company: Company,
    notice_id: str,
    name: str,
    content: bytes,
    ctype="application/octet-stream",
):
    return client.post(
        f"/api/companies/{company.company_id}/change-notices/{notice_id}/attachments",
        files={"file": (name, content, ctype)},
    )


@pytest.fixture
def setup(clients, session: Session):
    company_client, admin_client = clients(), clients()
    company, product, batch = setup_company(company_client, session)
    sign_in(admin_client, session, is_admin=True)
    return company_client, admin_client, company, product, batch


# --- Pending notices change nothing --------------------------------------------------------


def test_pending_notice_leaves_published_data_unchanged(setup, session: Session) -> None:
    company_client, _, company, product, _ = setup

    response = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        proposed_changes={"name": "New Name", "package_size": "750 ml"},
        effective_date="2026-12-01",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["review_status"] == "PENDING_REVIEW"
    assert {(x["field_name"], x["current_value"], x["proposed_value"]) for x in body["fields"]} == {
        ("name", "Old Name", "New Name"),
        ("package_size", None, "750 ml"),
    }
    session.refresh(product)
    assert product.name == "Old Name"
    assert product.package_size is None


def test_clarification_and_rejection_leave_data_unchanged(setup, session: Session) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "X"}
    ).json()["notice_id"]

    clarify = decide(admin_client, notice_id, "REQUEST_CLARIFICATION", "Attach the new label")
    reject = decide(admin_client, notice_id, "REJECT", "No evidence")

    assert clarify.json()["review_status"] == "CLARIFICATION_REQUESTED"
    assert reject.json()["review_status"] == "REJECTED"
    session.refresh(product)
    assert product.name == "Old Name"


# --- Approval applies changes and keeps history ---------------------------------------------


def test_approval_updates_product_and_keeps_history(setup, session: Session) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        proposed_changes={"name": "New Name", "brand": "New Brand"},
    ).json()["notice_id"]
    old_brand = product.brand

    response = decide(admin_client, notice_id, "APPROVE", "Label checked")

    assert response.status_code == 200
    assert response.json()["review_status"] == "APPROVED"
    session.refresh(product)
    assert (product.name, product.brand) == ("New Name", "New Brand")
    rows = {
        r.field_name: r
        for r in session.exec(
            select(ChangeNoticeField).where(ChangeNoticeField.notice_id == notice_id)
        )
    }
    assert rows["name"].applied_old_value == "Old Name"
    assert rows["brand"].applied_old_value == old_brand
    notice = session.get(ChangeNotice, notice_id)
    assert notice.reviewed_by_user_id is not None and notice.reviewed_at is not None
    applied = session.exec(
        select(AuditLog).where(
            AuditLog.entity_id == product.product_id, AuditLog.action == "change_notice_applied"
        )
    ).one()
    assert applied.old_values == {"name": "Old Name", "brand": old_brand}
    assert applied.new_values["name"] == "New Name"


def test_approval_updates_batch_dates(setup, session: Session) -> None:
    company_client, admin_client, company, _, batch = setup
    notice_id = submit(
        company_client,
        company,
        batch_id=str(batch.batch_id),
        change_type="BATCH_DETAILS",
        proposed_changes={"expiry_date": "2030-01-31"},
    ).json()["notice_id"]

    decide(admin_client, notice_id, "APPROVE")

    session.refresh(batch)
    assert batch.expiry_date.isoformat() == "2030-01-31"


def test_approved_change_shows_in_lookup(setup, session: Session) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        proposed_changes={"name": "Shown Name"},
    ).json()["notice_id"]

    before = company_client.post(
        "/api/lookups/registration",
        json={"registration_number": "DEMO-NAFDAC-7001", "batch_number": "LOT-7"},
    )
    decide(admin_client, notice_id, "APPROVE")
    after = company_client.post(
        "/api/lookups/registration",
        json={"registration_number": "DEMO-NAFDAC-7001", "batch_number": "LOT-7"},
    )

    assert before.json()["product"]["name"] == "Old Name"
    assert after.json()["product"]["name"] == "Shown Name"


def test_stale_notice_is_not_applied(setup, session: Session) -> None:
    company_client, admin_client, company, product, _ = setup
    first = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "A"}
    ).json()
    second = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        proposed_changes={"name": "B", "brand": "Changed"},
    ).json()
    decide(admin_client, first["notice_id"], "APPROVE")

    response = decide(admin_client, second["notice_id"], "APPROVE")

    assert response.status_code == 409
    session.refresh(product)
    assert product.name == "A"
    assert product.brand != "Changed"  # nothing from the stale notice applied
    assert session.get(ChangeNotice, second["notice_id"]).review_status == "PENDING_REVIEW"


def test_clarification_answer_returns_notice_to_pending_then_approve(
    setup, session: Session
) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        proposed_changes={"name": "New"},
    ).json()["notice_id"]
    decide(admin_client, notice_id, "REQUEST_CLARIFICATION", "Why?")
    blocked = decide(admin_client, notice_id, "APPROVE")

    answer = company_client.post(
        f"/api/companies/{company.company_id}/change-notices/{notice_id}/respond",
        json={"message": "New label from March"},
    )
    approved = decide(admin_client, notice_id, "APPROVE")

    assert blocked.status_code == 409
    assert answer.json()["review_status"] == "PENDING_REVIEW"
    assert "Response to clarification" in answer.json()["reason"]
    assert approved.status_code == 200


def test_clarification_needs_a_note(setup) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "N"}
    ).json()["notice_id"]

    assert decide(admin_client, notice_id, "REQUEST_CLARIFICATION").status_code == 422


def test_decided_notice_cannot_be_decided_again(setup) -> None:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "N"}
    ).json()["notice_id"]
    decide(admin_client, notice_id, "APPROVE")

    assert decide(admin_client, notice_id, "REJECT").status_code == 409


# --- Validation of proposed changes ----------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"product_code": "DEMO-PC-NEW"},
        {"unknown_field": "x"},
        {"name": None},
        {"name": ""},
        {"name": "Old Name"},  # no actual change
    ],
)
def test_invalid_product_changes_are_rejected(setup, session: Session, changes: dict) -> None:
    company_client, _, company, product, _ = setup

    response = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes=changes
    )

    assert response.status_code == 422
    assert session.exec(select(ChangeNotice)).all() == []


def test_batch_number_cannot_be_changed(setup) -> None:
    company_client, _, company, _, batch = setup

    response = submit(
        company_client,
        company,
        batch_id=str(batch.batch_id),
        proposed_changes={"batch_number": "LOT-8"},
    )

    assert response.status_code == 422


def test_batch_expiry_before_production_is_rejected(setup, session: Session) -> None:
    company_client, _, company, _, batch = setup
    batch.production_date = batch.expiry_date = None
    session.add(batch)
    session.flush()

    response = submit(
        company_client, company, batch_id=str(batch.batch_id),
        proposed_changes={"production_date": "2027-01-01", "expiry_date": "2026-01-01"},
    )  # fmt: skip

    assert response.status_code == 422


def test_exactly_one_target_required(setup) -> None:
    company_client, _, company, product, batch = setup

    both = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        batch_id=str(batch.batch_id),
        proposed_changes={"name": "N"},
    )
    neither = submit(company_client, company, proposed_changes={"name": "N"})

    assert both.status_code == neither.status_code == 422


def test_client_cannot_set_review_fields(setup, session: Session) -> None:
    company_client, _, company, product, _ = setup

    response = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "N"},
        review_status="APPROVED", reviewed_by_user_id=str(company.company_id),
    )  # fmt: skip

    notice = session.get(ChangeNotice, response.json()["notice_id"])
    assert notice.review_status == "PENDING_REVIEW"
    assert notice.reviewed_by_user_id is None


# --- Ownership -------------------------------------------------------------------------------


def test_member_cannot_submit_for_another_companys_product(setup, session: Session) -> None:
    company_client, _, company, _, _ = setup
    other_product = f.make_product(session, f.make_company(session), product_code="DEMO-PC-OTHER")

    response = submit(
        company_client,
        company,
        product_id=str(other_product.product_id),
        proposed_changes={"name": "N"},
    )

    assert response.status_code == 404


def test_member_cannot_read_another_companys_notices(setup, session: Session) -> None:
    company_client, _, _, _, _ = setup
    other = f.make_company(session)

    assert (
        company_client.get(f"/api/companies/{other.company_id}/change-notices").status_code == 403
    )


def test_company_cannot_approve_its_own_notice(setup) -> None:
    company_client, _, company, product, _ = setup
    notice_id = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "N"}
    ).json()["notice_id"]

    assert decide(company_client, notice_id, "APPROVE").status_code == 403


# --- Attachments -----------------------------------------------------------------------------


@pytest.fixture
def notice(setup) -> tuple[TestClient, TestClient, Company, str]:
    company_client, admin_client, company, product, _ = setup
    notice_id = submit(
        company_client, company, product_id=str(product.product_id), proposed_changes={"name": "N"}
    ).json()["notice_id"]
    return company_client, admin_client, company, notice_id


@pytest.mark.parametrize(
    ("name", "content", "mime"),
    [
        ("label.pdf", PDF, "application/pdf"),
        ("photo.PNG", PNG, "image/png"),
        ("scan.jpeg", JPG, "image/jpeg"),
    ],
)
def test_allowed_files_are_stored_under_random_keys(
    notice, session: Session, upload_dir: Path, name: str, content: bytes, mime: str
) -> None:
    company_client, _, company, notice_id = notice

    response = upload(company_client, company, notice_id, name, content)

    assert response.status_code == 201
    assert response.json()["mime_type"] == mime
    stored = session.exec(select(NoticeAttachment)).one()
    assert len(stored.storage_key) == 32 and name not in stored.storage_key
    assert (upload_dir / stored.storage_key).read_bytes() == content
    assert [p.name for p in upload_dir.iterdir()] == [stored.storage_key]


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("virus.exe", b"MZ\x90\x00"),
        ("notes.txt", b"hello"),
        ("page.html", b"<html></html>"),
        ("fake.pdf", b"<html>not a pdf</html>"),  # right extension, wrong content
        ("fake.png", PDF),  # PDF bytes renamed to .png
        ("noextension", PDF),
        ("empty.pdf", b""),
    ],
)
def test_bad_file_types_are_rejected(
    notice, session: Session, upload_dir: Path, name: str, content: bytes
) -> None:
    company_client, _, company, notice_id = notice

    response = upload(company_client, company, notice_id, name, content, "application/pdf")

    assert response.status_code == 422
    assert session.exec(select(NoticeAttachment)).all() == []
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_oversized_file_is_rejected(notice, session: Session) -> None:
    company_client, _, company, notice_id = notice

    response = upload(company_client, company, notice_id, "big.pdf", PDF + b"0" * (5 * 1024 * 1024))

    assert response.status_code == 413
    assert session.exec(select(NoticeAttachment)).all() == []


def test_attachment_limit_per_notice(notice) -> None:
    company_client, _, company, notice_id = notice
    statuses = [
        upload(company_client, company, notice_id, f"f{i}.pdf", PDF).status_code for i in range(6)
    ]

    assert statuses == [201] * 5 + [422]


def test_no_attachments_after_decision(notice) -> None:
    company_client, admin_client, company, notice_id = notice
    decide(admin_client, notice_id, "REJECT")

    assert upload(company_client, company, notice_id, "late.pdf", PDF).status_code == 409


def test_attachment_download_is_private(notice, clients, session: Session) -> None:
    company_client, admin_client, company, notice_id = notice
    attachment_id = upload(company_client, company, notice_id, "label.pdf", PDF).json()[
        "attachment_id"
    ]
    outsider = clients()
    other_company = f.make_company(session)
    outsider_user = sign_in(outsider, session)
    f.make_member(session, outsider_user, other_company)
    anonymous = clients()

    own = company_client.get(f"/api/companies/{company.company_id}/attachments/{attachment_id}")
    admin = admin_client.get(f"/api/admin/attachments/{attachment_id}")
    other = outsider.get(f"/api/companies/{other_company.company_id}/attachments/{attachment_id}")
    cross = outsider.get(f"/api/companies/{company.company_id}/attachments/{attachment_id}")
    anon = anonymous.get(f"/api/admin/attachments/{attachment_id}")

    assert own.status_code == admin.status_code == 200
    assert own.content == PDF
    assert own.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in own.headers["content-disposition"]
    assert other.status_code == 404
    assert cross.status_code == 403
    assert anon.status_code == 401


def test_original_filename_is_sanitised(notice, session: Session) -> None:
    company_client, _, company, notice_id = notice

    upload(company_client, company, notice_id, "../../etc/<label>.pdf", PDF)

    assert session.exec(select(NoticeAttachment)).one().original_filename == "_label_.pdf"


def test_registration_number_change_goes_through_review(setup, session: Session) -> None:
    company_client, admin_client, company, product, _ = setup
    notice = submit(
        company_client,
        company,
        product_id=str(product.product_id),
        change_type="LABEL",
        proposed_changes={"registration_number": " nafdac reg no: demo-nafdac-7002 "},
    ).json()

    assert notice["fields"][0]["proposed_value"] == "DEMO-NAFDAC-7002"  # normalised
    session.refresh(product)
    assert product.registration_number == "DEMO-NAFDAC-7001"  # unchanged while pending
    decide(admin_client, notice["notice_id"], "APPROVE")
    session.refresh(product)
    assert product.registration_number == "DEMO-NAFDAC-7002"
