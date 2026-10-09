"""regulator register replaces credential records

Revision ID: 0004_regulator_register
Revises: 0003_batch_scan
Create Date: 2026-10-09

- Adds regulator_register (simulated NAFDAC/SON register, the only source of registration
  status) and product.registration_number.
- Drops credential_record and change_notice.credential_id (credentials are no longer claims).
- Lookup results change, so existing batch_scan rows are deleted (they hold the old result
  values) and the input column is renamed to input_registration_number.
- CREDENTIAL_DETAILS is removed from change_type (existing rows become OTHER).

Hand-edited: Alembic does not compare CHECK constraints, so those are replaced explicitly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_regulator_register"
down_revision: str | Sequence[str] | None = "0003_batch_scan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_RESULTS = (
    "'INSUFFICIENT_OR_AMBIGUOUS', 'REGISTRATION_NOT_FOUND', "
    "'REGISTRATION_EXPIRED_OR_INACTIVE', 'REGISTRATION_MISMATCH', 'REGISTERED_ACTIVE'"
)
OLD_RESULTS = (
    "'DEMO_RECORD_FOUND', 'BATCH_NOT_FOUND', 'BATCH_EXPIRED', 'DETAILS_MISMATCH', "
    "'CREDENTIAL_EXPIRED_OR_INACTIVE', 'INSUFFICIENT_OR_AMBIGUOUS'"
)
NEW_CHANGE_TYPES = (
    "'PACKAGING', 'LABEL', 'PRODUCT_DETAILS', 'BATCH_DETAILS', 'LOCATION_DETAILS', 'OTHER'"
)
OLD_CHANGE_TYPES = (
    "'PACKAGING', 'LABEL', 'PRODUCT_DETAILS', 'BATCH_DETAILS', 'CREDENTIAL_DETAILS', "
    "'LOCATION_DETAILS', 'OTHER'"
)


def upgrade() -> None:
    # --- regulator register and product registration number -----------------------------
    op.create_table(
        "regulator_register",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("register_id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("registration_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("registered_product_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("registered_company_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("data_mode", sa.String(length=4), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("last_checked_on", sa.Date(), nullable=False),
        sa.CheckConstraint("data_mode IN ('DEMO')", name=op.f("ck_regulator_register_data_mode")),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name=op.f("ck_regulator_register_register_status")
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"],
            ["regulatory_agency.agency_id"],
            name=op.f("fk_regulator_register_agency_id_regulatory_agency"),
        ),
        sa.PrimaryKeyConstraint("register_id", name=op.f("pk_regulator_register")),
        sa.UniqueConstraint(
            "registration_number", name=op.f("uq_regulator_register_registration_number")
        ),
    )
    op.create_index(
        op.f("ix_regulator_register_agency_id"), "regulator_register", ["agency_id"], unique=False
    )
    op.add_column(
        "product",
        sa.Column("registration_number", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_product_registration_number"), "product", ["registration_number"], unique=False
    )

    # --- change notices: remove credential targets and the CREDENTIAL_DETAILS type ----------
    op.execute(
        "DELETE FROM notice_attachment WHERE notice_id IN "
        "(SELECT notice_id FROM change_notice WHERE credential_id IS NOT NULL)"
    )
    op.execute(
        "DELETE FROM change_notice_field WHERE notice_id IN "
        "(SELECT notice_id FROM change_notice WHERE credential_id IS NOT NULL)"
    )
    op.execute("DELETE FROM change_notice WHERE credential_id IS NOT NULL")
    op.drop_constraint(op.f("ck_change_notice_exactly_one_target"), "change_notice", type_="check")
    op.drop_constraint(
        op.f("fk_change_notice_credential_id_credential_record"),
        "change_notice",
        type_="foreignkey",
    )
    op.drop_column("change_notice", "credential_id")
    op.create_check_constraint(
        op.f("ck_change_notice_exactly_one_target"),
        "change_notice",
        "num_nonnulls(product_id, batch_id, location_id) = 1",
    )
    op.drop_constraint(op.f("ck_change_notice_change_type"), "change_notice", type_="check")
    op.execute(
        "UPDATE change_notice SET change_type = 'OTHER' WHERE change_type = 'CREDENTIAL_DETAILS'"
    )
    op.alter_column(
        "change_notice",
        "change_type",
        existing_type=sa.VARCHAR(length=18),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_change_notice_change_type"),
        "change_notice",
        f"change_type IN ({NEW_CHANGE_TYPES})",
    )

    # --- credential records are gone ------------------------------------------------------
    op.drop_index(op.f("ix_credential_record_agency_id"), table_name="credential_record")
    op.drop_index(op.f("ix_credential_record_product_id"), table_name="credential_record")
    op.drop_table("credential_record")

    # --- scan log: new results and registration-number input -------------------------------
    op.execute("DELETE FROM batch_scan")
    op.drop_constraint(op.f("ck_batch_scan_lookup_result"), "batch_scan", type_="check")
    op.alter_column(
        "batch_scan",
        "result",
        existing_type=sa.VARCHAR(length=30),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_batch_scan_lookup_result"), "batch_scan", f"result IN ({NEW_RESULTS})"
    )
    op.alter_column("batch_scan", "input_product_code", new_column_name="input_registration_number")


def downgrade() -> None:
    op.alter_column("batch_scan", "input_registration_number", new_column_name="input_product_code")
    op.execute("DELETE FROM batch_scan")
    op.drop_constraint(op.f("ck_batch_scan_lookup_result"), "batch_scan", type_="check")
    op.alter_column(
        "batch_scan",
        "result",
        existing_type=sa.String(length=32),
        type_=sa.VARCHAR(length=30),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_batch_scan_lookup_result"), "batch_scan", f"result IN ({OLD_RESULTS})"
    )

    op.create_table(
        "credential_record",
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("review_note", sa.VARCHAR(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("agency_id", sa.UUID(), nullable=False),
        sa.Column("reference_number", sa.VARCHAR(), nullable=False),
        sa.Column("status", sa.VARCHAR(length=8), nullable=False),
        sa.Column("valid_from", sa.DATE(), nullable=True),
        sa.Column("valid_until", sa.DATE(), nullable=True),
        sa.Column("data_mode", sa.VARCHAR(length=4), nullable=False),
        sa.Column("provenance", sa.TEXT(), nullable=False),
        sa.Column("checked_on", sa.DATE(), nullable=False),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("review_status", sa.VARCHAR(length=14), nullable=False),
        sa.CheckConstraint("data_mode IN ('DEMO')", name=op.f("ck_credential_record_data_mode")),
        sa.CheckConstraint(
            "review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
            name=op.f("ck_credential_record_review_status"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name=op.f("ck_credential_record_credential_status")
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name=op.f("ck_credential_record_valid_until_after_from"),
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"],
            ["regulatory_agency.agency_id"],
            name=op.f("fk_credential_record_agency_id_regulatory_agency"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.product_id"],
            name=op.f("fk_credential_record_product_id_product"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["app_user.user_id"],
            name=op.f("fk_credential_record_reviewed_by_user_id_app_user"),
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["app_user.user_id"],
            name=op.f("fk_credential_record_submitted_by_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("credential_id", name=op.f("pk_credential_record")),
        sa.UniqueConstraint(
            "agency_id",
            "reference_number",
            name=op.f("uq_credential_record_agency_id_reference_number"),
        ),
    )
    op.create_index(
        op.f("ix_credential_record_product_id"), "credential_record", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_credential_record_agency_id"), "credential_record", ["agency_id"], unique=False
    )

    op.drop_constraint(op.f("ck_change_notice_change_type"), "change_notice", type_="check")
    op.alter_column(
        "change_notice",
        "change_type",
        existing_type=sa.String(length=16),
        type_=sa.VARCHAR(length=18),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_change_notice_change_type"),
        "change_notice",
        f"change_type IN ({OLD_CHANGE_TYPES})",
    )
    op.drop_constraint(op.f("ck_change_notice_exactly_one_target"), "change_notice", type_="check")
    op.add_column("change_notice", sa.Column("credential_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_change_notice_credential_id_credential_record"),
        "change_notice",
        "credential_record",
        ["credential_id"],
        ["credential_id"],
    )
    op.create_check_constraint(
        op.f("ck_change_notice_exactly_one_target"),
        "change_notice",
        "num_nonnulls(product_id, batch_id, credential_id, location_id) = 1",
    )

    op.drop_index(op.f("ix_product_registration_number"), table_name="product")
    op.drop_column("product", "registration_number")
    op.drop_index(op.f("ix_regulator_register_agency_id"), table_name="regulator_register")
    op.drop_table("regulator_register")
