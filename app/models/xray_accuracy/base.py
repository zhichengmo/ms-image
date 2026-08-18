"""SQLAlchemy foundations for the validation-only XRay run contract.

These models intentionally have no foreign keys.  Relationships are opaque
IDs and are checked by the service layer so the contract remains portable
across the existing databases.  No migration is created in this phase.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.async_db import BaseModel


class XRayTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="TIMESTAMP：记录创建时间（UTC），用于不可变审计",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="TIMESTAMP：记录更新时间（UTC），仅技术状态可更新",
    )


class XRayBaseModel(XRayTimestampMixin, BaseModel):
    __abstract__ = True
