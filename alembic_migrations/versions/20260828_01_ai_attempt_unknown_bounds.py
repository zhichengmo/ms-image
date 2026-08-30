"""Add durable bounds for unknown Provider Attempt reconciliation.

Revision ID: 20260828_01
Revises: 20260824_02
Create Date: 2026-08-28

The migration is additive and online-code compatible: old workers ignore the
new columns, while P1-B workers require them before deployment.  Historical
unknown rows intentionally keep ``first_unknown_at`` NULL because no existing
timestamp proves when the network result first became unknown.
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260828_01"
down_revision = "20260824_02"
branch_labels = None
depends_on = None


def _assert_no_p1b_facts_for_downgrade() -> None:
    if context.is_offline_mode():
        return
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM ai_call_attempt_record "
            "WHERE first_unknown_at IS NOT NULL OR reconcile_count <> 0 LIMIT 1"
        )
    ).first()
    if row is not None:
        raise RuntimeError("ai_attempt_unknown_bounds_downgrade_blocked_by_facts")


def upgrade() -> None:
    op.add_column(
        "ai_call_attempt_record",
        sa.Column(
            "first_unknown_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: Attempt 首次进入 unknown 的可信时间；历史未知可为 NULL",
        ),
    )
    op.add_column(
        "ai_call_attempt_record",
        sa.Column(
            "reconcile_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="INT: 已获持久 CAS 授权的 Provider 原请求 lookup 次数，从 0 开始",
        ),
    )


def downgrade() -> None:
    _assert_no_p1b_facts_for_downgrade()
    op.drop_column("ai_call_attempt_record", "reconcile_count")
    op.drop_column("ai_call_attempt_record", "first_unknown_at")
