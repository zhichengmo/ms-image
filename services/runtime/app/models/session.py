from datetime import datetime

from sqlalchemy import BigInteger, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.imaging_base import ImagingRecordBase


class Session(ImagingRecordBase):
    __tablename__ = "session_record"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_session_id",
            name="uq_session_record_source_session",
        ),
        UniqueConstraint("request_id", name="uq_session_record_request_id"),
        Index("ix_session_record_subject_created", "subject_id", "created_at"),
        Index("ix_session_record_status_created", "status", "created_at"),
    )

    source_system: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): 来源系统，例如 vet-platform",
    )
    source_session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 上游会话 opaque ID，用于跨服务幂等",
    )
    source_medical_record_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="VARCHAR(128)|NULL: 上游病历 opaque ID",
    )
    subject_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 宠物或患者 opaque ID",
    )
    requester_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 来自可信认证上下文的用户或服务 opaque ID",
    )
    request_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 创建请求幂等 ID",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        server_default=text("'open'"),
        comment=(
            "VARCHAR(32): 会话状态 open开放/processing处理中/"
            "completed处理完成/closed已关闭/cancelled已取消"
        ),
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Session 乐观锁版本，合法状态推进时递增",
    )
    started_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="DATETIME(6): 上游可信会话开始时间，UTC",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 影像处理完成时间，UTC",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 上游明确关闭时间，UTC",
    )
    cancelled_by_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="VARCHAR(128)|NULL: 取消操作人或服务 opaque ID",
    )
    cancel_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="VARCHAR(200)|NULL: 脱敏且稳定的取消业务原因",
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 会话取消时间，UTC",
    )


__all__ = ["Session"]
