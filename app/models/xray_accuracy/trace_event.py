from typing import Any

from sqlalchemy import BigInteger, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayTraceEvent(XRayBaseModel):
    __tablename__ = "xray_accuracy_trace_event"
    __table_args__ = (
        Index("ix_xray_trace_tenant_run_created", "tenant_id", "run_id", "created_at"),
        Index("ix_xray_trace_run_created", "run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：TraceEvent 唯一标识（append-only）",
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，读取必须 tenant filter",
    )
    trace_namespace: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：跨 HTTP/Broker/Worker 的 trace namespace",
    )
    stage_key: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：阶段节点白名单名称",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：技术事件类型，不承载医学 verdict",
    )
    event_payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：脱敏事件字段，不含 prompt/原图/secret",
    )
    fingerprint: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：事件指纹，供重放与审计",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="BIGINT：事件对应 Run CAS 版本",
    )
