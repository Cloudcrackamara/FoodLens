"""Database-level rules from docs/SCHEMA.md. Each test runs in a rolled-back transaction."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from alembic import command
from app.models import NoticeAttachment, OrderBatchAllocation
from app.models.enums import (
    AttachmentMimeType,
    ChangeNoticeStatus,
    CompanyReviewStatus,
    DataMode,
    MembershipStatus,
    ProductStatus,
    ReviewStatus,
)
from tests import factories as f


def test_migrations_match_models(alembic_config: Config, engine) -> None:
    # Raises if the models have changes no migration covers.
    command.check(alembic_config)


def test_every_table_has_uuid_pk_and_created_at(engine) -> None:
    inspector = inspect(engine)
    for table in SQLModel.metadata.sorted_tables:
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        pk = inspector.get_pk_constraint(table.name)["constrained_columns"]
        assert len(pk) == 1, table.name
        assert str(columns[pk[0]]["type"]) == "UUID", table.name
        assert "created_at" in columns, table.name


def test_append_only_tables_have_no_updated_at(engine) -> None:
    inspector = inspect(engine)
    for name in ("audit_log", "change_notice_field", "notice_attachment"):
        assert "updated_at" not in {c["name"] for c in inspector.get_columns(name)}


def test_no_payment_columns_anywhere(engine) -> None:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            assert "payment" not in column["name"], f"{table}.{column['name']}"
            assert "price" not in column["name"], f"{table}.{column['name']}"


def test_new_records_default_to_unreviewed_states(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    member = f.make_member(session, user, company)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)
    record = f.make_register(session, f.make_agency(session))
    notice = f.make_notice(session, company, user, product_id=product.product_id)

    assert user.is_admin is False
    assert user.is_active is True
    assert company.review_status == CompanyReviewStatus.PENDING_REVIEW
    assert company.reviewed_by_user_id is None
    assert member.membership_status == MembershipStatus.ACTIVE
    assert member.is_public_contact is False
    assert product.status == ProductStatus.DRAFT
    assert batch.review_status == ReviewStatus.PENDING_REVIEW
    assert record.data_mode == DataMode.DEMO
    assert product.registration_number is None
    assert notice.review_status == ChangeNoticeStatus.PENDING_REVIEW
    assert isinstance(product.product_id, uuid.UUID)
    assert product.created_at is not None


def test_batch_number_unique_per_product(session: Session) -> None:
    product = f.make_product(session, f.make_company(session))
    f.make_batch(session, product, batch_number="DEMO-LOT-001")

    with pytest.raises(IntegrityError):
        f.make_batch(session, product, batch_number="DEMO-LOT-001")


def test_same_batch_number_allowed_on_different_products(session: Session) -> None:
    company = f.make_company(session)
    first = f.make_batch(session, f.make_product(session, company), batch_number="DEMO-LOT-001")
    second = f.make_batch(session, f.make_product(session, company), batch_number="DEMO-LOT-001")

    assert first.batch_id != second.batch_id


def test_product_code_is_unique(session: Session) -> None:
    company = f.make_company(session)
    f.make_product(session, company, product_code="DEMO-PC-1")

    with pytest.raises(IntegrityError):
        f.make_product(session, company, product_code="DEMO-PC-1")


def test_user_belongs_to_at_most_one_company(session: Session) -> None:
    user = f.make_user(session)
    f.make_member(session, user, f.make_company(session))

    with pytest.raises(IntegrityError):
        f.make_member(session, user, f.make_company(session))


def test_user_email_is_unique(session: Session) -> None:
    f.make_user(session, email="same@example.test")

    with pytest.raises(IntegrityError):
        f.make_user(session, email="same@example.test")


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("company", "review_status"),
        ("product", "status"),
        ("product_batch", "review_status"),
        ("regulator_register", "data_mode"),
        ("regulator_register", "status"),
    ],
)
def test_enum_columns_reject_unknown_values(session: Session, table: str, column: str) -> None:
    company = f.make_company(session)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)
    record = f.make_register(session, f.make_agency(session))
    ids = {
        "company": ("company_id", company.company_id),
        "product": ("product_id", product.product_id),
        "product_batch": ("batch_id", batch.batch_id),
        "regulator_register": ("register_id", record.register_id),
    }
    pk_name, pk_value = ids[table]

    with pytest.raises(IntegrityError):
        session.execute(
            text(f"UPDATE {table} SET {column} = 'SAFE' WHERE {pk_name} = :id"),
            {"id": pk_value},
        )


def test_batch_expiry_cannot_precede_production(session: Session) -> None:
    product = f.make_product(session, f.make_company(session))

    with pytest.raises(IntegrityError):
        f.make_batch(
            session,
            product,
            production_date=date(2026, 5, 1),
            expiry_date=date(2026, 4, 1),
        )


def test_registration_number_is_unique_in_register(session: Session) -> None:
    agency = f.make_agency(session)
    f.make_register(session, agency, registration_number="DEMO-NAFDAC-0001")

    with pytest.raises(IntegrityError):
        f.make_register(session, agency, registration_number="DEMO-NAFDAC-0001")


def test_products_may_share_a_registration_number(session: Session) -> None:
    company = f.make_company(session)
    first = f.make_product(session, company, registration_number="DEMO-NAFDAC-0001")
    copy = f.make_product(session, company, registration_number="DEMO-NAFDAC-0001")

    assert first.product_id != copy.product_id


def test_credential_table_is_gone(engine) -> None:
    assert "credential_record" not in inspect(engine).get_table_names()


def test_change_notice_requires_exactly_one_target(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    product = f.make_product(session, company)
    batch = f.make_batch(session, product)

    with pytest.raises(IntegrityError):
        with session.begin_nested():
            f.make_notice(session, company, user)

    with pytest.raises(IntegrityError):
        f.make_notice(
            session, company, user, product_id=product.product_id, batch_id=batch.batch_id
        )


def test_change_notice_target_must_exist(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)

    with pytest.raises(IntegrityError):
        f.make_notice(session, company, user, product_id=uuid.uuid4())


def test_attachment_size_limited_to_5_mb(session: Session) -> None:
    user = f.make_user(session)
    company = f.make_company(session)
    notice = f.make_notice(
        session, company, user, product_id=f.make_product(session, company).product_id
    )

    session.add(
        NoticeAttachment(
            notice_id=notice.notice_id,
            storage_key="private/ok.pdf",
            original_filename="ok.pdf",
            mime_type=AttachmentMimeType.PDF,
            size_bytes=5 * 1024 * 1024,
        )
    )
    session.flush()

    with pytest.raises(IntegrityError):
        session.add(
            NoticeAttachment(
                notice_id=notice.notice_id,
                storage_key="private/too-big.pdf",
                original_filename="too-big.pdf",
                mime_type=AttachmentMimeType.PDF,
                size_bytes=5 * 1024 * 1024 + 1,
            )
        )
        session.flush()


def test_order_buyer_and_seller_must_differ(session: Session) -> None:
    company = f.make_company(session)

    with pytest.raises(IntegrityError):
        f.make_order(session, company, company, f.make_user(session))


def test_order_quantities_must_be_positive(session: Session) -> None:
    seller = f.make_company(session)
    product = f.make_product(session, seller)
    order = f.make_order(session, f.make_company(session), seller, f.make_user(session))
    line = f.make_line(session, order, product)
    batch = f.make_batch(session, product)

    with pytest.raises(IntegrityError):
        with session.begin_nested():
            f.make_line(session, order, product, quantity=Decimal("0"))

    with pytest.raises(IntegrityError):
        session.add(
            OrderBatchAllocation(
                line_id=line.line_id, batch_id=batch.batch_id, allocated_quantity=Decimal("-1")
            )
        )
        session.flush()
