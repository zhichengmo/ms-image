from sqlalchemy import BigInteger, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.imaging_base import ImagingRecordBase


class AIConfigRecord(ImagingRecordBase):
    __tablename__ = "ai_config_record"
    __table_args__ = (
        UniqueConstraint(
            "config_key", "version", name="uq_ai_config_record_key_version"
        ),
        UniqueConstraint("activation_slot", name="uq_ai_config_record_activation_slot"),
        UniqueConstraint(
            "release_fingerprint", name="uq_ai_config_record_release_fingerprint"
        ),
        Index(
            "ix_ai_config_record_scope_status",
            "activation_scope",
            "scope_key",
            "status",
        ),
    )

    config_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 稳定配置键"
    )
    version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 不可变配置版本"
    )
    activation_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): global/experiment"
    )
    scope_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 激活范围键"
    )
    activation_slot: Mapped[str | None] = mapped_column(
        String(320), nullable=True, comment="VARCHAR(320)|NULL: active 唯一槽"
    )
    modality_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): 适用模态"
    )
    task_type: Mapped[str] = mapped_column(
        String(48), nullable=False, comment="VARCHAR(48): 适用任务类型"
    )
    capability_manifest_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: 冻结 Provider capability，首期 provider_disabled",
    )
    compiled_pipeline_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: 固定 Profile 编译结果"
    )
    compiled_pipeline_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): compiled pipeline SHA256"
    )
    stage_registry_contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): Stage Registry 合同版本"
    )
    prompt_bundle_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: 冻结 zh-CN Prompt Bundle、资产内容、选择策略和 SHA",
    )
    schema_bundle_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: 冻结 CompleteMedicalResult Schema Bundle 和 SHA",
    )
    model_policy_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: requested model、Prompt/token/image budget 和 actual-model 要求",
    )
    provider_plan_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: Secret reference/disabled Provider 计划"
    )
    budget_policy_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: 冻结预算策略"
    )
    release_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="CHAR(64): Config、Prompt、Schema、模型、Provider 和代码合同联合摘要",
    )
    config_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 规范化 Config 正文摘要"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        comment="VARCHAR(32): draft/validated/active/retired",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Config CAS 版本",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 验证错误码"
    )


__all__ = ["AIConfigRecord"]
