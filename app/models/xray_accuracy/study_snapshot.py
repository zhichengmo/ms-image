from datetime import datetime
from typing import Any

from sqlalchemy import Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayStudySnapshot(XRayBaseModel):
    """Immutable study revision after preparation has been frozen."""

    __tablename__ = "xray_accuracy_study_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "study_revision_id", name="uq_xray_study_revision"),
        Index("ix_xray_study_tenant_session", "tenant_id", "session_id", "created_at"),
        Index("ix_xray_study_tenant_status", "tenant_id", "study_status"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：Study snapshot 行 opaque 标识",
    )
    study_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：稳定 Study opaque 标识，不声明 foreign key",
    )
    study_revision_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：不可变 Study revision opaque 标识",
    )
    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，查询必须与 JWT 一致",
    )
    study_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="received",
        comment="VARCHAR(32)：Study 状态 received/assembling/ready_full_study/partial/over_budget/invalid/expired",
    )
    expected_image_count: Mapped[int] = mapped_column(
        nullable=False,
        comment="INT：上游声明的 expected image 数量，不等于已发送数量",
    )
    expected_manifest_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="CHAR(64)：expected manifest ordered SHA256",
    )
    preparation_metadata_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="CHAR(64)：Study preparation 幂等输入摘要，不保存敏感元数据原文",
    )
    ordered_source_image_ids_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False,
        comment="JSON：按 source_index 排序的 opaque image asset 标识",
    )
    projection_groups_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：投照分组及安全元数据，不作医学结论",
    )
    body_scope: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：检查部位安全提示，不含诊断结论",
    )
    species: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="VARCHAR(32)：物种安全元数据，未知时为空",
    )
    identity_confidence: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown",
        comment="VARCHAR(32)：Study identity 置信状态 confirmed/conflict/unknown",
    )
    coverage_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown",
        comment="VARCHAR(32)：覆盖状态 unknown/ready_for_request/full_sent/partial_sent/over_budget",
    )
    frozen_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="TIMESTAMP：Study revision 冻结时间（UTC），非空后不可修改",
    )
