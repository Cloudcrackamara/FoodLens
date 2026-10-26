"""log recognised carton scans as CARTON_CODE

Revision ID: 0008_carton_code_result
Revises: 0007_drop_register
Create Date: 2026-10-26

- scan_event.result allows CARTON_CODE, so carton scans never count as pack checks in stats or
  risk rules (D148).
- A CARTON_CODE scan names a carton and no unit (CHECK).

Hand-written: autogenerate does not compare CHECK constraints. Downgrade deletes CARTON_CODE
scans (scan_event refuses UPDATE, so they cannot be mapped to another result).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_carton_code_result"
down_revision: str | Sequence[str] | None = "0007_drop_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_RESULTS = (
    "'INVALID_IDENTITY', 'SUSPICIOUS_ACTIVITY', 'BATCH_OR_PRODUCT_WARNING', "
    "'RECOGNISED_JUST_SOLD', 'RECOGNISED_PREVIOUSLY_SOLD', 'RECOGNISED_NOT_SOLD'"
)
NEW_RESULTS = f"{OLD_RESULTS}, 'CARTON_CODE'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_scan_event_check_result"), "scan_event", type_="check")
    op.create_check_constraint(
        op.f("ck_scan_event_check_result"), "scan_event", f"result IN ({NEW_RESULTS})"
    )
    op.create_check_constraint(
        op.f("ck_scan_event_carton_code_has_carton"),
        "scan_event",
        "result <> 'CARTON_CODE' OR (carton_id IS NOT NULL AND unit_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_scan_event_carton_code_has_carton"), "scan_event", type_="check")
    op.execute("DELETE FROM scan_event WHERE result = 'CARTON_CODE'")
    op.drop_constraint(op.f("ck_scan_event_check_result"), "scan_event", type_="check")
    op.create_check_constraint(
        op.f("ck_scan_event_check_result"), "scan_event", f"result IN ({OLD_RESULTS})"
    )
