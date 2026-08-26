from datetime import datetime

from sqlalchemy import Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.core.async_db import BaseModel
from apps.backend.models.imaging_base import new_opaque_id


class AIControlAuditRecord(BaseModel):
    """Append-only, command-idempotency audit record for high-impact AI controls."""

    __tablename__ = "ai_control_audit_record"
    __table_args__ = (
        UniqueConstraint("request_id", "resource_type", "action_type", name="uq_ai_control_audit_request_resource_action"),
        Index("ix_ai_control_audit_resource_created", "resource_type", "resource_id", "created_at"),
        Index("ix_ai_control_audit_key_created", "resource_key", "created_at"),
        Index("ix_ai_control_audit_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_opaque_id, comment="VARCHAR(64): 控制面审计事件 opaque ID，单列主键")
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 控制面资源类型，候选 prompt/connection/model_pool/ai_config")
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 被操作资源 opaque ID")
    resource_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 被操作资源稳定业务键")
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 控制面动作类型，候选 create/update/validate/activate/retire/rollback")
    before_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True, comment="CHAR(64)|NULL: 操作前资源摘要")
    after_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True, comment="CHAR(64)|NULL: 操作后资源摘要")
    changed_fields_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: ai-control-change-set.v1 变更字段与脱敏摘要")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="VARCHAR(500)|NULL: 操作原因或回滚原因")
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 控制面命令幂等与追踪 ID")
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): 操作者类型，候选 user/service")
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 可信操作者身份 ID")
    result_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="VARCHAR(32): 审计结果类型，候选 succeeded/rejected/failed")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)"), comment="DATETIME(6): 审计事件创建时间，UTC")


__all__ = ["AIControlAuditRecord"]
