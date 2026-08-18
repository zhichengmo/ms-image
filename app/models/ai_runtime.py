"""Legacy-compatible AI governance tables used by the XRay adapter.

The table names and lookup semantics mirror ``vet-platform`` (``ai_config``
→ ``gpt_config_item``/``ai_prompt_template`` → ``ai_model_pool`` →
``ai_api_connection``).  IDs are opaque strings in this service and logical
references are checked by the Service layer; no database foreign keys are
declared.  Secrets are represented by ``secret_ref`` and never stored here.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.async_db import BaseModel


class AiConfig(BaseModel):
    __tablename__ = "ai_config"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="INT：旧链配置主键")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="DATETIME：创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="DATETIME：更新时间")
    items: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="VARCHAR(1000)：旧链配置项 ID 列表，使用短横线分隔")
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="VARCHAR(50)：配置版本号")
    is_del: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="SMALLINT：删除状态，0 正常 1 删除")


class GptConfigItem(BaseModel):
    __tablename__ = "gpt_config_item"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="INT：旧链配置项主键")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="DATETIME：创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="DATETIME：更新时间")
    config_type: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, comment="SMALLINT：2 模型 3 输出格式 5 参数")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="TEXT：配置内容")
    is_del: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="SMALLINT：删除状态")
    note: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="VARCHAR(50)：备注")
    human_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, comment="FLOAT：旧链路人工权重")


class AiPromptTemplate(BaseModel):
    __tablename__ = "ai_prompt_template"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="INT：旧链 Prompt 模板主键")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="DATETIME：创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="DATETIME：更新时间")
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="VARCHAR(100)：模板名称")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="TEXT：中文 Prompt 内容")
    content_en: Mapped[str | None] = mapped_column(Text, nullable=True, comment="TEXT：英文 Prompt 内容")
    module_category: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="VARCHAR(50)：模块分类")
    human_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, comment="FLOAT：旧链路人工权重")
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="BOOLEAN：Prompt 工程师确认状态")
    is_del: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="SMALLINT：删除状态")


class AiModelPool(BaseModel):
    __tablename__ = "ai_model_pool"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="INT：旧链模型池主键")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="DATETIME：创建时间")
    model_pool: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="VARCHAR(100)：有序 API 连接 ID 列表，使用短横线分隔")
    note: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="VARCHAR(100)：备注")


class AiApiConnection(BaseModel):
    __tablename__ = "ai_api_connection"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="INT：旧链 API 连接主键")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="DATETIME：创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="DATETIME：更新时间")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="VARCHAR(500)：OpenAI-compatible API 基础地址")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="VARCHAR(255)：旧链 API 密钥；仅允许 Secret Manager 同步，禁止日志输出")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="VARCHAR(100)：模型名称")
    connection_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="VARCHAR(100)：连接名称")
    human_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, comment="FLOAT：人工权重")
    is_del: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="SMALLINT：删除状态，0 正常 1 删除")


__all__ = ["AiConfig", "GptConfigItem", "AiPromptTemplate", "AiModelPool", "AiApiConnection"]
