"""initial schema: poems, images, audios, jobs

Revision ID: 0001
Revises:
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character", sa.String(length=32), nullable=False),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("lang", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("poem_en", sa.Text(), nullable=False),
        sa.Column("poem_ja", sa.Text(), nullable=False),
        sa.Column("mood", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_poems_character", "poems", ["character"])

    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poem_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative", sa.Text(), nullable=False, server_default=""),
        sa.Column("checkpoint", sa.String(length=128), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["poem_id"], ["poems.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_images_poem_id", "images", ["poem_id"])

    op.create_table(
        "audios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poem_id", sa.Integer(), nullable=False),
        sa.Column("backend", sa.String(length=16), nullable=False, server_default="piper"),
        sa.Column("voice", sa.String(length=64), nullable=True),
        sa.Column("lang", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["poem_id"], ["poems.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audios_poem_id", "audios", ["poem_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
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
    )
    op.create_index("ix_jobs_type", "jobs", ["type"])
    op.create_index("ix_jobs_ref_id", "jobs", ["ref_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("audios")
    op.drop_table("images")
    op.drop_table("poems")
