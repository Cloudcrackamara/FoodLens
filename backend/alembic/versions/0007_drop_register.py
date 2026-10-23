"""drop the simulated regulator register, the lookup log and batch QR tokens

Revision ID: 0007_drop_register
Revises: 0006_unit_identity
Create Date: 2026-10-22

- Drops regulator_register, regulatory_agency and batch_scan (D104). Their data is not migrated:
  the registration lookup is gone, and product.registration_number stays as information only.
- Drops product_batch.qr_token: identities now live on units and cartons (D138).
- Adds product_batch.released_at, set when every unit of the batch is released.

Downgrade recreates the dropped tables and column empty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_drop_register"
down_revision: str | Sequence[str] | None = "0006_unit_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOOKUP_RESULTS = (
    "'INSUFFICIENT_OR_AMBIGUOUS', 'REGISTRATION_NOT_FOUND', "
    "'REGISTRATION_EXPIRED_OR_INACTIVE', 'REGISTRATION_MISMATCH', 'REGISTERED_ACTIVE'"
)


def upgrade() -> None:
    op.drop_index(op.f("ix_regulator_register_agency_id"), table_name="regulator_register")
    op.drop_table("regulator_register")
    op.drop_table("regulatory_agency")
    op.drop_index(op.f("ix_batch_scan_matched_batch_id"), table_name="batch_scan")
    op.drop_table("batch_scan")

    op.drop_constraint(op.f("uq_product_batch_qr_token"), "product_batch", type_="unique")
    op.drop_column("product_batch", "qr_token")
    op.add_column(
        "product_batch", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("product_batch", "released_at")
    op.add_column("product_batch", sa.Column("qr_token", sa.VARCHAR(), nullable=True))
    op.create_unique_constraint(op.f("uq_product_batch_qr_token"), "product_batch", ["qr_token"])

    op.create_table(
        "batch_scan",
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("scan_id", sa.UUID(), nullable=False),
        sa.Column("input_registration_number", sa.VARCHAR(), nullable=True),
        sa.Column("input_batch_number", sa.VARCHAR(), nullable=True),
        sa.Column("matched_batch_id", sa.UUID(), nullable=True),
        sa.Column("result", sa.VARCHAR(length=32), nullable=False),
        sa.CheckConstraint(
            f"result IN ({LOOKUP_RESULTS})", name=op.f("ck_batch_scan_lookup_result")
        ),
        sa.ForeignKeyConstraint(
            ["matched_batch_id"],
            ["product_batch.batch_id"],
            name=op.f("fk_batch_scan_matched_batch_id_product_batch"),
        ),
        sa.PrimaryKeyConstraint("scan_id", name=op.f("pk_batch_scan")),
    )
    op.create_index(
        op.f("ix_batch_scan_matched_batch_id"), "batch_scan", ["matched_batch_id"], unique=False
    )

    op.create_table(
        "regulatory_agency",
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
        sa.Column("agency_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("scheme", sa.VARCHAR(), nullable=False),
        sa.Column("data_mode", sa.VARCHAR(length=4), nullable=False),
        sa.CheckConstraint("data_mode IN ('DEMO')", name=op.f("ck_regulatory_agency_data_mode")),
        sa.PrimaryKeyConstraint("agency_id", name=op.f("pk_regulatory_agency")),
        sa.UniqueConstraint("name", "scheme", name=op.f("uq_regulatory_agency_name_scheme")),
    )
    op.create_table(
        "regulator_register",
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
        sa.Column("register_id", sa.UUID(), nullable=False),
        sa.Column("agency_id", sa.UUID(), nullable=False),
        sa.Column("registration_number", sa.VARCHAR(), nullable=False),
        sa.Column("registered_product_name", sa.VARCHAR(), nullable=False),
        sa.Column("registered_company_name", sa.VARCHAR(), nullable=False),
        sa.Column("status", sa.VARCHAR(length=8), nullable=False),
        sa.Column("expires_on", sa.DATE(), nullable=True),
        sa.Column("data_mode", sa.VARCHAR(length=4), nullable=False),
        sa.Column("provenance", sa.TEXT(), nullable=False),
        sa.Column("last_checked_on", sa.DATE(), nullable=False),
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
        op.f("ix_regulator_register_agency_id"),
        "regulator_register",
        ["agency_id"],
        unique=False,
    )
