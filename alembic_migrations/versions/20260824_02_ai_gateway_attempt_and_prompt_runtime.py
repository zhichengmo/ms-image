"""Add Prompt Runtime, Gateway profile and Physical Attempt persistence.

Revision ID: 20260824_02
Revises: 20260824_01
Create Date: 2026-08-24

This migration extends the Phase A-C schema for the Prompt Runtime and AI
Gateway work: Prompt message contracts and source receipts, a frozen Gateway
profile on ai-config.v2 rows, frozen multi-message rendering and attempt
bookkeeping on the logical Call, and the independent Physical Attempt table.
No foreign key, database enum or tenant_id is introduced.
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "20260824_02"
down_revision = "20260824_01"
branch_labels = None
depends_on = None


UTC_NOW_6 = sa.text("CURRENT_TIMESTAMP(6)")
PREPARED = sa.text("'prepared'")
ZERO = sa.text("0")


def _assert_no_attempt_rows_for_downgrade() -> None:
    """Prevent a destructive downgrade once physical attempts exist."""
    if context.is_offline_mode():
        return
    row = op.get_bind().execute(
        sa.text("SELECT 1 FROM ai_call_attempt_record LIMIT 1")
    ).first()
    if row is not None:
        raise RuntimeError("ai_gateway_downgrade_blocked_by_attempt_rows")


def _assert_no_new_config_rows_for_downgrade() -> None:
    """Prevent a destructive downgrade once Prompt Runtime columns carry data."""
    if context.is_offline_mode():
        return
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM ai_config_record "
            "WHERE gateway_profile_json IS NOT NULL "
            "OR prompt_message_contract_json IS NOT NULL "
            "OR prompt_source_receipt_sha256 IS NOT NULL LIMIT 1"
        )
    ).first()
    if row is not None:
        raise RuntimeError("ai_gateway_downgrade_blocked_by_prompt_runtime_config_rows")


def upgrade() -> None:
    # Prompt source control plane gains the optional multi-message contract and
    # the external-source receipt.  Legacy single-body Prompts keep NULLs.
    op.add_column(
        "ai_prompt_template",
        sa.Column(
            "message_contract_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: prompt-message-contract.v1 多消息冻结合同，NULL 表示旧单正文兼容",
        ),
    )
    op.add_column(
        "ai_prompt_template",
        sa.Column(
            "source_receipt_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: prompt-source-receipt.v1 外部来源导入回执，不含凭证或正文副本",
        ),
    )
    op.add_column(
        "ai_prompt_template",
        sa.Column(
            "source_receipt_sha256",
            mysql.CHAR(length=64),
            nullable=True,
            comment="CHAR(64)|NULL: 外部 Prompt 来源回执规范化 SHA256",
        ),
    )

    # ai-config.v2 rows freeze the Prompt Runtime contract and Gateway profile.
    op.add_column(
        "ai_config_record",
        sa.Column(
            "prompt_message_contract_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: 冻结 prompt-message-contract.v1，NULL 表示旧单正文兼容",
        ),
    )
    op.add_column(
        "ai_config_record",
        sa.Column(
            "prompt_source_receipt_sha256",
            mysql.CHAR(length=64),
            nullable=True,
            comment="CHAR(64)|NULL: 冻结 Prompt 外部来源回执 SHA256",
        ),
    )
    op.add_column(
        "ai_config_record",
        sa.Column(
            "gateway_profile_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: ai-gateway-profile.v1 冻结 Gateway 资格和 SSE 传输合同",
        ),
    )

    # Logical Call gains frozen multi-message content and Physical Attempt
    # bookkeeping; the attempt table itself is created below.
    op.add_column(
        "ai_call_record",
        sa.Column(
            "rendered_messages_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: 冻结多消息 Prompt 内容，不含短期签名 URL",
        ),
    )
    op.add_column(
        "ai_call_record",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=ZERO,
            comment="INT: 已创建 Physical Attempt 数量，single-lane 首期最多按冻结预算递增",
        ),
    )
    op.add_column(
        "ai_call_record",
        sa.Column(
            "winner_attempt_id",
            sa.String(length=64),
            nullable=True,
            comment="VARCHAR(64)|NULL: 通过 Schema 校验并 CAS 接受的 Physical Attempt ID",
        ),
    )

    op.create_table(
        "ai_call_attempt_record",
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): Physical Attempt opaque ID，单列主键",
        ),
        sa.Column(
            "ai_call_id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 所属 Logical Call ID，不设外键",
        ),
        sa.Column(
            "attempt_no",
            sa.Integer(),
            nullable=False,
            comment="INT: 同一 Logical Call 内 Physical Attempt 序号，从 1 开始",
        ),
        sa.Column(
            "physical_attempt_key",
            mysql.CHAR(length=64),
            nullable=False,
            comment="CHAR(64): 冻结物理发送事实的全局唯一摘要键",
        ),
        sa.Column(
            "provider_idempotency_key",
            sa.String(length=160),
            nullable=False,
            comment="VARCHAR(160): 同一 Physical Attempt 网络重放固定复用的 Provider 幂等键",
        ),
        sa.Column(
            "trace_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 端到端追踪 ID",
        ),
        sa.Column(
            "request_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 业务请求 ID",
        ),
        sa.Column(
            "connection_id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 冻结 Connection ID，不设外键",
        ),
        sa.Column(
            "connection_sha256",
            mysql.CHAR(length=64),
            nullable=False,
            comment="CHAR(64): 冻结 Connection 元数据 SHA256",
        ),
        sa.Column(
            "provider_type",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): Provider adapter 类型",
        ),
        sa.Column(
            "api_format",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): Gateway API 格式，候选 chat-completions/responses",
        ),
        sa.Column(
            "requested_model",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 冻结请求模型",
        ),
        sa.Column(
            "actual_model",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: Provider 确认的实际模型",
        ),
        sa.Column(
            "request_sha256",
            mysql.CHAR(length=64),
            nullable=False,
            comment="CHAR(64): 不含 Secret/签名 URL 的冻结 Gateway 请求 SHA256",
        ),
        sa.Column(
            "sent_image_manifest_sha256",
            mysql.CHAR(length=64),
            nullable=True,
            comment="CHAR(64)|NULL: 本 Attempt 实际发送影像清单 SHA256",
        ),
        sa.Column(
            "image_count_sent",
            sa.Integer(),
            nullable=False,
            server_default=ZERO,
            comment="INT: 本 Attempt 实际发送影像张数",
        ),
        sa.Column(
            "image_receipt_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: ai-image-receipt.v1 脱敏影像发送回执，不含签名 URL",
        ),
        sa.Column(
            "provider_request_id",
            sa.String(length=160),
            nullable=True,
            comment="VARCHAR(160)|NULL: Gateway/Provider 请求 ID",
        ),
        sa.Column(
            "usage_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: Provider usage 计量回执",
        ),
        sa.Column(
            "response_object_ref_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: encrypted-object-ref.v1 原始响应加密对象引用",
        ),
        sa.Column(
            "response_sha256",
            mysql.CHAR(length=64),
            nullable=True,
            comment="CHAR(64)|NULL: 原始 Provider 响应字节 SHA256",
        ),
        sa.Column(
            "parsed_result_json",
            mysql.JSON(),
            nullable=True,
            comment="JSON|NULL: 严格 Schema 验证后的结构化结果",
        ),
        sa.Column(
            "error_code",
            sa.String(length=80),
            nullable=True,
            comment="VARCHAR(80)|NULL: 稳定错误码",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=PREPARED,
            comment="VARCHAR(32): Physical Attempt 状态，候选 prepared/sending/succeeded/failed/unknown/cancelled",
        ),
        sa.Column(
            "state_version",
            sa.BigInteger(),
            nullable=False,
            server_default=ZERO,
            comment="BIGINT: Physical Attempt CAS 版本",
        ),
        sa.Column(
            "prepared_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            comment="DATETIME(6): prepared 已持久化时间",
        ),
        sa.Column(
            "sent_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: 开始发送网络时间",
        ),
        sa.Column(
            "finished_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: Attempt 终态/已收敛时间",
        ),
        sa.Column(
            "next_reconcile_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: unknown Attempt 下次对账时间",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录创建时间，UTC",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录最后更新时间，UTC",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ai_call_id",
            "attempt_no",
            name="uq_ai_call_attempt_record_call_no",
        ),
        sa.UniqueConstraint(
            "physical_attempt_key",
            name="uq_ai_call_attempt_record_physical_key",
        ),
        sa.UniqueConstraint(
            "provider_idempotency_key",
            name="uq_ai_call_attempt_record_provider_idempotency",
        ),
    )
    op.create_index(
        "ix_ai_call_attempt_record_call_status",
        "ai_call_attempt_record",
        ["ai_call_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_ai_call_attempt_record_reconcile",
        "ai_call_attempt_record",
        ["status", "next_reconcile_at"],
        unique=False,
    )


def downgrade() -> None:
    _assert_no_attempt_rows_for_downgrade()
    _assert_no_new_config_rows_for_downgrade()

    op.drop_index(
        "ix_ai_call_attempt_record_reconcile",
        table_name="ai_call_attempt_record",
    )
    op.drop_index(
        "ix_ai_call_attempt_record_call_status",
        table_name="ai_call_attempt_record",
    )
    op.drop_table("ai_call_attempt_record")

    op.drop_column("ai_call_record", "winner_attempt_id")
    op.drop_column("ai_call_record", "attempt_count")
    op.drop_column("ai_call_record", "rendered_messages_json")

    op.drop_column("ai_config_record", "gateway_profile_json")
    op.drop_column("ai_config_record", "prompt_source_receipt_sha256")
    op.drop_column("ai_config_record", "prompt_message_contract_json")

    op.drop_column("ai_prompt_template", "source_receipt_sha256")
    op.drop_column("ai_prompt_template", "source_receipt_json")
    op.drop_column("ai_prompt_template", "message_contract_json")
