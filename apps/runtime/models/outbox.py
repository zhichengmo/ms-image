from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.runtime.models.imaging_base import ImagingRecordBase


class Outbox(ImagingRecordBase):
    __tablename__ = "outbox_record"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_outbox_record_event_key"),
        Index(
            "ix_outbox_record_publish_retry",
            "publish_status",
            "next_retry_at",
            "created_at",
        ),
        Index(
            "ix_outbox_record_publish_lease",
            "publish_status",
            "relay_lease_expires_at",
        ),
        Index(
            "ix_outbox_record_aggregate",
            "aggregate_type",
            "aggregate_id",
            "created_at",
        ),
    )

    aggregate_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): 业务 owner 类型 image/stage/call"
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 业务 owner opaque ID"
    )
    aggregate_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="BIGINT: 创建事件时业务 owner CAS 版本"
    )
    event_key: Mapped[str] = mapped_column(
        String(160), nullable=False, comment="VARCHAR(160): 不可变事件幂等键"
    )
    event_type: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        comment="VARCHAR(48): 事件类型 validate_image/execute_stage/reconcile",
    )
    destination_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 目标队列或 topic 稳定配置键"
    )
    trace_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 跨边界追踪 opaque ID"
    )
    message_version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): Broker 白名单消息合同版本"
    )
    message_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="JSON: 仅含 opaque ID、版本和 trace，禁止影像/Prompt/truth/Secret",
    )
    message_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="CHAR(64): 规范消息载荷 SHA256"
    )
    publish_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="VARCHAR(32): 发布状态 pending/publishing/published/retry_wait/dead_letter/cancelled",
    )
    relay_owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: relay lease owner"
    )
    relay_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: relay lease 到期时间，UTC"
    )
    publish_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="INT: Broker 发布尝试次数",
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下一次发布重试时间，UTC"
    )
    broker_message_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: Broker/Celery 消息 ID"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Broker confirm 时间，UTC"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定发布错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏发布错误摘要"
    )


__all__ = ["Outbox"]
