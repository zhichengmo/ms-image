from datetime import datetime
from typing import Any

from sqlalchemy import Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, synonym

from .base import XRayBaseModel


class XRayOutbox(XRayBaseModel):
    __tablename__ = "xray_accuracy_outbox"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "task_id",
            name="uq_xray_outbox_tenant_run_task",
        ),
        Index("ix_xray_outbox_publish_retry", "publish_status", "next_retry_at"),
        Index(
            "ix_xray_outbox_tenant_publish_retry",
            "tenant_id",
            "publish_status",
            "next_retry_at",
        ),
        Index("ix_xray_outbox_run", "run_id"),
        Index("ix_xray_outbox_consumer", "consumer_status", "consumer_next_retry_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：Outbox event 唯一标识",
    )
    # The external event id is the same opaque value as the DAL primary key.
    # Keep a Python synonym for compatibility without storing a duplicate DB
    # column.
    event_id = synonym("id")
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，发布前必须校验",
    )
    task_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：异步任务幂等标识",
    )
    stage_key: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：阶段节点白名单名称",
    )
    release_fingerprint: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：发布指纹，不携带医学结论",
    )
    expected_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="INT：消费者执行 CAS 的预期版本",
    )
    trace_namespace: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：跨进程 trace namespace",
    )
    message_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False,
        comment="JSON：仅允许白名单消息字段，禁止 prompt/image/truth/output",
    )
    message_payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="CHAR(64)：白名单消息规范化 SHA256，用于 Broker 对账",
    )
    message_whitelist_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="xray-message.v1",
        comment="VARCHAR(32)：跨进程消息字段白名单版本",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="execute",
        comment="VARCHAR(64)：事件类型 execute/reconcile/review/delivery；取消由 stage_key 表示",
    )
    publish_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="VARCHAR(32)：发布状态 pending/publishing/published/retry/dead_letter",
    )
    consumer_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="VARCHAR(32)：消费者状态 pending/running/completed/retry_wait/dead_letter/cancelled",
    )
    consumer_owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Worker consumer lease 所有者，可为空",
    )
    consumer_lease_expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Worker consumer lease 到期时间（UTC）",
    )
    consumer_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="INT：消费者执行尝试次数，与 relay 发布次数分离",
    )
    consumer_started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：消费者开始执行时间（UTC）",
    )
    consumer_finished_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：消费者完成时间（UTC）",
    )
    consumer_next_retry_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：消费者下次重试时间（UTC）",
    )
    consumer_last_error: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="VARCHAR(255)：脱敏消费者错误，不含密钥/URL/原图",
    )
    relay_owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Outbox relay lease 所有者，可为空",
    )
    relay_lease_expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Outbox relay lease 到期时间（UTC）",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="INT：relay 发布尝试次数",
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：下次发布重试时间（UTC）",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：发布确认时间（UTC）",
    )
    last_error: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="VARCHAR(255)：脱敏技术错误摘要，禁止密钥/URL/原图",
    )
