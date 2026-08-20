from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.imaging_base import ImagingRecordBase


class Study(ImagingRecordBase):
    __tablename__ = "study_record"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "source_study_id", name="uq_study_record_session_source"
        ),
        UniqueConstraint("revision_id", name="uq_study_record_revision_id"),
        Index("ix_study_record_session_created", "session_id", "created_at"),
        Index(
            "ix_study_record_modality_status_created",
            "modality_type",
            "status",
            "created_at",
        ),
        Index("ix_study_record_dicom_uid", "dicom_study_uid"),
    )

    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 所属 Session opaque ID"
    )
    source_study_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 上游或服务端稳定生成的 Study opaque ID",
    )
    modality_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment=(
            "VARCHAR(32): 模态 xray/ct/mri/ultrasound/endoscopy/pathology/"
            "clinical_photo/dental_xray/other"
        ),
    )
    dicom_study_uid: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: DICOM StudyInstanceUID"
    )
    body_part: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 检查部位技术信息"
    )
    metadata_schema_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): Study 技术元数据白名单合同版本",
    )
    revision_no: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="BIGINT: 当前影像集合修订号，从 1 递增",
    )
    revision_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 当前修订 opaque ID"
    )
    revision_reason: Mapped[str | None] = mapped_column(
        String(48),
        nullable=True,
        comment="VARCHAR(48)|NULL: 修订原因 initial/add/replace/delete/reorder/metadata_correction",
    )
    revision_changed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="DATETIME(6): 当前修订生效时间，UTC"
    )
    expected_image_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="INT|NULL: 上游声明的当前修订预期影像数"
    )
    expected_manifest_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="CHAR(64)|NULL: 上游声明的有序清单 SHA256"
    )
    resolved_manifest_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="CHAR(64)|NULL: 服务端解析后的有序清单 SHA256"
    )
    completeness_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="VARCHAR(32): 完整性 unknown未知/partial不完整/complete完整/conflict冲突",
    )
    completeness_attested_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 完整性声明者 opaque ID"
    )
    identity_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="VARCHAR(32): 身份一致性 unknown未知/confirmed已确认/conflict冲突",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ingesting",
        server_default=text("'ingesting'"),
        comment="VARCHAR(32): 接入状态 ingesting接入中/validating校验中/ready就绪/invalid无效",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: Study 修订和状态推进的 CAS 版本",
    )
    technical_metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 不含诊断结论的白名单 Study 技术元数据"
    )
    acquired_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 影像采集时间，UTC"
    )
    ready_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 完整性通过时间，UTC"
    )


__all__ = ["Study"]
