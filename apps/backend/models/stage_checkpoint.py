from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class StageCheckpoint(ImagingRecordBase):
    __tablename__ = "stage_checkpoint_record"
    __table_args__ = (
        UniqueConstraint("task_id", "task_attempt_no", "stage_instance_key", name="uq_stage_checkpoint_task_instance"),
        Index("ix_stage_checkpoint_task_no", "task_id", "stage_no"),
        Index("ix_stage_checkpoint_handler", "handler_key", "handler_version", "created_at"),
        Index("ix_stage_checkpoint_retry", "status", "next_retry_at"),
        Index("ix_stage_checkpoint_lease", "status", "lease_expires_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Task opaque ID")
    task_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Task 尝试号")
    stage_instance_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): Stage 实例稳定键")
    stage_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Pipeline 顺序号")
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Stage 业务键")
    handler_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 冻结 handler key")
    handler_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 冻结 handler 版本")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/queued/running/completed/failed/cancelled/dead_letter")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Stage CAS 版本")
    lease_owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VARCHAR(128)|NULL: Worker lease owner")
    lease_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: lease 世代")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: lease 到期")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Worker 心跳")
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 小型冻结 Stage 输入")
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): Stage 输入 SHA256")
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 小型 Stage 输出")
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="CHAR(64)|NULL: Stage 输出 SHA256")
    budget_reservation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: Stage 预算预留")
    accepted_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: 接受的 AI Call ID")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="INT: Stage 重试次数")
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下一次重试")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 终态时间")


__all__ = ["StageCheckpoint"]
