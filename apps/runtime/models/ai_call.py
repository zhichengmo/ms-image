from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.runtime.models.imaging_base import ImagingRecordBase


class AICall(ImagingRecordBase):
    __tablename__ = "ai_call_record"
    __table_args__ = (
        UniqueConstraint("logical_call_key", name="uq_ai_call_record_logical_call"),
        UniqueConstraint("idempotency_key", name="uq_ai_call_record_idempotency"),
        Index("ix_ai_call_record_stage_status", "stage_checkpoint_id", "status"),
        Index("ix_ai_call_record_unknown_retry", "status", "next_reconcile_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Task 查询投影 opaque ID")
    stage_checkpoint_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 所属 Stage checkpoint ID")
    task_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Task attempt 序号")
    stage_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Stage attempt 序号")
    node_call_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: Stage attempt 内调用序号")
    logical_call_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): Task/Stage/input/config 逻辑调用键")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="VARCHAR(160): Provider 请求幂等键")
    ai_config_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): 冻结 AI Config ID")
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): Config 摘要")
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="VARCHAR(64): Provider adapter 类型")
    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="VARCHAR(160)|NULL: Provider request ID")
    requested_model: Mapped[str] = mapped_column(String(128), nullable=False, comment="VARCHAR(128): 请求模型")
    actual_model: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="VARCHAR(128)|NULL: Provider 确认模型")
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): Provider 请求摘要")
    rendered_prompt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 渲染 Prompt 摘要")
    schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 输出 Schema 摘要")
    requested_image_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="CHAR(64): 请求影像清单摘要")
    sent_image_manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="CHAR(64)|NULL: 实际发送影像清单摘要")
    image_count_requested: Mapped[int] = mapped_column(Integer, nullable=False, comment="INT: 请求影像数量")
    image_count_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="INT: 实际发送影像数量")
    image_receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: Provider 逐图 receipt")
    budget_reservation_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="JSON: 原子预算预留")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared", server_default=text("'prepared'"), comment="VARCHAR(32): prepared/sent/succeeded/failed/unknown")
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="BIGINT: AI Call CAS 版本")
    result_disposition: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"), comment="VARCHAR(32): pending/accepted/rejected/late/ignored")
    response_object_ref_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: 原始响应完整 ObjectRef")
    parsed_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="JSON|NULL: Schema 验证后的结构化结果")
    response_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="CHAR(64)|NULL: 响应摘要")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码")
    next_reconcile_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: unknown-call 对账时间")
    prepared_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, comment="DATETIME(6): prepared 时间")
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: sent 时间")
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 终态时间")


__all__ = ["AICall"]
