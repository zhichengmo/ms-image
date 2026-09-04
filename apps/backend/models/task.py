from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class Task(ImagingRecordBase):
    __tablename__ = "task_record"
    __table_args__ = (
        UniqueConstraint("business_key", name="uq_task_record_business_key"),
        Index("ix_task_record_study_created", "study_id", "created_at"),
        Index("ix_task_record_requester_created", "requester_id", "created_at"),
        Index("ix_task_record_execution_retry", "execution_status", "next_retry_at"),
        Index(
            "ix_task_record_source_type_created",
            "source_task_id",
            "task_type",
            "created_at",
        ),
    )

    study_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Study opaque ID")
    source_task_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "VARCHAR(64)|NULL: 来源诊断 Task opaque ID，仅 anatomy_localization 使用"
        ),
    )
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): Caller 可信身份 opaque ID")
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): Caller 请求幂等 ID")
    task_type: Mapped[str] = mapped_column(String(48), nullable=False, comment="VARCHAR(48): 类型 diagnose/quality_control/generate_report/replay/qualification")
    business_key: Mapped[str] = mapped_column(String(200), nullable=False, comment="VARCHAR(200): 全局业务幂等键")
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): API/执行合同版本")
    ai_config_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 冻结 AI Config opaque ID")
    compiled_pipeline_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 冻结 compiled pipeline SHA256")
    stage_registry_contract_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Stage Registry 合同版本")
    routing_policy_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): ControlPlane 路由策略版本")
    assignment_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 冻结分配摘要")
    study_revision_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 冻结 Study revision opaque ID")
    report_required: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("1"), comment="TINYINT(1): 是否要求 Report")
    run_mode: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): production/shadow/validation_only/replay，仅 ControlPlane 注入")
    experiment_arm_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VARCHAR(128)|NULL: ControlPlane 实验臂 opaque ID")
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/queued/running/retry_wait/completed/failed/cancelled/dead_letter")
    ai_medical_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_produced", server_default=text("'not_produced'"), comment="VARCHAR(32): not_produced/not_applicable/normal/abnormal/review_required/non_diagnostic")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Task CAS 版本")
    request_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 冻结脱敏请求与有序 Image manifest")
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 冻结请求载体 SHA256")
    budget_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 冻结预算")
    budget_reserved_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 原子预留预算")
    budget_consumed_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 已结算预算")
    current_report_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: 当前 Report opaque ID")
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), comment="INT: Task 执行尝试号")
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下一次重试时间")
    deadline_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Task 截止时间")
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 跨边界 trace ID")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要")
    cancel_requested_by_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VARCHAR(128)|NULL: 取消 Caller ID")
    cancel_reason: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="VARCHAR(200)|NULL: 取消原因")
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 取消请求时间")
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 首次开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 终态时间")


__all__ = ["Task"]
