"""Baseline: empty schema (Phase 0)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-07

"""

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No tables yet. Business models start in Phase 1."""


def downgrade() -> None:
    pass
