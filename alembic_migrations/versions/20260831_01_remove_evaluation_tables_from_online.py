"""Remove legacy empty Evaluation tables from the online database.

Revision ID: 20260831_01
Revises: 20260828_01
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

from alembic_evaluation_migrations.schema_contract import (
    EVALUATION_TABLE_NAMES,
    create_evaluation_tables,
)


revision = "20260831_01"
down_revision = "20260828_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        for table_name in sorted(EVALUATION_TABLE_NAMES):
            op.execute(sa.text(f"DROP TABLE IF EXISTS `{table_name}`"))
        return

    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names()) & EVALUATION_TABLE_NAMES
    for table_name in sorted(existing):
        if bind.execute(sa.text(f"SELECT 1 FROM `{table_name}` LIMIT 1")).first():
            raise RuntimeError("online_evaluation_table_cleanup_blocked_by_rows")
    for table_name in (
        "evaluation_artifact_record",
        "evaluation_run_record",
        "evaluation_outbox_record",
        "evaluation_job_record",
    ):
        if table_name in existing:
            op.drop_table(table_name)


def downgrade() -> None:
    if not context.is_offline_mode():
        existing = set(sa.inspect(op.get_bind()).get_table_names())
        if existing & EVALUATION_TABLE_NAMES:
            raise RuntimeError("online_evaluation_table_restore_conflict")
    create_evaluation_tables(op)
