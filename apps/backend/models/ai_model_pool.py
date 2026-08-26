from datetime import datetime

from sqlalchemy import BigInteger, Index, JSON, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class AIModelPool(ImagingRecordBase):
    """Versioned, reusable model execution pool. Phase A-C permits one single lane only."""

    __tablename__ = "ai_model_pool"
    __table_args__ = (
        UniqueConstraint("pool_key", "version", name="uq_ai_model_pool_key_version"),
        Index("ix_ai_model_pool_execution_status", "execution_mode", "status"),
        Index("ix_ai_model_pool_sha256", "pool_sha256"),
    )

    pool_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 稳定模型池业务键")
    version: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 模型池不可变版本")
    name: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): 模型池中文显示名称")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="VARCHAR(500)|NULL: 模型池用途说明")
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): 模型池执行模式，候选 single/race")
    winner_policy: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 模型池胜出策略，候选 single/first_technically_valid")
    lane_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="SMALLINT: 冻结 lane 数量，Phase A-C 固定 1")
    lane_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: ai-model-pool-lanes.v1 有序 lane 计划")
    pool_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False, comment="CHAR(64): 规范化模型池内容 SHA256")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default=text("'draft'"), comment="VARCHAR(32): 模型池状态，候选 draft/validated/retired")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: Model Pool CAS 版本")
    validated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 模型池验证通过时间")
    retired_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 模型池退役时间")
    created_by_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 创建者可信身份 ID")
    updated_by_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 最近操作者可信身份 ID")


__all__ = ["AIModelPool"]
