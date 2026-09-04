"""Add the optional source diagnosis reference for display localization tasks.

Revision ID: 20260904_01
Revises: 20260901_01
Create Date: 2026-09-04

Existing Task rows are intentionally not backfilled. The reference remains an
opaque string without a database foreign key so deployment does not couple the
new display query path to historical data cleanup.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260904_01"
down_revision = "20260901_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_record",
        sa.Column(
            "source_task_id",
            sa.String(length=64),
            nullable=True,
            comment=(
                "VARCHAR(64)|NULL: 来源诊断 Task opaque ID，仅 anatomy_localization 使用"
            ),
        ),
    )
    op.create_index(
        "ix_task_record_source_type_created",
        "task_record",
        ["source_task_id", "task_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_record_source_type_created",
        table_name="task_record",
    )
    op.drop_column("task_record", "source_task_id")
