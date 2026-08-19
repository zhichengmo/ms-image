from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.imaging_base import ImagingRecordBase


class EvaluationJob(ImagingRecordBase):
    __tablename__ = "evaluation_job_record"
    __table_args__ = (UniqueConstraint("business_key", name="uq_evaluation_job_business_key"), Index("ix_evaluation_job_status", "status", "created_at"))
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): Evaluation/ControlPlane requester ID")
    business_key: Mapped[str] = mapped_column(String(200), nullable=False, comment="VARCHAR(200): Job 幂等键")
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 冻结 dataset 指纹")
    gold_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 冻结 Gold 指纹")
    scorer_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): scorer 指纹")
    experiment_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): experiment 指纹")
    case_split_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: case split/failure-bank/holdout 合同")
    input_manifest_artifact_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 输入 manifest Artifact ID")
    sanitization_artifact_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): sanitization Artifact ID")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/queued/running/completed/failed/cancelled")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Job CAS 版本")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")


class EvaluationOutbox(ImagingRecordBase):
    __tablename__ = "evaluation_outbox_record"
    __table_args__ = (UniqueConstraint("event_key", name="uq_evaluation_outbox_event_key"), Index("ix_evaluation_outbox_status", "publish_status", "next_retry_at"))
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID")
    aggregate_version: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="BIGINT: Job 版本")
    event_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): 事件幂等键")
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, comment="VARCHAR(48): execute_evaluation")
    message_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: opaque ID/version/trace")
    message_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 消息摘要")
    publish_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/published/retry_wait/dead_letter")
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下次重试")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")


class EvaluationRun(ImagingRecordBase):
    __tablename__ = "evaluation_run_record"
    __table_args__ = (UniqueConstraint("job_id", "run_no", name="uq_evaluation_run_job_no"), Index("ix_evaluation_run_status", "job_id", "status"))
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID")
    run_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Job 内 Run 序号")
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): dataset 指纹")
    gold_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): Gold 指纹")
    scorer_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): scorer 指纹")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/running/completed/failed")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Run CAS 版本")
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 结果摘要")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")


class EvaluationArtifact(ImagingRecordBase):
    __tablename__ = "evaluation_artifact_record"
    __table_args__ = (Index("ix_evaluation_artifact_job_run", "job_id", "run_id"), Index("ix_evaluation_artifact_kind", "artifact_kind", "created_at"))
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): EvaluationJob 查询投影")
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: EvaluationRun 查询投影")
    artifact_kind: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): input_manifest/sanitization/result/metrics")
    object_ref_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 完整 ObjectRef")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): Artifact 内容摘要")
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: producer/sanitization/visibility provenance")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): evaluation_internal/approval_only")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready", server_default=text("'ready'"), comment="VARCHAR(32): ready/failed/void")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")


__all__ = ["EvaluationArtifact", "EvaluationJob", "EvaluationOutbox", "EvaluationRun"]
