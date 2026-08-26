"""Immutable AI runtime Config records with explicit v1/v2 read compatibility."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class AIConfigRecord(ImagingRecordBase):
    """The only runtime release record; v2 rows freeze all execution inputs."""

    __tablename__ = "ai_config_record"
    __table_args__ = (
        UniqueConstraint("config_key", "version", name="uq_ai_config_record_key_version"),
        UniqueConstraint("activation_slot", name="uq_ai_config_record_activation_slot"),
        Index("ix_ai_config_record_scope_status", "activation_scope", "scope_key", "status"),
        Index("ix_ai_config_record_key_status_created", "config_key", "status", "created_at"),
        Index("ix_ai_config_record_release_fingerprint", "release_fingerprint"),
        Index("ix_ai_config_record_prompt_template", "prompt_template_id"),
        Index("ix_ai_config_record_model_pool", "model_pool_id"),
    )

    config_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 稳定 AI Config 业务键"
    )
    version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): AI Config 不可变版本"
    )
    name: Mapped[str | None] = mapped_column(
        String(160), nullable=True, comment="VARCHAR(160)|NULL: AI Config 中文显示名称，v2 必填"
    )
    config_contract_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)|NULL: AI Config 数据合同版本，v2 为 ai-config.v2",
    )
    modality_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): 适用影像模态"
    )
    task_type: Mapped[str] = mapped_column(
        String(48), nullable=False, comment="VARCHAR(48): 适用 Task 类型"
    )
    profile_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 固定 Pipeline Profile 键，v2 必填"
    )
    activation_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): global/experiment 激活范围"
    )
    scope_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 激活范围键"
    )
    activation_slot: Mapped[str | None] = mapped_column(
        String(320), nullable=True,
        comment="VARCHAR(320)|NULL: Active Config 槽，v2 写作用域 SHA256，v1 保留历史复合槽",
    )

    # v2 immutable Prompt snapshot.  The source table is a logical reference;
    # no foreign keys are declared so historical Config snapshots remain usable.
    prompt_template_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 来源 Prompt 模板版本 ID，v2 必填"
    )
    prompt_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 冻结 Prompt 业务键，v2 必填"
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 冻结 Prompt 版本，v2 必填"
    )
    prompt_content: Mapped[str | None] = mapped_column(
        MEDIUMTEXT, nullable=True, comment="MEDIUMTEXT|NULL: 冻结完整 Prompt 正文，v2 必填"
    )
    prompt_variables_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 冻结 prompt-variables.v1 合同，v2 必填"
    )
    prompt_content_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True, comment="CHAR(64)|NULL: 冻结 Prompt 正文 SHA256，v2 必填"
    )
    prompt_message_contract_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: 冻结 prompt-message-contract.v1，NULL 表示旧单正文兼容",
    )
    prompt_source_receipt_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True,
        comment="CHAR(64)|NULL: 冻结 Prompt 外部来源回执 SHA256",
    )

    # v2 immutable expanded model/connection snapshot.  The secret reference
    # is stored only inside this runtime snapshot and must never be serialized
    # by control-plane responses.
    model_pool_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 来源 Model Pool 版本 ID，v2 必填"
    )
    model_pool_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 冻结 Model Pool 业务键，v2 必填"
    )
    model_pool_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 冻结 Model Pool 版本，v2 必填"
    )
    model_snapshot_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: ai-model-snapshot.v1 展开模型与连接快照，v2 必填"
    )
    model_snapshot_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True, comment="CHAR(64)|NULL: 模型与连接快照 SHA256，v2 必填"
    )
    output_schema_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 冻结输出 JSON Schema，v2 必填"
    )
    output_schema_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True, comment="CHAR(64)|NULL: 冻结输出 Schema SHA256，v2 必填"
    )

    gateway_profile_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: ai-gateway-profile.v1 冻结 Gateway 资格和 SSE 传输合同",
    )
    capability_manifest_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: ai-capability-manifest.v1 冻结能力清单"
    )
    compiled_pipeline_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: 冻结 Profile 编译结果"
    )
    compiled_pipeline_sha256: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 编译后 Pipeline SHA256"
    )
    stage_registry_contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): Stage Registry 合同版本"
    )
    budget_policy_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: ai-budget-policy.v1 Task/Call 冻结预算策略"
    )
    config_sha256: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 规范化 AI Config 冻结正文 SHA256"
    )
    release_fingerprint: Mapped[str] = mapped_column(
        CHAR(64), nullable=False,
        comment="CHAR(64): 行为相关 Prompt/模型/Schema/Pipeline 联合指纹",
    )

    # v1 fields remain nullable for historical rows only.  New API writes are
    # restricted to ai-config.v2 and never accept these client-supplied bundles.
    prompt_bundle_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: v1 冻结 Prompt Bundle 兼容读取字段"
    )
    schema_bundle_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: v1 冻结 Schema Bundle 兼容读取字段"
    )
    model_policy_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: v1 模型策略兼容读取字段"
    )
    provider_plan_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: v1 Provider 计划兼容读取字段"
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default=text("'draft'"),
        comment="VARCHAR(32): draft/validated/active/retired",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0"),
        comment="BIGINT: AI Config CAS 版本",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 最近稳定验证错误码"
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 验证通过时间"
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 最近激活时间"
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Config 最近退役时间"
    )
    created_by_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 创建者可信身份 ID，v2 必填"
    )
    updated_by_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 最近操作者可信身份 ID，v2 必填"
    )


__all__ = ["AIConfigRecord"]
