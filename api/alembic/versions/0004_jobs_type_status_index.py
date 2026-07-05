"""add composite (type, status) index on jobs (#124)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05

The workers' reconcile/queue-scan queries filter jobs on both ``type`` and
``status`` (e.g. WHERE type = 'image' AND status IN ('queued','running')); the
single-column indexes only cover one predicate. This composite index backs both.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_jobs_type_status", "jobs", ["type", "status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_type_status", table_name="jobs")
