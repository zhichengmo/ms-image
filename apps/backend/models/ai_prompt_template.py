from datetime import datetime

from sqlalchemy import BigInteger, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import CHAR, DATETIME, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class AIPromptTemplate(ImagingRecordBase):
    """One immutable-version complete Prompt body; draft rows are the only editable rows."""

    __tablename__ = "ai_prompt_template"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_template_key_version"),
        Index("ix_ai_prompt_template_key_status_created", "prompt_key", "status", "created_at"),
        Index("ix_ai_prompt_template_content_sha256", "content_sha256"),
    )

    prompt_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 稳定 Prompt 业务键"
    )
    version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): Prompt 不可变版本"
    )
    name: Mapped[str] = mapped_column(
        String(160), nullable=False, comment="VARCHAR(160): Prompt 中文显示名称"
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: Prompt 用途说明"
    )
    language: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="VARCHAR(16): Prompt 语言，首期候选 zh-CN"
    )
    content: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="MEDIUMTEXT: 完整 Prompt 正文，唯一正文事实"
    )
    variables_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="JSON: prompt-variables.v1 允许变量合同"
    )
    content_sha256: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="CHAR(64): 规范化 Prompt 正文 SHA256"
    )
    message_contract_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: prompt-message-contract.v1 多消息冻结合同，NULL 表示旧单正文兼容",
    )
    source_receipt_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON|NULL: prompt-source-receipt.v1 外部来源导入回执，不含凭证或正文副本",
    )
    source_receipt_sha256: Mapped[str | None] = mapped_column(
        CHAR(64), nullable=True,
        comment="CHAR(64)|NULL: 外部 Prompt 来源回执规范化 SHA256",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default=text("'draft'"),
        comment="VARCHAR(32): Prompt 状态，候选 draft/validated/retired",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0"),
        comment="BIGINT: Prompt 状态与草稿更新 CAS 版本",
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Prompt 验证通过时间"
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Prompt 退役时间"
    )
    created_by_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 创建者可信身份 ID"
    )
    updated_by_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 最近操作者可信身份 ID"
    )


__all__ = ["AIPromptTemplate"]
