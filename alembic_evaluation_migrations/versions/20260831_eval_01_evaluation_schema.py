"""Create or adopt the isolated Evaluation schema.

Revision ID: 20260831_eval_01
Revises:
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

from alembic_evaluation_migrations.schema_contract import (
    EVALUATION_TABLE_NAMES,
    create_evaluation_tables,
    drop_evaluation_tables,
    validate_evaluation_schema,
)


revision = "20260831_eval_01"
down_revision = None
branch_labels = None
depends_on = None


def _existing_evaluation_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names()) & EVALUATION_TABLE_NAMES


def upgrade() -> None:
    if context.is_offline_mode():
        create_evaluation_tables(op)
        return

    existing = _existing_evaluation_tables()
    if existing and existing != EVALUATION_TABLE_NAMES:
        raise RuntimeError("evaluation_schema_adoption_invalid")
    if not existing:
        create_evaluation_tables(op)
    validate_evaluation_schema(op.get_bind())


def downgrade() -> None:
    if not context.is_offline_mode():
        existing = _existing_evaluation_tables()
        if existing != EVALUATION_TABLE_NAMES:
            raise RuntimeError("evaluation_schema_adoption_invalid")
        for table_name in sorted(EVALUATION_TABLE_NAMES):
            row = op.get_bind().execute(
                sa.text(f"SELECT 1 FROM `{table_name}` LIMIT 1")
            ).first()
            if row is not None:
                raise RuntimeError("evaluation_schema_downgrade_blocked_by_rows")
    drop_evaluation_tables(op)
