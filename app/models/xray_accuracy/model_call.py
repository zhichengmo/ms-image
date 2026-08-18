from typing import Any

from sqlalchemy import BigInteger, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import XRayBaseModel


class XRayModelCall(XRayBaseModel):
    __tablename__ = "xray_accuracy_model_call"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "node_key",
            "attempt_id",
            name="uq_xray_model_call_tenant_run_node_attempt",
        ),
        Index("ix_xray_model_call_run_node", "run_id", "node_key"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="VARCHAR(64)：ModelCall 审计标识",
    )
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="VARCHAR(128)：租户标识，禁止跨租户读取",
    )
    attempt_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：Provider 物理调用尝试标识；Checkpoint attempt 记录于 receipt request_trace",
    )
    node_key: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：逻辑节点标识，当前仅 engineering_stub",
    )
    module_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Prompt module_key，例如 xray_accuracy；零模型请求日志字段",
    )
    provider_key: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="VARCHAR(64)：Provider adapter 标识，例如 stub/replay 或 openai/compatible；仅记录脱敏标识",
    )
    requested_model: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：请求模型标识，零模型阶段为空",
    )
    actual_model: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：实际模型标识，禁止伪造医学 Provider",
    )
    prompt_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Prompt 资产键，零模型阶段为空",
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：Prompt 版本，零模型阶段为空",
    )
    prompt_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：Prompt 摘要，零模型阶段为空",
    )
    rendered_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：渲染请求摘要，零模型阶段为空",
    )
    schema_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="VARCHAR(128)：Provider schema 键，零模型阶段为空",
    )
    schema_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：schema 摘要，零模型阶段为空",
    )
    requested_language: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="VARCHAR(32)：请求语言，零模型阶段为空",
    )
    actual_language: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="VARCHAR(32)：实际语言，禁止静默回退",
    )
    image_ordered_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：有序图像集合摘要，零模型阶段为空",
    )
    receipt_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON：Provider receipt 元数据，不含 secret/signed URL",
    )
    raw_output_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：原始输出摘要，不保存 raw 医学输出",
    )
    parsed_output_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="CHAR(64)：解析输出摘要，零模型阶段为空",
    )
    finish_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：Provider finish reason，零模型阶段为空",
    )
    input_tokens: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="BIGINT：输入 token 数，零模型阶段为空",
    )
    output_tokens: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="BIGINT：输出 token 数，零模型阶段为空",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="BIGINT：调用延迟毫秒，零模型阶段为空",
    )
    retry_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="INT：逻辑节点重试序号",
    )
    fallback_used: Mapped[str] = mapped_column(
        String(8), nullable=False, default="no",
        comment="VARCHAR(8)：连接池 fallback 标志 yes/no，仅用于工程审计，不进入医学比较",
    )
    error_class: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="VARCHAR(64)：endpoint_timeout/network_unreachable/tls_failure/provider_auth/model_invalid/schema_invalid/rate_limited/provider_unavailable 等技术错误分类",
    )
