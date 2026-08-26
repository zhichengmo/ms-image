"""Physical Provider-attempt facts for one immutable AI logical call."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class AICallAttempt(ImagingRecordBase):
    """Durable network-delivery fact; no Provider I/O occurs before ``prepared`` commits."""

    __tablename__ = "ai_call_attempt_record"
    __table_args__ = (
        UniqueConstraint("ai_call_id", "attempt_no", name="uq_ai_call_attempt_record_call_no"),
        UniqueConstraint("physical_attempt_key", name="uq_ai_call_attempt_record_physical_key"),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_ai_call_attempt_record_provider_idempotency",
        ),
        Index("ix_ai_call_attempt_record_call_status", "ai_call_id", "status"),
        Index("ix_ai_call_attempt_record_reconcile", "status", "next_reconcile_at"),
    )

    ai_call_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 所属 Logical Call ID，不设外键"
    )
    attempt_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="INT: 同一 Logical Call 内 Physical Attempt 序号，从 1 开始"
    )
    physical_attempt_key: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 冻结物理发送事实的全局唯一摘要键"
    )
    provider_idempotency_key: Mapped[str] = mapped_column(
        String(160), nullable=False,
        comment="VARCHAR(160): 同一 Physical Attempt 网络重放固定复用的 Provider 幂等键",
    )
    trace_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 端到端追踪 ID"
    )
    request_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 业务请求 ID"
    )
    connection_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 冻结 Connection ID，不设外键"
    )
    connection_sha256: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 冻结 Connection 元数据 SHA256"
    )
    provider_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): Provider adapter 类型"
    )
    api_format: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): Gateway API 格式，候选 chat-completions/responses"
    )
    requested_model: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 冻结请求模型"
    )
    actual_model: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: Provider 确认的实际模型"
    )
    request_sha256: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 不含 Secret/签名 URL 的冻结 Gateway 请求 SHA256"
    )
    sent_image_manifest_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True, comment="CHAR(64)|NULL: 本 Attempt 实际发送影像清单 SHA256"
    )
    image_count_sent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"),
        comment="INT: 本 Attempt 实际发送影像张数",
    )
    image_receipt_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: ai-image-receipt.v1 脱敏影像发送回执，不含签名 URL",
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True, comment="VARCHAR(160)|NULL: Gateway/Provider 请求 ID"
    )
    usage_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: Provider usage 计量回执"
    )
    response_object_ref_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: encrypted-object-ref.v1 原始响应加密对象引用",
    )
    response_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True, comment="CHAR(64)|NULL: 原始 Provider 响应字节 SHA256"
    )
    parsed_result_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 严格 Schema 验证后的结构化结果"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="prepared", server_default=text("'prepared'"),
        comment="VARCHAR(32): Physical Attempt 状态，候选 prepared/sending/succeeded/failed/unknown/cancelled",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0"),
        comment="BIGINT: Physical Attempt CAS 版本",
    )
    prepared_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="DATETIME(6): prepared 已持久化时间"
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 开始发送网络时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Attempt 终态/已收敛时间"
    )
    next_reconcile_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: unknown Attempt 下次对账时间"
    )


__all__ = ["AICallAttempt"]
