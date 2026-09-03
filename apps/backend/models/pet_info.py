from decimal import Decimal

from sqlalchemy import Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class PetInfo(ImagingRecordBase):
    """Cat/dog breed catalog migrated from the legacy ``pets_info`` domain."""

    __tablename__ = "pet_info"
    __table_args__ = (
        UniqueConstraint("species", "full_name", name="uq_pet_info_species_full_name"),
        Index("ix_pet_info_species_status_letter", "species", "status", "first_letter"),
        Index("ix_pet_info_species_name", "species", "name"),
        {"comment": "宠物品种资料目录：保存猫狗品种检索与展示资料"},
    )

    species: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="VARCHAR(32): 品种所属物种 cat猫/dog狗"
    )
    full_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 品种完整中文名称"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="VARCHAR(128): 品种常用名称"
    )
    english_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 品种英文名称"
    )
    alias: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="VARCHAR(255)|NULL: 品种别名"
    )
    origin_place: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 品种原产地"
    )
    figure: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 体型描述"
    )
    reference_weight_kg: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 3),
        nullable=True,
        comment="DECIMAL(8,3)|NULL: 品种参考体重，单位千克",
    )
    fur_length: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="VARCHAR(64)|NULL: 毛发长度描述"
    )
    features: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 品种外观与性格特征"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 品种简介与档案说明"
    )
    image_keys_json: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON|NULL: 品种图片对象存储 key 列表，不保存签名 URL",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 品种资料来源页面 URL"
    )
    first_letter: Mapped[str] = mapped_column(
        String(1), nullable=False, comment="VARCHAR(1): 品种名称首字母 A-Z/#"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="VARCHAR(32): 目录状态 active展示/hidden隐藏/retired停用",
    )


__all__ = ["PetInfo"]
