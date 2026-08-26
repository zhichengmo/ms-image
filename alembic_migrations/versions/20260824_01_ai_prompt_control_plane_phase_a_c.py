"""Add the provider-disabled AI Prompt control plane and Config v2 snapshots.

Revision ID: 20260824_01
Revises:
Create Date: 2026-08-24

This migration is intentionally an upgrade from the repository's pre-Alembic
runtime schema.  It creates the four new control-plane tables and extends the
existing Config and logical Call tables without removing any v1 Bundle fields.
It must be applied only after the existing application schema has been stamped
as this repository's Alembic baseline.
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "20260824_01"
down_revision = None
branch_labels = None
depends_on = None


UTC_NOW_6 = sa.text("CURRENT_TIMESTAMP(6)")
DRAFT = sa.text("'draft'")
ZERO = sa.text("0")
PREPARED = sa.text("'prepared'")
PENDING = sa.text("'pending'")


V1_BUNDLE_COMMENTS = {
    "prompt_bundle_json": (
        "JSON: 冻结 zh-CN Prompt Bundle、资产内容、选择策略和 SHA",
        "JSON|NULL: v1 冻结 Prompt Bundle 兼容读取字段",
    ),
    "schema_bundle_json": (
        "JSON: 冻结 CompleteMedicalResult Schema Bundle 和 SHA",
        "JSON|NULL: v1 冻结 Schema Bundle 兼容读取字段",
    ),
    "model_policy_json": (
        "JSON: requested model、Prompt/token/image budget 和 actual-model 要求",
        "JSON|NULL: v1 模型策略兼容读取字段",
    ),
    "provider_plan_json": (
        "JSON: Secret reference/disabled Provider 计划",
        "JSON|NULL: v1 Provider 计划兼容读取字段",
    ),
}
CONFIG_SHA_COMMENTS = {
    "compiled_pipeline_sha256": (
        "CHAR(64): compiled pipeline SHA256",
        "CHAR(64): 编译后 Pipeline SHA256",
    ),
    "config_sha256": (
        "CHAR(64): 规范化 Config 正文摘要",
        "CHAR(64): 规范化 AI Config 冻结正文 SHA256",
    ),
    "release_fingerprint": (
        "CHAR(64): Config、Prompt、Schema、模型、Provider 和代码合同联合摘要",
        "CHAR(64): 行为相关 Prompt/模型/Schema/Pipeline 联合指纹",
    ),
}
CALL_SHA_COMMENTS = {
    "config_sha256": "CHAR(64): Config 摘要",
    "request_sha256": "CHAR(64): Provider 请求摘要",
    "rendered_prompt_sha256": "CHAR(64): 渲染 Prompt 摘要",
    "schema_sha256": "CHAR(64): 输出 Schema 摘要",
    "requested_image_manifest_sha256": "CHAR(64): 请求影像清单摘要",
    "sent_image_manifest_sha256": "CHAR(64)|NULL: 实际发送影像清单摘要",
}


def _assert_no_v2_config_rows_for_downgrade() -> None:
    """Prevent a destructive downgrade once v2-only rows have been written."""
    if context.is_offline_mode():
        return
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM ai_config_record "
            "WHERE config_contract_version = 'ai-config.v2' LIMIT 1"
        )
    ).first()
    if row is not None:
        raise RuntimeError(
            "ai_prompt_control_plane_downgrade_blocked_by_v2_config_rows"
        )


def _assert_release_fingerprint_unique_for_downgrade() -> None:
    """The pre-v2 schema made release_fingerprint globally unique."""
    if context.is_offline_mode():
        return
    row = op.get_bind().execute(
        sa.text(
            "SELECT release_fingerprint FROM ai_config_record "
            "GROUP BY release_fingerprint HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if row is not None:
        raise RuntimeError(
            "ai_prompt_control_plane_downgrade_blocked_by_release_fingerprint_duplicates"
        )


def upgrade() -> None:
    # Phase A source control plane.  IDs have no server default because the
    # application assigns opaque IDs before each durable write.
    op.create_table(
        "ai_prompt_template",
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
        ),
        sa.Column(
            "prompt_key",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 稳定 Prompt 业务键",
        ),
        sa.Column(
            "version",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): Prompt 不可变版本",
        ),
        sa.Column(
            "name",
            sa.String(length=160),
            nullable=False,
            comment="VARCHAR(160): Prompt 中文显示名称",
        ),
        sa.Column(
            "description",
            sa.String(length=500),
            nullable=True,
            comment="VARCHAR(500)|NULL: Prompt 用途说明",
        ),
        sa.Column(
            "language",
            sa.String(length=16),
            nullable=False,
            comment="VARCHAR(16): Prompt 语言，首期候选 zh-CN",
        ),
        sa.Column(
            "content",
            mysql.MEDIUMTEXT(),
            nullable=False,
            comment="MEDIUMTEXT: 完整 Prompt 正文，唯一正文事实",
        ),
        sa.Column(
            "variables_json",
            mysql.JSON(),
            nullable=False,
            comment="JSON: prompt-variables.v1 允许变量合同",
        ),
        sa.Column(
            "content_sha256",
            mysql.CHAR(length=64),
            nullable=False,
            comment="CHAR(64): 规范化 Prompt 正文 SHA256",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=DRAFT,
            comment="VARCHAR(32): Prompt 状态，候选 draft/validated/retired",
        ),
        sa.Column(
            "state_version",
            sa.BigInteger(),
            nullable=False,
            server_default=ZERO,
            comment="BIGINT: Prompt 状态与草稿更新 CAS 版本",
        ),
        sa.Column(
            "validated_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: Prompt 验证通过时间",
        ),
        sa.Column(
            "retired_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: Prompt 退役时间",
        ),
        sa.Column(
            "created_by_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 创建者可信身份 ID",
        ),
        sa.Column(
            "updated_by_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 最近操作者可信身份 ID",
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
        sa.UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_template_key_version"),
    )
    op.create_index(
        "ix_ai_prompt_template_key_status_created",
        "ai_prompt_template",
        ["prompt_key", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_prompt_template_content_sha256",
        "ai_prompt_template",
        ["content_sha256"],
        unique=False,
    )

    op.create_table(
        "ai_api_connection",
        sa.Column("id", sa.String(length=64), nullable=False, comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键"),
        sa.Column("connection_key", sa.String(length=128), nullable=False, comment="VARCHAR(128): 稳定连接业务键"),
        sa.Column("version", sa.String(length=64), nullable=False, comment="VARCHAR(64): 连接不可变版本"),
        sa.Column("name", sa.String(length=160), nullable=False, comment="VARCHAR(160): 连接中文显示名称"),
        sa.Column("provider_type", sa.String(length=64), nullable=False, comment="VARCHAR(64): Provider adapter 类型"),
        sa.Column("api_format", sa.String(length=64), nullable=False, comment="VARCHAR(64): 请求协议格式"),
        sa.Column("base_url", sa.String(length=500), nullable=False, comment="VARCHAR(500): Provider 基础地址，不含 Secret"),
        sa.Column("secret_ref", sa.String(length=500), nullable=False, comment="VARCHAR(500): 外部 Secret Manager 引用，不是 Secret 值"),
        sa.Column("region", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: Provider 区域标识"),
        sa.Column("capability_json", mysql.JSON(), nullable=False, comment="JSON: connection-capability.v1 非敏感能力声明"),
        sa.Column("connection_sha256", mysql.CHAR(length=64), nullable=False, comment="CHAR(64): 规范化连接元数据 SHA256，不对 Secret 值计算"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=DRAFT, comment="VARCHAR(32): 连接状态，候选 draft/validated/retired"),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=ZERO, comment="BIGINT: Connection CAS 版本"),
        sa.Column("validated_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 结构验证通过时间"),
        sa.Column("retired_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 连接退役时间"),
        sa.Column("created_by_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 创建者可信身份 ID"),
        sa.Column("updated_by_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 最近操作者可信身份 ID"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=UTC_NOW_6, comment="DATETIME(6): 记录创建时间，UTC"),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=UTC_NOW_6, comment="DATETIME(6): 记录最后更新时间，UTC"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_key", "version", name="uq_ai_api_connection_key_version"),
    )
    op.create_index("ix_ai_api_connection_provider_status", "ai_api_connection", ["provider_type", "status"], unique=False)
    op.create_index("ix_ai_api_connection_sha256", "ai_api_connection", ["connection_sha256"], unique=False)

    op.create_table(
        "ai_model_pool",
        sa.Column("id", sa.String(length=64), nullable=False, comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键"),
        sa.Column("pool_key", sa.String(length=128), nullable=False, comment="VARCHAR(128): 稳定模型池业务键"),
        sa.Column("version", sa.String(length=64), nullable=False, comment="VARCHAR(64): 模型池不可变版本"),
        sa.Column("name", sa.String(length=160), nullable=False, comment="VARCHAR(160): 模型池中文显示名称"),
        sa.Column("description", sa.String(length=500), nullable=True, comment="VARCHAR(500)|NULL: 模型池用途说明"),
        sa.Column("execution_mode", sa.String(length=32), nullable=False, comment="VARCHAR(32): 模型池执行模式，候选 single/race"),
        sa.Column("winner_policy", sa.String(length=64), nullable=False, comment="VARCHAR(64): 模型池胜出策略，候选 single/first_technically_valid"),
        sa.Column("lane_count", sa.SmallInteger(), nullable=False, comment="SMALLINT: 冻结 lane 数量，Phase A-C 固定 1"),
        sa.Column("lane_plan_json", mysql.JSON(), nullable=False, comment="JSON: ai-model-pool-lanes.v1 有序 lane 计划"),
        sa.Column("pool_sha256", mysql.CHAR(length=64), nullable=False, comment="CHAR(64): 规范化模型池内容 SHA256"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=DRAFT, comment="VARCHAR(32): 模型池状态，候选 draft/validated/retired"),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=ZERO, comment="BIGINT: Model Pool CAS 版本"),
        sa.Column("validated_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 模型池验证通过时间"),
        sa.Column("retired_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 模型池退役时间"),
        sa.Column("created_by_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 创建者可信身份 ID"),
        sa.Column("updated_by_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 最近操作者可信身份 ID"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=UTC_NOW_6, comment="DATETIME(6): 记录创建时间，UTC"),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=UTC_NOW_6, comment="DATETIME(6): 记录最后更新时间，UTC"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pool_key", "version", name="uq_ai_model_pool_key_version"),
    )
    op.create_index("ix_ai_model_pool_execution_status", "ai_model_pool", ["execution_mode", "status"], unique=False)
    op.create_index("ix_ai_model_pool_sha256", "ai_model_pool", ["pool_sha256"], unique=False)

    op.create_table(
        "ai_control_audit_record",
        sa.Column("id", sa.String(length=64), nullable=False, comment="VARCHAR(64): 控制面审计事件 opaque ID，单列主键"),
        sa.Column("resource_type", sa.String(length=64), nullable=False, comment="VARCHAR(64): 控制面资源类型，候选 prompt/connection/model_pool/ai_config"),
        sa.Column("resource_id", sa.String(length=64), nullable=False, comment="VARCHAR(64): 被操作资源 opaque ID"),
        sa.Column("resource_key", sa.String(length=128), nullable=False, comment="VARCHAR(128): 被操作资源稳定业务键"),
        sa.Column("action_type", sa.String(length=64), nullable=False, comment="VARCHAR(64): 控制面动作类型，候选 create/update/validate/activate/retire/rollback"),
        sa.Column("before_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 操作前资源摘要"),
        sa.Column("after_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 操作后资源摘要"),
        sa.Column("changed_fields_json", mysql.JSON(), nullable=False, comment="JSON: ai-control-change-set.v1 变更字段与脱敏摘要"),
        sa.Column("reason", sa.String(length=500), nullable=True, comment="VARCHAR(500)|NULL: 操作原因或回滚原因"),
        sa.Column("request_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 控制面命令幂等与追踪 ID"),
        sa.Column("actor_type", sa.String(length=32), nullable=False, comment="VARCHAR(32): 操作者类型，候选 user/service"),
        sa.Column("actor_id", sa.String(length=128), nullable=False, comment="VARCHAR(128): 可信操作者身份 ID"),
        sa.Column("result_type", sa.String(length=32), nullable=False, comment="VARCHAR(32): 审计结果类型，候选 succeeded/rejected/failed"),
        sa.Column("error_code", sa.String(length=80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=UTC_NOW_6, comment="DATETIME(6): 审计事件创建时间，UTC"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "resource_type", "action_type", name="uq_ai_control_audit_request_resource_action"),
    )
    op.create_index("ix_ai_control_audit_resource_created", "ai_control_audit_record", ["resource_type", "resource_id", "created_at"], unique=False)
    op.create_index("ix_ai_control_audit_key_created", "ai_control_audit_record", ["resource_key", "created_at"], unique=False)
    op.create_index("ix_ai_control_audit_actor_created", "ai_control_audit_record", ["actor_id", "created_at"], unique=False)

    # Phase B: preserve v1 Bundle facts but make them nullable so a v2 Config
    # can carry the new frozen single-Prompt snapshot instead.
    op.drop_constraint("uq_ai_config_record_release_fingerprint", "ai_config_record", type_="unique")
    for column_name, (existing_comment, target_comment) in V1_BUNDLE_COMMENTS.items():
        op.alter_column(
            "ai_config_record",
            column_name,
            existing_type=mysql.JSON(),
            existing_nullable=False,
            nullable=True,
            existing_comment=existing_comment,
            comment=target_comment,
        )

    op.add_column("ai_config_record", sa.Column("name", sa.String(length=160), nullable=True, comment="VARCHAR(160)|NULL: AI Config 中文显示名称，v2 必填"))
    op.add_column("ai_config_record", sa.Column("config_contract_version", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: AI Config 数据合同版本，v2 为 ai-config.v2"))
    op.add_column("ai_config_record", sa.Column("profile_key", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: 固定 Pipeline Profile 键，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_template_id", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: 来源 Prompt 模板版本 ID，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_key", sa.String(length=128), nullable=True, comment="VARCHAR(128)|NULL: 冻结 Prompt 业务键，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_version", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: 冻结 Prompt 版本，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_content", mysql.MEDIUMTEXT(), nullable=True, comment="MEDIUMTEXT|NULL: 冻结完整 Prompt 正文，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_variables_json", mysql.JSON(), nullable=True, comment="JSON|NULL: 冻结 prompt-variables.v1 合同，v2 必填"))
    op.add_column("ai_config_record", sa.Column("prompt_content_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 冻结 Prompt 正文 SHA256，v2 必填"))
    op.add_column("ai_config_record", sa.Column("model_pool_id", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: 来源 Model Pool 版本 ID，v2 必填"))
    op.add_column("ai_config_record", sa.Column("model_pool_key", sa.String(length=128), nullable=True, comment="VARCHAR(128)|NULL: 冻结 Model Pool 业务键，v2 必填"))
    op.add_column("ai_config_record", sa.Column("model_pool_version", sa.String(length=64), nullable=True, comment="VARCHAR(64)|NULL: 冻结 Model Pool 版本，v2 必填"))
    op.add_column("ai_config_record", sa.Column("model_snapshot_json", mysql.JSON(), nullable=True, comment="JSON|NULL: ai-model-snapshot.v1 展开模型与连接快照，v2 必填"))
    op.add_column("ai_config_record", sa.Column("model_snapshot_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 模型与连接快照 SHA256，v2 必填"))
    op.add_column("ai_config_record", sa.Column("output_schema_json", mysql.JSON(), nullable=True, comment="JSON|NULL: 冻结输出 JSON Schema，v2 必填"))
    op.add_column("ai_config_record", sa.Column("output_schema_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 冻结输出 Schema SHA256，v2 必填"))
    op.add_column("ai_config_record", sa.Column("validated_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 验证通过时间"))
    op.add_column("ai_config_record", sa.Column("activated_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 最近激活时间"))
    op.add_column("ai_config_record", sa.Column("retired_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 最近退役时间"))
    op.add_column("ai_config_record", sa.Column("created_by_id", sa.String(length=128), nullable=True, comment="VARCHAR(128)|NULL: 创建者可信身份 ID，v2 必填"))
    op.add_column("ai_config_record", sa.Column("updated_by_id", sa.String(length=128), nullable=True, comment="VARCHAR(128)|NULL: 最近操作者可信身份 ID，v2 必填"))
    for column_name, (existing_comment, target_comment) in CONFIG_SHA_COMMENTS.items():
        op.alter_column(
            "ai_config_record",
            column_name,
            existing_type=sa.String(length=64),
            type_=mysql.CHAR(length=64),
            existing_nullable=False,
            nullable=False,
            existing_comment=existing_comment,
            comment=target_comment,
        )
    op.create_index("ix_ai_config_record_key_status_created", "ai_config_record", ["config_key", "status", "created_at"], unique=False)
    op.create_index("ix_ai_config_record_release_fingerprint", "ai_config_record", ["release_fingerprint"], unique=False)
    op.create_index("ix_ai_config_record_prompt_template", "ai_config_record", ["prompt_template_id"], unique=False)
    op.create_index("ix_ai_config_record_model_pool", "ai_config_record", ["model_pool_id"], unique=False)

    # Phase C logical-call provenance.  Physical attempts remain Phase D and
    # are deliberately absent from this migration.
    op.add_column("ai_call_record", sa.Column("release_fingerprint", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 冻结运行行为 release fingerprint"))
    op.add_column("ai_call_record", sa.Column("execution_mode", sa.String(length=32), nullable=True, comment="VARCHAR(32)|NULL: 逻辑调用执行模式，候选 single/race"))
    op.add_column("ai_call_record", sa.Column("context_sha256", mysql.CHAR(length=64), nullable=True, comment="CHAR(64)|NULL: 渲染安全变量上下文 SHA256"))
    for column_name, comment in CALL_SHA_COMMENTS.items():
        is_nullable = column_name == "sent_image_manifest_sha256"
        op.alter_column(
            "ai_call_record",
            column_name,
            existing_type=sa.String(length=64),
            type_=mysql.CHAR(length=64),
            existing_nullable=is_nullable,
            nullable=is_nullable,
            existing_comment=comment,
            comment=comment,
        )
    op.create_index("ix_ai_call_record_release_fingerprint", "ai_call_record", ["release_fingerprint"], unique=False)
    op.create_index("ix_ai_call_record_task_created", "ai_call_record", ["task_id", "created_at"], unique=False)


def downgrade() -> None:
    _assert_no_v2_config_rows_for_downgrade()
    _assert_release_fingerprint_unique_for_downgrade()

    op.drop_index("ix_ai_call_record_task_created", table_name="ai_call_record")
    op.drop_index("ix_ai_call_record_release_fingerprint", table_name="ai_call_record")
    for column_name, comment in CALL_SHA_COMMENTS.items():
        is_nullable = column_name == "sent_image_manifest_sha256"
        op.alter_column(
            "ai_call_record",
            column_name,
            existing_type=mysql.CHAR(length=64),
            type_=sa.String(length=64),
            existing_nullable=is_nullable,
            nullable=is_nullable,
            existing_comment=comment,
            comment=comment,
        )
    op.drop_column("ai_call_record", "context_sha256")
    op.drop_column("ai_call_record", "execution_mode")
    op.drop_column("ai_call_record", "release_fingerprint")

    op.drop_index("ix_ai_config_record_model_pool", table_name="ai_config_record")
    op.drop_index("ix_ai_config_record_prompt_template", table_name="ai_config_record")
    op.drop_index("ix_ai_config_record_release_fingerprint", table_name="ai_config_record")
    op.drop_index("ix_ai_config_record_key_status_created", table_name="ai_config_record")
    for column_name, (target_comment, original_comment) in CONFIG_SHA_COMMENTS.items():
        op.alter_column(
            "ai_config_record",
            column_name,
            existing_type=mysql.CHAR(length=64),
            type_=sa.String(length=64),
            existing_nullable=False,
            nullable=False,
            existing_comment=target_comment,
            comment=original_comment,
        )
    for column_name in (
        "updated_by_id",
        "created_by_id",
        "retired_at",
        "activated_at",
        "validated_at",
        "output_schema_sha256",
        "output_schema_json",
        "model_snapshot_sha256",
        "model_snapshot_json",
        "model_pool_version",
        "model_pool_key",
        "model_pool_id",
        "prompt_content_sha256",
        "prompt_variables_json",
        "prompt_content",
        "prompt_version",
        "prompt_key",
        "prompt_template_id",
        "profile_key",
        "config_contract_version",
        "name",
    ):
        op.drop_column("ai_config_record", column_name)
    for column_name, (original_comment, target_comment) in V1_BUNDLE_COMMENTS.items():
        op.alter_column(
            "ai_config_record",
            column_name,
            existing_type=mysql.JSON(),
            existing_nullable=True,
            nullable=False,
            existing_comment=target_comment,
            comment=original_comment,
        )
    op.create_unique_constraint(
        "uq_ai_config_record_release_fingerprint",
        "ai_config_record",
        ["release_fingerprint"],
    )

    op.drop_index("ix_ai_control_audit_actor_created", table_name="ai_control_audit_record")
    op.drop_index("ix_ai_control_audit_key_created", table_name="ai_control_audit_record")
    op.drop_index("ix_ai_control_audit_resource_created", table_name="ai_control_audit_record")
    op.drop_table("ai_control_audit_record")
    op.drop_index("ix_ai_model_pool_sha256", table_name="ai_model_pool")
    op.drop_index("ix_ai_model_pool_execution_status", table_name="ai_model_pool")
    op.drop_table("ai_model_pool")
    op.drop_index("ix_ai_api_connection_sha256", table_name="ai_api_connection")
    op.drop_index("ix_ai_api_connection_provider_status", table_name="ai_api_connection")
    op.drop_table("ai_api_connection")
    op.drop_index("ix_ai_prompt_template_content_sha256", table_name="ai_prompt_template")
    op.drop_index("ix_ai_prompt_template_key_status_created", table_name="ai_prompt_template")
    op.drop_table("ai_prompt_template")
