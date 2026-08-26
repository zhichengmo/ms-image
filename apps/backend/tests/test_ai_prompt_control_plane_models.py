"""DDL-level model constraints for the Phase A-C control plane.

The checks use SQLAlchemy metadata only.  No database is created or contacted.
"""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects import mysql

from apps.backend.models.ai_api_connection import AIAPIConnection
from apps.backend.models.ai_call import AICall
from apps.backend.models.ai_call_attempt import AICallAttempt
from apps.backend.models.ai_config_record import AIConfigRecord
from apps.backend.models.ai_control_audit_record import AIControlAuditRecord
from apps.backend.models.ai_model_pool import AIModelPool
from apps.backend.models.ai_prompt_template import AIPromptTemplate


CONTROL_PLANE_MODELS = (
    AIPromptTemplate,
    AIAPIConnection,
    AIModelPool,
    AIControlAuditRecord,
)
RUNTIME_RECORD_MODELS = (AICall, AICallAttempt)


def test_new_control_plane_tables_use_opaque_single_column_ids_without_fk_enum_or_tenant() -> None:
    for model in CONTROL_PLANE_MODELS:
        table = model.__table__
        primary_key_columns = list(table.primary_key.columns)
        assert [column.name for column in primary_key_columns] == ["id"]
        assert isinstance(primary_key_columns[0].type, String)
        assert primary_key_columns[0].type.length == 64
        assert primary_key_columns[0].nullable is False
        assert "tenant_id" not in table.c
        assert not table.foreign_keys
        assert not any(isinstance(item, ForeignKeyConstraint) for item in table.constraints)
        assert not any(
            isinstance(column.type, (SAEnum, mysql.ENUM)) for column in table.columns
        )


def test_new_control_plane_columns_have_typed_chinese_comments() -> None:
    for model in CONTROL_PLANE_MODELS:
        for column in model.__table__.columns:
            assert column.comment, f"{model.__tablename__}.{column.name} is missing a comment"
            assert ":" in column.comment or "：" in column.comment
            assert any("\u4e00" <= char <= "\u9fff" for char in column.comment)


def test_audit_idempotency_unique_constraint_is_exact() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in AIControlAuditRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("request_id", "resource_type", "action_type") in unique_column_sets


def test_activation_slot_keeps_v1_compatible_storage_width_while_v2_writes_hashes() -> None:
    activation_slot = AIConfigRecord.__table__.c.activation_slot
    assert isinstance(activation_slot.type, String)
    assert activation_slot.type.length == 320
    assert activation_slot.nullable is True


def test_runtime_call_and_attempt_models_use_opaque_ids_without_fk_enum_or_tenant() -> None:
    for model in RUNTIME_RECORD_MODELS:
        table = model.__table__
        primary_key_columns = list(table.primary_key.columns)
        assert [column.name for column in primary_key_columns] == ["id"]
        assert isinstance(primary_key_columns[0].type, String)
        assert primary_key_columns[0].type.length == 64
        assert primary_key_columns[0].nullable is False
        assert "tenant_id" not in table.c
        assert not table.foreign_keys
        assert not any(isinstance(item, ForeignKeyConstraint) for item in table.constraints)
        assert not any(
            isinstance(column.type, (SAEnum, mysql.ENUM)) for column in table.columns
        )
        for column in table.columns:
            assert column.comment, f"{model.__tablename__}.{column.name} is missing a comment"


def test_attempt_unique_constraints_are_exact_and_status_is_string() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in AICallAttempt.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("ai_call_id", "attempt_no") in unique_column_sets
    assert ("provider_idempotency_key",) in unique_column_sets
    assert ("physical_attempt_key",) in unique_column_sets
    assert isinstance(AICallAttempt.__table__.c.status.type, String)
    assert AICall.__table__.c.attempt_count.nullable is False
