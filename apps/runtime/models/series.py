from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.runtime.models.imaging_base import ImagingRecordBase


class Series(ImagingRecordBase):
    __tablename__ = "series_record"
    __table_args__ = (
        UniqueConstraint("study_id", "series_key", name="uq_series_record_study_key"),
        Index(
            "ix_series_record_study_status_no", "study_id", "status", "series_no"
        ),
        Index("ix_series_record_dicom_uid", "dicom_series_uid"),
    )

    study_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 所属 Study opaque ID"
    )
    series_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): Study 内稳定分组键"
    )
    dicom_series_uid: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: DICOM SeriesInstanceUID"
    )
    series_no: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="INT|NULL: 归一化 SeriesNumber 或稳定展示顺序"
    )
    metadata_schema_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): Series 技术元数据白名单合同版本",
    )
    expected_image_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="INT|NULL: 上游声明的预期 Instance 数"
    )
    actual_image_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="INT: 从当前修订 ready Image 集合确定性计算的影像数",
    )
    manifest_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="CHAR(64)|NULL: Series 有序影像清单 SHA256"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ingesting",
        server_default=text("'ingesting'"),
        comment="VARCHAR(32): 状态 ingesting接入中/validating校验中/ready就绪/incomplete不完整/invalid无效",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Series 影像集合或状态变化的 CAS 版本",
    )
    technical_metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 层厚、间距、方向、几何等白名单元数据"
    )
    acquired_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Series 采集时间，UTC"
    )
    ready_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Series 校验通过时间，UTC"
    )


__all__ = ["Series"]
