"""add CHECK constraints for status / type / lang / character / backend (#123)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

Enforces the allowed enum values at the database level (previously only the
application StrEnums constrained them, so a bad worker write or manual SQL could
store an invalid value). Values mirror app.models' StrEnums / Character / LANGS;
kept literal here so the migration stays self-contained. Targets PostgreSQL (the
production DB, like 0001).
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# (table, constraint name, condition)
_CONSTRAINTS = [
    ("poems", "ck_poems_character", "character IN ('sayori', 'natsuki', 'yuri', 'monika')"),
    ("poems", "ck_poems_lang", "lang IN ('en', 'ja')"),
    ("images", "ck_images_status", "status IN ('pending', 'running', 'done', 'failed')"),
    ("audios", "ck_audios_backend", "backend IN ('piper', 'xtts', 'voicevox')"),
    ("audios", "ck_audios_lang", "lang IN ('en', 'ja')"),
    ("audios", "ck_audios_status", "status IN ('pending', 'running', 'done', 'failed')"),
    ("jobs", "ck_jobs_type", "type IN ('image', 'audio')"),
    ("jobs", "ck_jobs_status", "status IN ('queued', 'running', 'done', 'failed')"),
]


def upgrade() -> None:
    for table, name, condition in _CONSTRAINTS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for table, name, _ in reversed(_CONSTRAINTS):
        op.drop_constraint(name, table, type_="check")
