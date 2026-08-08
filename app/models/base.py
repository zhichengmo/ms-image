from sqlalchemy import DateTime, func, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.async_db import BaseModel


class BaseTimeModel(BaseModel):
    """基础时间模型"""
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")