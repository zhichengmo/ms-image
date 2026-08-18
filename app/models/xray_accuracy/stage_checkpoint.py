from datetime import datetime

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayStageCheckpoint(XRayBaseModel):
    __tablename__ = "xray_accuracy_stage_checkpoint"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "stage_key",
            "attempt_id",
            name="uq_xray_checkpoint_run_stage_attempt",
        ),
        Index("ix_xray_checkpoint_tenant_run_stage", "tenant_id", "run_id", "stage_key", "attempt_id"),
        Index("ix_xray_checkpoint_tenant_lease", "tenant_id", "status", "lease_expires_at"),
        Index("ix_xray_checkpoint_lease", "status", "lease_expires_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：StageCheckpoint 唯一标识",
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，禁止跨租户读取",
    )
    stage_key: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：状态机节点白名单名称",
    )
    attempt_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：逻辑任务尝试标识；Provider physical retry 由 ModelCall attempt_id 区分",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued",
        comment="VARCHAR(32)：阶段状态 queued/retry/running/completed/failed/cancelled/late",
    )
    owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Worker lease 所有者，可为空",
    )
    expected_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="BIGINT：claim 时预期 Run state_version",
    )
    input_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：阶段输入摘要 SHA256",
    )
    output_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：阶段输出摘要 SHA256，零模型可为空",
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Worker lease 到期时间（UTC）",
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Worker heartbeat 时间（UTC）",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：阶段开始时间（UTC）",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：阶段结束时间（UTC）",
    )
    error_class: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：技术错误分类，不映射 normal/abnormal",
    )
