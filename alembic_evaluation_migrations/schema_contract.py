"""Frozen R4A Evaluation database schema contract used by both migration chains."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import mysql


EVALUATION_TABLE_NAMES = frozenset(
    {
        "evaluation_job_record",
        "evaluation_outbox_record",
        "evaluation_run_record",
        "evaluation_artifact_record",
    }
)


def _record_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "id",
            sa.String(64),
            primary_key=True,
            nullable=False,
            comment="VARCHAR(64): 服务端生成的记录 opaque ID，单列主键",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            comment="DATETIME(6): 记录创建时间，UTC",
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            comment="DATETIME(6): 记录最后更新时间，UTC",
        ),
    ]


def build_evaluation_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    sa.Table(
        "evaluation_job_record",
        metadata,
        sa.Column("requester_id", sa.String(128), nullable=False, comment="VARCHAR(128): Evaluation/ControlPlane requester ID"),
        sa.Column("business_key", sa.String(200), nullable=False, comment="VARCHAR(200): Job 幂等键"),
        sa.Column("request_payload_sha256", sa.String(64), nullable=False, comment="CHAR(64): 规范化 Evaluation Job 创建请求 SHA256，用于完整 payload 幂等比对"),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): 冻结 dataset 指纹"),
        sa.Column("gold_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): 冻结 Gold 指纹"),
        sa.Column("scorer_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): scorer 指纹"),
        sa.Column("experiment_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): experiment 指纹"),
        sa.Column("case_split_json", mysql.JSON(), nullable=False, comment="JSON: case split/failure-bank/holdout 合同"),
        sa.Column("denominator_contract_json", mysql.JSON(), nullable=False, comment="JSON: 医学条件与端到端分母合同"),
        sa.Column("input_manifest_artifact_id", sa.String(64), nullable=False, comment="VARCHAR(64): 输入 manifest Artifact ID"),
        sa.Column("sanitization_artifact_id", sa.String(64), nullable=False, comment="VARCHAR(64): sanitization Artifact ID"),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'queued'"), comment="VARCHAR(32): queued/running/retry_wait/completed/failed/cancelled/dead_letter"),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="BIGINT: Job CAS 版本"),
        sa.Column("lease_owner_id", sa.String(128), nullable=True, comment="VARCHAR(128)|NULL: Evaluation Worker lease owner"),
        sa.Column("lease_generation", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="BIGINT: Evaluation Worker lease 世代，防止旧 Worker 回写"),
        sa.Column("lease_expires_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Evaluation Worker lease 到期时间，UTC"),
        sa.Column("heartbeat_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Evaluation Worker 最近心跳时间，UTC"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="INT: Evaluation Job 已安排的重试次数"),
        sa.Column("next_retry_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下一次可执行时间，UTC"),
        sa.Column("result_artifact_id", sa.String(64), nullable=True, comment="VARCHAR(64)|NULL: metric_summary Artifact ID"),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 首次开始时间，UTC"),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 终态完成时间，UTC"),
        sa.Column("error_code", sa.String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"),
        sa.Column("error_message", sa.String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"),
        *_record_columns(),
        sa.UniqueConstraint("business_key", name="uq_evaluation_job_business_key"),
        sa.Index("ix_evaluation_job_status", "status", "created_at"),
        sa.Index("ix_evaluation_job_lease", "status", "lease_expires_at"),
        sa.Index("ix_evaluation_job_retry", "status", "next_retry_at", "created_at"),
    )
    sa.Table(
        "evaluation_outbox_record",
        metadata,
        sa.Column("job_id", sa.String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID"),
        sa.Column("aggregate_version", sa.BigInteger(), nullable=False, comment="BIGINT: Job 版本"),
        sa.Column("event_key", sa.String(160), nullable=False, comment="VARCHAR(160): 事件幂等键"),
        sa.Column("event_type", sa.String(48), nullable=False, comment="VARCHAR(48): execute_evaluation"),
        sa.Column("destination_key", sa.String(128), nullable=False, comment="VARCHAR(128): Evaluation queue 配置键"),
        sa.Column("trace_id", sa.String(128), nullable=False, comment="VARCHAR(128): 跨边界 trace ID"),
        sa.Column("message_version", sa.String(32), nullable=False, comment="VARCHAR(32): Evaluation 消息合同版本"),
        sa.Column("message_json", mysql.JSON(), nullable=False, comment="JSON: opaque ID/version/trace"),
        sa.Column("message_sha256", sa.String(64), nullable=False, comment="CHAR(64): 消息摘要"),
        sa.Column("publish_status", sa.String(32), nullable=False, server_default=sa.text("'pending'"), comment="VARCHAR(32): pending/publishing/published/retry_wait/dead_letter/cancelled"),
        sa.Column("relay_owner_id", sa.String(128), nullable=True, comment="VARCHAR(128)|NULL: Relay lease owner"),
        sa.Column("relay_lease_expires_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Relay lease 到期"),
        sa.Column("publish_attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="INT: 发布尝试次数"),
        sa.Column("next_retry_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: 下次重试"),
        sa.Column("broker_message_id", sa.String(128), nullable=True, comment="VARCHAR(128)|NULL: Broker message ID"),
        sa.Column("published_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: publisher confirm 时间"),
        sa.Column("error_code", sa.String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"),
        sa.Column("error_message", sa.String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"),
        *_record_columns(),
        sa.UniqueConstraint("event_key", name="uq_evaluation_outbox_event_key"),
        sa.Index("ix_evaluation_outbox_status", "publish_status", "next_retry_at", "created_at"),
        sa.Index("ix_evaluation_outbox_lease", "publish_status", "relay_lease_expires_at"),
        sa.Index("ix_evaluation_outbox_job", "job_id", "created_at"),
    )
    sa.Table(
        "evaluation_run_record",
        metadata,
        sa.Column("job_id", sa.String(64), nullable=False, comment="VARCHAR(64): EvaluationJob ID"),
        sa.Column("run_no", sa.Integer(), nullable=False, comment="INT: Job 内 Run 序号"),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): dataset 指纹"),
        sa.Column("gold_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): Gold 指纹"),
        sa.Column("scorer_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): scorer 指纹"),
        sa.Column("experiment_fingerprint", sa.String(64), nullable=False, comment="CHAR(64): experiment 指纹"),
        sa.Column("case_split_sha256", sa.String(64), nullable=False, comment="CHAR(64): 冻结 case split 合同摘要"),
        sa.Column("denominator_contract_sha256", sa.String(64), nullable=False, comment="CHAR(64): 冻结双分母合同摘要"),
        sa.Column("input_manifest_artifact_sha256", sa.String(64), nullable=False, comment="CHAR(64): 输入 manifest Artifact 摘要"),
        sa.Column("sanitization_artifact_sha256", sa.String(64), nullable=False, comment="CHAR(64): 脱敏证明 Artifact 摘要"),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'started'"), comment="VARCHAR(32): started/succeeded/failed/cancelled/unknown"),
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="BIGINT: Run CAS 版本"),
        sa.Column("summary_json", mysql.JSON(), nullable=True, comment="JSON|NULL: 结果摘要"),
        sa.Column("error_code", sa.String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"),
        sa.Column("error_message", sa.String(500), nullable=True, comment="VARCHAR(500)|NULL: 脱敏错误摘要"),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False, comment="DATETIME(6): Run 开始时间，UTC"),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=True, comment="DATETIME(6)|NULL: Run 完成时间，UTC"),
        *_record_columns(),
        sa.UniqueConstraint("job_id", "run_no", name="uq_evaluation_run_job_no"),
        sa.Index("ix_evaluation_run_status", "job_id", "status"),
    )
    sa.Table(
        "evaluation_artifact_record",
        metadata,
        sa.Column("job_id", sa.String(64), nullable=False, comment="VARCHAR(64): EvaluationJob 查询投影"),
        sa.Column("run_id", sa.String(64), nullable=True, comment="VARCHAR(64)|NULL: EvaluationRun 查询投影"),
        sa.Column("artifact_kind", sa.String(64), nullable=False, comment="VARCHAR(64): input_manifest/sanitization/case_result/failure_summary/metric_summary/paired_ab_summary"),
        sa.Column("object_ref_json", mysql.JSON(), nullable=False, comment="JSON: 完整 ObjectRef"),
        sa.Column("content_sha256", sa.String(64), nullable=False, comment="CHAR(64): Artifact 内容摘要"),
        sa.Column("provenance_json", mysql.JSON(), nullable=False, comment="JSON: producer/sanitization/visibility provenance"),
        sa.Column("visibility", sa.String(32), nullable=False, comment="VARCHAR(32): evaluation_internal/approval_only"),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'ready'"), comment="VARCHAR(32): ready/failed/void"),
        sa.Column("error_code", sa.String(80), nullable=True, comment="VARCHAR(80)|NULL: 稳定错误码"),
        *_record_columns(),
        sa.UniqueConstraint("job_id", "run_id", "artifact_kind", name="uq_evaluation_artifact_run_kind"),
        sa.Index("ix_evaluation_artifact_job_run", "job_id", "run_id"),
        sa.Index("ix_evaluation_artifact_kind", "artifact_kind", "created_at"),
    )
    return metadata


def create_evaluation_tables(operations: Any) -> None:
    metadata = build_evaluation_metadata()
    for table in metadata.sorted_tables:
        columns = [column._copy() for column in table.columns]
        uniques = [
            sa.UniqueConstraint(
                *(column.name for column in constraint.columns),
                name=constraint.name,
            )
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        ]
        operations.create_table(table.name, *columns, *uniques)
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            operations.create_index(
                index.name,
                table.name,
                [column.name for column in index.columns],
                unique=index.unique,
            )


def drop_evaluation_tables(operations: Any) -> None:
    for table_name in (
        "evaluation_artifact_record",
        "evaluation_run_record",
        "evaluation_outbox_record",
        "evaluation_job_record",
    ):
        operations.drop_table(table_name)


def _type_signature(value: sa.types.TypeEngine[Any]) -> tuple[Any, ...]:
    if isinstance(value, sa.BigInteger):
        return ("bigint",)
    if isinstance(value, sa.Integer):
        return ("integer",)
    if isinstance(value, sa.String):
        return ("varchar", value.length)
    if isinstance(value, mysql.DATETIME):
        return ("datetime", value.fsp)
    if isinstance(value, sa.JSON):
        return ("json",)
    return (value.__class__.__name__.lower(),)


def _normalize_default(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(getattr(value, "arg", value)).strip().lower()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return normalized


def _named_columns(items: Iterable[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    return {
        str(item["name"]): tuple(str(value) for value in item["column_names"])
        for item in items
        if item.get("name")
    }


def validate_evaluation_schema(bind: Any) -> None:
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names()) & EVALUATION_TABLE_NAMES
    if existing != EVALUATION_TABLE_NAMES:
        raise RuntimeError("evaluation_schema_adoption_invalid")

    metadata = build_evaluation_metadata()
    for table_name in sorted(EVALUATION_TABLE_NAMES):
        table = metadata.tables[table_name]
        expected_columns = list(table.columns)
        actual_columns = inspector.get_columns(table_name)
        if [item["name"] for item in actual_columns] != [
            column.name for column in expected_columns
        ]:
            raise RuntimeError("evaluation_schema_adoption_invalid")
        for expected, actual in zip(expected_columns, actual_columns, strict=True):
            if (
                _type_signature(expected.type) != _type_signature(actual["type"])
                or expected.nullable != actual["nullable"]
                or _normalize_default(expected.server_default)
                != _normalize_default(actual.get("default"))
                or expected.comment != actual.get("comment")
            ):
                raise RuntimeError("evaluation_schema_adoption_invalid")

        expected_pk = tuple(column.name for column in table.primary_key.columns)
        actual_pk = tuple(inspector.get_pk_constraint(table_name)["constrained_columns"])
        if expected_pk != actual_pk:
            raise RuntimeError("evaluation_schema_adoption_invalid")

        # The project contract deliberately has no database foreign keys or
        # CHECK constraints.  Adoption must reject extra constraints instead
        # of silently accepting a schema that is only column-compatible.
        if inspector.get_foreign_keys(table_name) or inspector.get_check_constraints(
            table_name
        ):
            raise RuntimeError("evaluation_schema_adoption_invalid")

        expected_unique = {
            str(constraint.name): tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint) and constraint.name
        }
        actual_unique = _named_columns(inspector.get_unique_constraints(table_name))
        if expected_unique != actual_unique:
            raise RuntimeError("evaluation_schema_adoption_invalid")

        expected_indexes = {
            str(index.name): tuple(column.name for column in index.columns)
            for index in table.indexes
            if index.name and not index.unique
        }
        actual_indexes = {
            name: columns
            for name, columns in _named_columns(inspector.get_indexes(table_name)).items()
            if name not in actual_unique
        }
        if expected_indexes != actual_indexes:
            raise RuntimeError("evaluation_schema_adoption_invalid")


__all__ = [
    "EVALUATION_TABLE_NAMES",
    "build_evaluation_metadata",
    "create_evaluation_tables",
    "drop_evaluation_tables",
    "validate_evaluation_schema",
]
