from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.models.imaging_base import ImagingRecordBase


class PetProfile(ImagingRecordBase):
    __tablename__ = "pet_profile"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_pet_profile_request_id"),
        UniqueConstraint(
            "source_system",
            "source_pet_id",
            name="uq_pet_profile_source_pet",
        ),
        Index(
            "ix_pet_profile_owner_status_created", "owner_id", "status", "created_at"
        ),
        Index("ix_pet_profile_owner_name", "owner_id", "name"),
        {"comment": "宠物档案表：保存认证主体所属宠物的基础与健康资料"},
    )

    owner_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 来自可信认证上下文的档案所有者 opaque ID",
    )
    request_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="VARCHAR(128): 创建宠物档案的全局幂等请求 ID",
    )
    source_system: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="VARCHAR(64)|NULL: 来源系统标识，例如 vet-platform",
    )
    source_pet_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="VARCHAR(128)|NULL: 来源系统中的宠物 opaque ID",
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="VARCHAR(64): 宠物名称"
    )
    species: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="VARCHAR(32): 宠物物种 cat猫/dog狗/other其他",
    )
    breed_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 宠物品种名称"
    )
    sex: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="VARCHAR(32): 生理性别 male公/female母/unknown未知",
    )
    neuter_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="VARCHAR(32): 绝育状态 intact未绝育/neutered已绝育/unknown未知",
    )
    vaccination_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="VARCHAR(32): 疫苗状态 vaccinated已接种/unvaccinated未接种/partial部分接种/unknown未知",
    )
    birthday: Mapped[date | None] = mapped_column(
        nullable=True, comment="DATE|NULL: 宠物出生日期"
    )
    avatar_object_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="VARCHAR(512)|NULL: 宠物头像对象存储 key，不保存签名 URL",
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 3),
        nullable=True,
        comment="DECIMAL(8,3)|NULL: 最近一次体重，单位千克",
    )
    weight_measured_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 最近一次体重测量时间，UTC",
    )
    last_vaccinated_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 最近一次疫苗接种时间，UTC",
    )
    last_examined_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6),
        nullable=True,
        comment="DATETIME(6)|NULL: 最近一次检查时间，UTC",
    )
    diet_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 饮食标准与饮食备注"
    )
    disease_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 已知疾病史"
    )
    allergy_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 已知过敏史"
    )
    family_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 家族病史"
    )
    care_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 日常护理建议与备注"
    )
    health_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 健康建议与观察备注"
    )
    medical_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="TEXT|NULL: 脱敏后的既往医疗史摘要"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="VARCHAR(32): 档案状态 active有效/archived已归档/deceased已故",
    )
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="BIGINT: 宠物档案乐观锁版本，成功变更时递增",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 档案归档时间，UTC"
    )
    archived_by_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="VARCHAR(128)|NULL: 归档操作人 opaque ID"
    )
    archive_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏且稳定的归档原因"
    )


__all__ = ["PetProfile"]
