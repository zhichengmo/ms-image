from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class Image(ImagingRecordBase):
    __tablename__ = "image_record"
    __table_args__ = (
        UniqueConstraint(
            "storage_profile", "object_key", name="uq_image_record_storage_object"
        ),
        UniqueConstraint(
            "series_id",
            "logical_image_key",
            "image_version_no",
            name="uq_image_record_logical_version",
        ),
        Index(
            "ix_image_record_logical_status_version",
            "series_id",
            "logical_image_key",
            "status",
            "image_version_no",
        ),
        Index(
            "ix_image_record_series_status_sequence",
            "series_id",
            "status",
            "sequence_no",
        ),
        Index("ix_image_record_sha256", "sha256"),
        Index("ix_image_record_sop_uid", "sop_instance_uid"),
        Index(
            "ix_image_record_retry",
            "status",
            "next_validation_at",
            "created_at",
        ),
        Index(
            "ix_image_record_validation_lease",
            "status",
            "validation_lease_expires_at",
        ),
    )

    series_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 所属 Series opaque ID"
    )
    source_image_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 上游影像 opaque ID"
    )
    logical_image_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): Series 内逻辑影像稳定键"
    )
    image_version_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="INT: 同一逻辑影像版本号，从 1 递增"
    )
    supersedes_image_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 被当前版本替换的上一 Image ID"
    )
    source_manifest_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 有序源 Image/ObjectRef 与变换版本清单"
    )
    sequence_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="INT: Series 内从 1 开始的稳定顺序"
    )
    image_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 角色 original/display/thumbnail/normalized/derived/segmentation",
    )
    image_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 形态 instance/photo/cine/video/wsi/volume/other",
    )
    metadata_schema_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): Image 技术元数据和 source manifest 合同版本",
    )
    storage_profile: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="VARCHAR(40): OSS Bucket/Endpoint 配置标识"
    )
    object_key: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="VARCHAR(512): OSS 稳定对象键，不保存 URL"
    )
    object_version_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True, comment="VARCHAR(160)|NULL: OSS 对象版本标识"
    )
    file_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 格式 dicom/jpeg/png/mp4/nifti/tiff/svs/other",
    )
    upload_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 上传模式 direct_put/multipart/internal_import",
    )
    upload_session_ref: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="VARCHAR(256)|NULL: multipart 上传会话 opaque 引用"
    )
    expected_part_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="INT|NULL: multipart 预期分片数"
    )
    expected_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="CHAR(64)|NULL: 调用方声明的待比对 SHA256"
    )
    expected_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="BIGINT|NULL: 调用方声明的对象字节数"
    )
    declared_content_type: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 调用方声明的 MIME"
    )
    content_type: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 服务端校验后的 MIME"
    )
    sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="CHAR(64)|NULL: 服务端流式校验的内容 SHA256"
    )
    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="BIGINT|NULL: 服务端校验后的对象字节数"
    )
    kms_key_version: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 对象加密密钥版本引用"
    )
    sop_instance_uid: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: DICOM SOPInstanceUID"
    )
    sop_class_uid: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: DICOM SOP Class UID"
    )
    instance_no: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="INT|NULL: DICOM InstanceNumber"
    )
    projection: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: XRay 投照位技术信息"
    )
    technical_metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 宽高、帧数、方向、像素间距等技术元数据"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploading",
        server_default=text("'uploading'"),
        comment="VARCHAR(32): 状态 uploading/validating/ready/superseded/quarantined/deleted",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: 上传确认、替换和隔离状态 CAS 版本",
    )
    validation_owner_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 当前校验 Worker 租约 owner"
    )
    validation_lease_generation: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: 校验租约世代，每次成功领取递增",
    )
    validation_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 当前校验租约到期时间"
    )
    validation_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 校验 Worker 最近心跳时间"
    )
    validation_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="INT: 影像完整校验尝试次数",
    )
    next_validation_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下一次允许校验时间"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定技术错误码"
    )
    upload_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 上传窗口到期时间"
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 对象与技术事实校验通过时间"
    )


__all__ = ["Image"]
