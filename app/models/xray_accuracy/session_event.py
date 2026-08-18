from typing import Any

from sqlalchemy import Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRaySessionEvent(XRayBaseModel):
    """Append-only lifecycle evidence before a Run exists."""

    __tablename__ = "xray_accuracy_session_event"
    __table_args__ = (
        Index("ix_xray_session_event_tenant_session", "tenant_id", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：Session event opaque 标识",
    )
    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，查询必须与 JWT 一致",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：Session 生命周期事件类型",
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="CHAR(64)：事件脱敏 payload SHA256，不保存敏感值",
    )
    trace_namespace: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：Session 生命周期审计命名空间",
    )
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：仅保存脱敏生命周期摘要",
    )
    created_by: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：创建事件的认证主体 opaque 标识",
    )
