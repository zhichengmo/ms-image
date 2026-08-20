from datetime import datetime

from sqlalchemy import Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.imaging_base import ImagingRecordBase


class Report(ImagingRecordBase):
    __tablename__ = "report_record"
    __table_args__ = (
        UniqueConstraint("task_id", "revision_no", name="uq_report_record_task_revision"),
        Index("ix_report_record_task_status", "task_id", "status"),
        Index("ix_report_record_source_stage", "source_stage_checkpoint_id"),
    )

    task_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Task opaque ID")
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Task 内 Report 修订号")
    source_stage_checkpoint_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Finalization Stage ID")
    source_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="VARCHAR(64)|NULL: accepted AI Call ID")
    medical_status: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): not_produced/normal/abnormal/review_required/non_diagnostic")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 不可变医学/技术 Report 内容")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 规范 content SHA256")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="final", server_default=text("'final'"), comment="VARCHAR(32): final/published/superseded/void")
    render_manifest_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 渲染产物 manifest")
    published_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 发布确认时间")
    voided_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 作废时间")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")


__all__ = ["Report"]
