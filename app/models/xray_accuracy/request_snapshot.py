from typing import Any

from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayRequestSnapshot(XRayBaseModel):
    __tablename__ = "xray_accuracy_request_snapshot"
    __table_args__ = (Index("ix_xray_snapshot_tenant_run", "tenant_id", "run_id"),)

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：RequestSnapshot 唯一标识",
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，查询必须与 JWT tenant 一致",
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key",
    )
    study_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：所属 Study opaque 标识，不声明 foreign key",
    )
    requested_operation: Mapped[str] = mapped_column(
        String(32), nullable=False, default="diagnose",
        comment="VARCHAR(32)：快照对应的 prepare_study/diagnose 操作",
    )
    study_revision: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：不可变 Study revision opaque 标识，不含 truth",
    )
    manifest_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False,
        comment="JSON：不可变 expected image manifest，不含 bytes/secret",
    )
    safe_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：允许的安全元数据，不含历史输出/truth/OCR/EXIF",
    )
    immutable_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="TIMESTAMP：快照冻结时间（UTC）",
    )
