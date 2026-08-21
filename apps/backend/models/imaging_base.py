from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, func
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.core.async_db import BaseModel


def new_opaque_id() -> str:
    return uuid4().hex


class ImagingRecordBase(BaseModel):
    """Shared columns for target imaging records; database access still uses DalBase."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=new_opaque_id,
        comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=func.utc_timestamp(6),
        comment="DATETIME(6): 记录创建时间，UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=func.utc_timestamp(6),
        onupdate=func.utc_timestamp(6),
        comment="DATETIME(6): 记录最后更新时间，UTC",
    )


__all__ = ["ImagingRecordBase", "new_opaque_id"]
