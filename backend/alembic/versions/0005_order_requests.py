"""order requests: REQUESTED status, allocations without quantities

Revision ID: 0005_order_requests
Revises: 0004_regulator_register
Create Date: 2026-10-12

- order_status SUBMITTED becomes REQUESTED (D96); existing rows are renamed.
- order_batch_allocation.allocated_quantity is dropped (no stock kept, D99) and a line can link a
  batch only once.

Hand-edited: Alembic does not compare CHECK constraints, so the status check is replaced here.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_order_requests"
down_revision: str | Sequence[str] | None = "0004_regulator_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_STATUSES = "'REQUESTED', 'ACCEPTED', 'DECLINED', 'FULFILLED', 'CANCELLED'"
OLD_STATUSES = "'SUBMITTED', 'ACCEPTED', 'DECLINED', 'FULFILLED', 'CANCELLED'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_wholesale_order_order_status"), "wholesale_order", type_="check")
    op.execute("UPDATE wholesale_order SET status = 'REQUESTED' WHERE status = 'SUBMITTED'")
    op.create_check_constraint(
        op.f("ck_wholesale_order_order_status"), "wholesale_order", f"status IN ({NEW_STATUSES})"
    )

    op.drop_constraint(
        op.f("ck_order_batch_allocation_allocated_quantity_positive"),
        "order_batch_allocation",
        type_="check",
    )
    op.drop_column("order_batch_allocation", "allocated_quantity")
    op.create_unique_constraint(
        op.f("uq_order_batch_allocation_line_id_batch_id"),
        "order_batch_allocation",
        ["line_id", "batch_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_order_batch_allocation_line_id_batch_id"), "order_batch_allocation", type_="unique"
    )
    # Old rows had a quantity; restore with 1 so the NOT NULL / > 0 rules hold.
    op.add_column(
        "order_batch_allocation",
        sa.Column(
            "allocated_quantity",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column("order_batch_allocation", "allocated_quantity", server_default=None)
    op.create_check_constraint(
        op.f("ck_order_batch_allocation_allocated_quantity_positive"),
        "order_batch_allocation",
        "allocated_quantity > 0",
    )

    op.drop_constraint(op.f("ck_wholesale_order_order_status"), "wholesale_order", type_="check")
    op.execute("UPDATE wholesale_order SET status = 'SUBMITTED' WHERE status = 'REQUESTED'")
    op.create_check_constraint(
        op.f("ck_wholesale_order_order_status"), "wholesale_order", f"status IN ({OLD_STATUSES})"
    )
