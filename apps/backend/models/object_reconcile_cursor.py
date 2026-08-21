from datetime import datetime

from sqlalchemy import BigInteger, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class ObjectReconcileCursor(ImagingRecordBase):
    __tablename__ = "object_reconcile_cursor_record"
    __table_args__ = (
        UniqueConstraint("cursor_key", name="uq_object_reconcile_cursor_key"),
        Index("ix_object_reconcile_cursor_due", "next_scan_at", "lease_expires_at"),
    )

    cursor_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): reconcile 范围稳定键")
    last_ready_updated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 上次成功扫描 Image updated_at")
    last_ready_image_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: 同时刻分页 Image ID")
    next_scan_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下次扫描时间")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: cursor CAS 版本")
    lease_owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VARCHAR(128)|NULL: reconcile lease owner")
    lease_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: reconcile lease 世代")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: reconcile lease 到期")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定扫描错误码")


__all__ = ["ObjectReconcileCursor"]
