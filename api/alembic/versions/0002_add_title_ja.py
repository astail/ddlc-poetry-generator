"""add poems.title_ja (Japanese title)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: existing poems have no Japanese title, so the frontend falls back
    # to the English title for them.
    op.add_column("poems", sa.Column("title_ja", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("poems", "title_ja")
