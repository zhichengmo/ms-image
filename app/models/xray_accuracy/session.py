from datetime import datetime

from sqlalchemy import Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRaySession(XRayBaseModel):
    """Business session owned by ms-image, independent from a diagnosis Run."""

    __tablename__ = "xray_accuracy_session"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_id", name="uq_xray_session_tenant_request"),
        Index("ix_xray_session_tenant_created", "tenant_id", "created_at"),
        Index("ix_xray_session_tenant_status", "tenant_id", "session_status"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：Session opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="VARCHAR(128)：租户标识，来自已验证 JWT",
    )
    subject_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：认证主体 opaque 标识",
    )
    request_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：Session 创建幂等请求标识",
    )
    case_request_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：上游病例请求 opaque 标识",
    )
    module_key: Mapped[str] = mapped_column(
        String(64), nullable=False, default="xray",
        comment="VARCHAR(64)：业务模块标识，当前固定 xray",
    )
    session_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open",
        comment="VARCHAR(32)：Session 状态 open/closed/cancelled",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：不含 truth/Prompt/原图地址的安全会话元数据",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Session 关闭时间（UTC）",
    )
