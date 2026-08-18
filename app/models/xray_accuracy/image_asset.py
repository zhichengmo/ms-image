from datetime import datetime
from typing import Any

from sqlalchemy import Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayImageAsset(XRayBaseModel):
    """Stable object-storage reference; bytes never live in MySQL."""

    __tablename__ = "xray_accuracy_image_asset"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "study_revision_id", "source_index", "asset_role",
            name="uq_xray_asset_source_index_role",
        ),
        Index("ix_xray_asset_tenant_study", "tenant_id", "study_revision_id", "source_index"),
        Index("ix_xray_asset_tenant_status", "tenant_id", "asset_status"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：Image asset opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，查询必须与 JWT 一致",
    )
    study_revision_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：所属 Study revision opaque 标识",
    )
    source_image_ref: Mapped[str] = mapped_column(
        String(512), nullable=False,
        comment="VARCHAR(512)：上游短期 opaque 影像引用，不保存完整 URL",
    )
    parent_asset_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：派生图 parent asset opaque 标识，不声明 foreign key",
    )
    asset_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="original",
        comment="VARCHAR(32)：资产角色 original/normalized/crop",
    )
    source_index: Mapped[int] = mapped_column(
        nullable=False,
        comment="INT：Study 内稳定图像序号，从 0 连续编号",
    )
    object_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="VARCHAR(512)：OSS 稳定 object key，不保存 signed URL",
    )
    content_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：对象内容 SHA256",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：对象 MIME 类型",
    )
    byte_size: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="BIGINT：对象字节数",
    )
    pixel_width: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="INT：图像像素宽度",
    )
    pixel_height: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="INT：图像像素高度",
    )
    orientation: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="VARCHAR(32)：方向元数据，未知时为空",
    )
    projection: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：投照元数据，未知时为空",
    )
    body_part: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：部位元数据，未知时为空",
    )
    dicom_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：清洗后的非敏感 DICOM 技术元数据",
    )
    asset_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="VARCHAR(32)：资产状态 pending/uploaded/invalid/expired",
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：上传完成时间（UTC）",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：对象生命周期到期时间（UTC）",
    )
