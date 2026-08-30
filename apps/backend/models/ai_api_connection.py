from datetime import datetime

from sqlalchemy import BigInteger, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class AIAPIConnection(ImagingRecordBase):
    """Non-sensitive AI Platform routing and capability metadata."""

    __tablename__ = "ai_api_connection"
    __table_args__ = (
        UniqueConstraint("connection_key", "version", name="uq_ai_api_connection_key_version"),
        Index("ix_ai_api_connection_provider_status", "provider_type", "status"),
        Index("ix_ai_api_connection_sha256", "connection_sha256"),
    )

    connection_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 稳定连接业务键")
    version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 连接不可变版本")
    name: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): 连接中文显示名称")
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Provider adapter 类型")
    api_format: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 请求协议格式")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="VARCHAR(500): Provider 基础地址，不含 Secret")
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False, comment="VARCHAR(500): 遗留非空列兼容占位，当前业务合同固定为空且不参与鉴权")
    region: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: Provider 区域标识")
    capability_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: connection-capability.v1 非敏感能力声明")
    connection_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False, comment="CHAR(64): 规范化连接元数据 SHA256，不对 Secret 值计算")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default=text("'draft'"), comment="VARCHAR(32): 连接状态，候选 draft/validated/retired")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Connection CAS 版本")
    validated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 结构验证通过时间")
    retired_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 连接退役时间")
    created_by_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 创建者可信身份 ID")
    updated_by_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 最近操作者可信身份 ID")


__all__ = ["AIAPIConnection"]
