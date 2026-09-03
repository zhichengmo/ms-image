"""Create pet profile, profile history, and breed catalog tables.

Revision ID: 20260901_01
Revises: 20260831_01
Create Date: 2026-09-01

The legacy ``vet_platform`` tables are intentionally not copied verbatim.  The
new tables use opaque string primary keys, string status fields, no foreign
keys, no database enums, and no tenant partition column.  Data import is an
independent operational step so this schema revision remains environment-safe.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260901_01"
down_revision = "20260831_01"
branch_labels = None
depends_on = None


UTC_NOW_6 = sa.text("CURRENT_TIMESTAMP(6)")
ACTIVE = sa.text("'active'")
UNKNOWN = sa.text("'unknown'")
ZERO = sa.text("0")


def upgrade() -> None:
    op.create_table(
        "pet_info",
        sa.Column(
            "species",
            sa.String(length=32),
            nullable=False,
            comment="VARCHAR(32): 品种所属物种 cat猫/dog狗",
        ),
        sa.Column(
            "full_name",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 品种完整中文名称",
        ),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 品种常用名称",
        ),
        sa.Column(
            "english_name",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: 品种英文名称",
        ),
        sa.Column(
            "alias",
            sa.String(length=255),
            nullable=True,
            comment="VARCHAR(255)|NULL: 品种别名",
        ),
        sa.Column(
            "origin_place",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: 品种原产地",
        ),
        sa.Column(
            "figure",
            sa.String(length=64),
            nullable=True,
            comment="VARCHAR(64)|NULL: 体型描述",
        ),
        sa.Column(
            "reference_weight_kg",
            mysql.DECIMAL(precision=8, scale=3),
            nullable=True,
            comment="DECIMAL(8,3)|NULL: 品种参考体重，单位千克",
        ),
        sa.Column(
            "fur_length",
            sa.String(length=64),
            nullable=True,
            comment="VARCHAR(64)|NULL: 毛发长度描述",
        ),
        sa.Column(
            "features",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 品种外观与性格特征",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 品种简介与档案说明",
        ),
        sa.Column(
            "image_keys_json",
            sa.JSON(),
            nullable=True,
            comment="JSON|NULL: 品种图片对象存储 key 列表，不保存签名 URL",
        ),
        sa.Column(
            "source_url",
            sa.String(length=500),
            nullable=True,
            comment="VARCHAR(500)|NULL: 品种资料来源页面 URL",
        ),
        sa.Column(
            "first_letter",
            sa.String(length=1),
            nullable=False,
            comment="VARCHAR(1): 品种名称首字母 A-Z/#",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=ACTIVE,
            comment="VARCHAR(32): 目录状态 active展示/hidden隐藏/retired停用",
        ),
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录创建时间，UTC",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录最后更新时间，UTC",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "species",
            "full_name",
            name="uq_pet_info_species_full_name",
        ),
        comment="宠物品种资料目录：保存猫狗品种检索与展示资料",
    )
    op.create_index(
        "ix_pet_info_species_name",
        "pet_info",
        ["species", "name"],
        unique=False,
    )
    op.create_index(
        "ix_pet_info_species_status_letter",
        "pet_info",
        ["species", "status", "first_letter"],
        unique=False,
    )

    op.create_table(
        "pet_profile",
        sa.Column(
            "owner_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 来自可信认证上下文的档案所有者 opaque ID",
        ),
        sa.Column(
            "request_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 创建宠物档案的全局幂等请求 ID",
        ),
        sa.Column(
            "source_system",
            sa.String(length=64),
            nullable=True,
            comment="VARCHAR(64)|NULL: 来源系统标识，例如 vet-platform",
        ),
        sa.Column(
            "source_pet_id",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: 来源系统中的宠物 opaque ID",
        ),
        sa.Column(
            "name",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 宠物名称",
        ),
        sa.Column(
            "species",
            sa.String(length=32),
            nullable=False,
            comment="VARCHAR(32): 宠物物种 cat猫/dog狗/other其他",
        ),
        sa.Column(
            "breed_name",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: 宠物品种名称",
        ),
        sa.Column(
            "sex",
            sa.String(length=32),
            nullable=False,
            server_default=UNKNOWN,
            comment="VARCHAR(32): 生理性别 male公/female母/unknown未知",
        ),
        sa.Column(
            "neuter_status",
            sa.String(length=32),
            nullable=False,
            server_default=UNKNOWN,
            comment="VARCHAR(32): 绝育状态 intact未绝育/neutered已绝育/unknown未知",
        ),
        sa.Column(
            "vaccination_status",
            sa.String(length=32),
            nullable=False,
            server_default=UNKNOWN,
            comment="VARCHAR(32): 疫苗状态 vaccinated已接种/unvaccinated未接种/partial部分接种/unknown未知",
        ),
        sa.Column(
            "birthday",
            sa.Date(),
            nullable=True,
            comment="DATE|NULL: 宠物出生日期",
        ),
        sa.Column(
            "avatar_object_key",
            sa.String(length=512),
            nullable=True,
            comment="VARCHAR(512)|NULL: 宠物头像对象存储 key，不保存签名 URL",
        ),
        sa.Column(
            "weight_kg",
            mysql.DECIMAL(precision=8, scale=3),
            nullable=True,
            comment="DECIMAL(8,3)|NULL: 最近一次体重，单位千克",
        ),
        sa.Column(
            "weight_measured_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: 最近一次体重测量时间，UTC",
        ),
        sa.Column(
            "last_vaccinated_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: 最近一次疫苗接种时间，UTC",
        ),
        sa.Column(
            "last_examined_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: 最近一次检查时间，UTC",
        ),
        sa.Column(
            "diet_notes",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 饮食标准与饮食备注",
        ),
        sa.Column(
            "disease_history",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 已知疾病史",
        ),
        sa.Column(
            "allergy_history",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 已知过敏史",
        ),
        sa.Column(
            "family_history",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 家族病史",
        ),
        sa.Column(
            "care_notes",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 日常护理建议与备注",
        ),
        sa.Column(
            "health_notes",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 健康建议与观察备注",
        ),
        sa.Column(
            "medical_history",
            sa.Text(),
            nullable=True,
            comment="TEXT|NULL: 脱敏后的既往医疗史摘要",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=ACTIVE,
            comment="VARCHAR(32): 档案状态 active有效/archived已归档/deceased已故",
        ),
        sa.Column(
            "state_version",
            sa.BigInteger(),
            nullable=False,
            server_default=ZERO,
            comment="BIGINT: 宠物档案乐观锁版本，成功变更时递增",
        ),
        sa.Column(
            "archived_at",
            mysql.DATETIME(fsp=6),
            nullable=True,
            comment="DATETIME(6)|NULL: 档案归档时间，UTC",
        ),
        sa.Column(
            "archived_by_id",
            sa.String(length=128),
            nullable=True,
            comment="VARCHAR(128)|NULL: 归档操作人 opaque ID",
        ),
        sa.Column(
            "archive_reason",
            sa.String(length=500),
            nullable=True,
            comment="VARCHAR(500)|NULL: 脱敏且稳定的归档原因",
        ),
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录创建时间，UTC",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录最后更新时间，UTC",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_pet_profile_request_id"),
        sa.UniqueConstraint(
            "source_system",
            "source_pet_id",
            name="uq_pet_profile_source_pet",
        ),
        comment="宠物档案表：保存认证主体所属宠物的基础与健康资料",
    )
    op.create_index(
        "ix_pet_profile_owner_name",
        "pet_profile",
        ["owner_id", "name"],
        unique=False,
    )
    op.create_index(
        "ix_pet_profile_owner_status_created",
        "pet_profile",
        ["owner_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "pet_profile_history",
        sa.Column(
            "pet_profile_id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 宠物档案 opaque ID，不声明数据库外键",
        ),
        sa.Column(
            "data_type",
            sa.String(length=32),
            nullable=False,
            comment="VARCHAR(32): 历史数据类型 profile宠物档案",
        ),
        sa.Column(
            "field_name",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 变更字段名；星号表示整份档案事件",
        ),
        sa.Column(
            "old_value_json",
            sa.JSON(),
            nullable=True,
            comment="JSON|NULL: 变更前的 JSON 安全值",
        ),
        sa.Column(
            "new_value_json",
            sa.JSON(),
            nullable=True,
            comment="JSON|NULL: 变更后的 JSON 安全值",
        ),
        sa.Column(
            "operation_type",
            sa.String(length=32),
            nullable=False,
            comment="VARCHAR(32): 操作类型 create创建/update更新/archive归档/restore恢复",
        ),
        sa.Column(
            "operator_id",
            sa.String(length=128),
            nullable=False,
            comment="VARCHAR(128): 操作人或服务 opaque ID",
        ),
        sa.Column(
            "snapshot_json",
            sa.JSON(),
            nullable=True,
            comment="JSON|NULL: 变更完成后的宠物档案安全快照",
        ),
        sa.Column(
            "remark",
            sa.String(length=500),
            nullable=True,
            comment="VARCHAR(500)|NULL: 脱敏后的变更备注",
        ),
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录创建时间，UTC",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=UTC_NOW_6,
            comment="DATETIME(6): 记录最后更新时间，UTC",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="宠物档案变更历史表：记录创建、更新、归档和恢复操作",
    )
    op.create_index(
        "ix_pet_profile_history_operator_created",
        "pet_profile_history",
        ["operator_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_pet_profile_history_profile_created",
        "pet_profile_history",
        ["pet_profile_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pet_profile_history_profile_created",
        table_name="pet_profile_history",
    )
    op.drop_index(
        "ix_pet_profile_history_operator_created",
        table_name="pet_profile_history",
    )
    op.drop_table("pet_profile_history")

    op.drop_index(
        "ix_pet_profile_owner_status_created",
        table_name="pet_profile",
    )
    op.drop_index("ix_pet_profile_owner_name", table_name="pet_profile")
    op.drop_table("pet_profile")

    op.drop_index(
        "ix_pet_info_species_status_letter",
        table_name="pet_info",
    )
    op.drop_index("ix_pet_info_species_name", table_name="pet_info")
    op.drop_table("pet_info")
