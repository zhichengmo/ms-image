from typing import Any

from sqlalchemy import Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class PetProfileHistory(ImagingRecordBase):
    __tablename__ = "pet_profile_history"
    __table_args__ = (
        Index(
            "ix_pet_profile_history_profile_created",
            "pet_profile_id",
            "created_at",
        ),
        Index(
            "ix_pet_profile_history_operator_created",
            "operator_id",
            "created_at",
        ),
        {"comment": "宠物档案变更历史表：记录创建、更新、归档和恢复操作"},
    )

    pet_profile_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): 宠物档案 opaque ID，不声明数据库外键",
    )
    data_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="profile",
        comment="VARCHAR(32): 历史数据类型 profile宠物档案",
    )
    field_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="VARCHAR(64): 变更字段名；星号表示整份档案事件",
    )
    old_value_json: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 变更前的 JSON 安全值"
    )
    new_value_json: Mapped[Any | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 变更后的 JSON 安全值"
    )
    operation_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 操作类型 create创建/update更新/archive归档/restore恢复",
    )
    operator_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 操作人或服务 opaque ID"
    )
    snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="JSON|NULL: 变更完成后的宠物档案安全快照"
    )
    remark: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏后的变更备注"
    )


__all__ = ["PetProfileHistory"]
