from datetime import datetime
from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayRun(XRayBaseModel):
    __tablename__ = "xray_accuracy_run"
    __table_args__ = (
        Index("ix_xray_run_tenant_created", "tenant_id", "created_at"),
        Index("ix_xray_run_tenant_status", "tenant_id", "execution_status"),
        UniqueConstraint(
            "tenant_id", "request_id", "contract_version",
            name="uq_xray_run_tenant_request_contract",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="VARCHAR(64)：Run 唯一标识（opaque）"
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="VARCHAR(128)：租户标识，来自已验证 JWT，不接受请求覆盖",
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：认证主体标识，不承载医学结论",
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key",
    )
    study_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：所属 Study opaque 标识，不声明 foreign key",
    )
    request_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：客户端幂等请求标识",
    )
    case_request_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：上游病例请求 opaque 标识，可为空",
    )
    requested_operation: Mapped[str] = mapped_column(
        String(32), nullable=False, default="diagnose",
        comment="VARCHAR(32)：运行操作 prepare_study/diagnose/qualification",
    )
    contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：API/数据合同版本字符串",
    )
    payload_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="CHAR(64)：规范化请求 SHA256，不含 secret/原图 bytes",
    )
    release_fingerprint: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：validation-only 发布指纹，不代表生产发布",
    )
    trace_namespace: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：HTTP→Outbox→Worker trace 命名空间",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="BIGINT：Run CAS 状态版本，单调递增",
    )
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued",
        comment="VARCHAR(32)：执行状态 queued/running/completed/failed/cancel_requested/cancelled",
    )
    ai_medical_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_produced",
        comment="VARCHAR(32)：医学状态 not_produced，零模型阶段禁止写 verdict",
    )
    delivery_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_published",
        comment="VARCHAR(32)：交付状态 not_published/held/published；执行模式由 validation_only 单独表达",
    )
    engineering_eligibility: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown",
        comment="VARCHAR(32)：工程可评估状态 unknown/clean/failed",
    )
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="validation_only",
        comment="VARCHAR(32)：执行模式 validation_only/production，单一执行模式事实源",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：技术终态时间（UTC），未终态为空",
    )
