from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.evaluation_base import EvaluationRecordBase


class EvaluationJob(EvaluationRecordBase):
    __tablename__ = "evaluation_job_record"
    __table_args__ = (
        UniqueConstraint("business_key", name="uq_evaluation_job_business_key"),
        Index("ix_evaluation_job_status", "status", "created_at"),
        Index("ix_evaluation_job_lease", "status", "lease_expires_at"),
        Index(
            "ix_evaluation_job_retry",
            "status",
            "next_retry_at",
            "created_at",
        ),
    )

    requester_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): Evaluation/ControlPlane requester ID",
    )
    business_key: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="VARCHAR(200): Job 幂等键"
    )
    request_payload_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="CHAR(64): 规范化 Evaluation Job 创建请求 SHA256，用于完整 payload 幂等比对",
    )
    dataset_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 冻结 dataset 指纹"
    )
    gold_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 冻结 Gold 指纹"
    )
    scorer_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): scorer 指纹"
    )
    experiment_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): experiment 指纹"
    )
    case_split_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: case split/failure-bank/holdout 合同",
    )
    denominator_contract_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: 医学条件与端到端分母合同",
    )
    input_manifest_artifact_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): 输入 manifest Artifact ID",
    )
    sanitization_artifact_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): sanitization Artifact ID",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
        comment="VARCHAR(32): queued/running/retry_wait/completed/failed/cancelled/dead_letter",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Job CAS 版本",
    )
    lease_owner_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="VARCHAR(128)|NULL: Evaluation Worker lease owner",
    )
    lease_generation: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Evaluation Worker lease 世代，防止旧 Worker 回写",
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: Evaluation Worker lease 到期时间，UTC",
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: Evaluation Worker 最近心跳时间，UTC",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="INT: Evaluation Job 已安排的重试次数",
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 下一次可执行时间，UTC",
    )
    result_artifact_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="VARCHAR(64)|NULL: metric_summary Artifact ID",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 首次开始时间，UTC",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 终态完成时间，UTC",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"
    )


class EvaluationOutbox(EvaluationRecordBase):
    __tablename__ = "evaluation_outbox_record"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_evaluation_outbox_event_key"),
        Index(
            "ix_evaluation_outbox_status",
            "publish_status",
            "next_retry_at",
            "created_at",
        ),
        Index(
            "ix_evaluation_outbox_lease",
            "publish_status",
            "relay_lease_expires_at",
        ),
        Index("ix_evaluation_outbox_job", "job_id", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID"
    )
    aggregate_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="BIGINT: Job 版本"
    )
    event_key: Mapped[str] = mapped_column(
        String(160), nullable=False, comment="VARCHAR(160): 事件幂等键"
    )
    event_type: Mapped[str] = mapped_column(
        String(48), nullable=False, comment="VARCHAR(48): execute_evaluation"
    )
    destination_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): Evaluation queue 配置键"
    )
    trace_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 跨边界 trace ID"
    )
    message_version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): Evaluation 消息合同版本"
    )
    message_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: opaque ID/version/trace"
    )
    message_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 消息摘要"
    )
    publish_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="VARCHAR(32): pending/publishing/published/retry_wait/dead_letter/cancelled",
    )
    relay_owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: Relay lease owner"
    )
    relay_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Relay lease 到期"
    )
    publish_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="INT: 发布尝试次数",
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下次重试"
    )
    broker_message_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: Broker message ID"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: publisher confirm 时间",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"
    )


class EvaluationRun(EvaluationRecordBase):
    __tablename__ = "evaluation_run_record"
    __table_args__ = (
        UniqueConstraint("job_id", "run_no", name="uq_evaluation_run_job_no"),
        Index("ix_evaluation_run_status", "job_id", "status"),
    )

    job_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID"
    )
    run_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="INT: Job 内 Run 序号"
    )
    dataset_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): dataset 指纹"
    )
    gold_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): Gold 指纹"
    )
    scorer_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): scorer 指纹"
    )
    experiment_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): experiment 指纹"
    )
    case_split_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 冻结 case split 合同摘要"
    )
    denominator_contract_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 冻结双分母合同摘要"
    )
    input_manifest_artifact_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 输入 manifest Artifact 摘要"
    )
    sanitization_artifact_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 脱敏证明 Artifact 摘要"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="started",
        server_default=text("'started'"),
        comment="VARCHAR(32): started/succeeded/failed/cancelled/unknown",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Run CAS 版本",
    )
    summary_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 结果摘要"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"
    )
    started_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="DATETIME(6): Run 开始时间，UTC"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Run 完成时间，UTC"
    )


class EvaluationArtifact(EvaluationRecordBase):
    __tablename__ = "evaluation_artifact_record"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "run_id",
            "artifact_kind",
            name="uq_evaluation_artifact_run_kind",
        ),
        Index("ix_evaluation_artifact_job_run", "job_id", "run_id"),
        Index("ix_evaluation_artifact_kind", "artifact_kind", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): EvaluationJob 查询投影"
    )
    run_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: EvaluationRun 查询投影"
    )
    artifact_kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): input_manifest/sanitization/case_result/failure_summary/metric_summary/paired_ab_summary",
    )
    object_ref_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: 完整 ObjectRef"
    )
    content_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): Artifact 内容摘要"
    )
    provenance_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: producer/sanitization/visibility provenance",
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): evaluation_internal/approval_only",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ready",
        server_default=text("'ready'"),
        comment="VARCHAR(32): ready/failed/void",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"
    )


__all__ = ["EvaluationArtifact", "EvaluationJob", "EvaluationOutbox", "EvaluationRun"]
