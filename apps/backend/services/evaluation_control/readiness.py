"""Dependency readiness for the isolated Evaluation Control application."""

from __future__ import annotations

import asyncio

from sqlalchemy import inspect, text

from alembic_evaluation_migrations.schema_contract import EVALUATION_TABLE_NAMES
from apps.backend.core.async_db import evaluation_async_engine
from apps.backend.core.config import settings
from apps.backend.core.dependencies import control_plane_jwt_readiness
from apps.backend.schemas.evaluation import (
    EvaluationControlReadinessComponent,
    EvaluationControlReadinessComponents,
    EvaluationControlReadinessResponse,
)


EVALUATION_ALEMBIC_HEAD = "20260831_eval_01"


async def _database_and_schema_ready() -> tuple[
    EvaluationControlReadinessComponent,
    EvaluationControlReadinessComponent,
]:
    try:
        async with evaluation_async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            database_name = (await connection.execute(text("SELECT DATABASE()"))).scalar_one()
            expected_name = settings.MYSQL_EVALUATION_DB.strip()
            if not expected_name or database_name != expected_name or database_name == settings.MYSQL_DB.strip():
                raise RuntimeError("evaluation_database_identity_invalid")

            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
            evaluation_tables = tables & EVALUATION_TABLE_NAMES
            if evaluation_tables != EVALUATION_TABLE_NAMES or "alembic_version" not in tables:
                return (
                    EvaluationControlReadinessComponent(required=True, ready=True, state="ready", error=None),
                    EvaluationControlReadinessComponent(
                        required=True,
                        ready=False,
                        state="unavailable",
                        error="evaluation_schema_unavailable",
                    ),
                )
            revisions = tuple(
                (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars()
            )
            if revisions != (EVALUATION_ALEMBIC_HEAD,):
                return (
                    EvaluationControlReadinessComponent(required=True, ready=True, state="ready", error=None),
                    EvaluationControlReadinessComponent(
                        required=True,
                        ready=False,
                        state="mismatch",
                        error="evaluation_schema_revision_mismatch",
                    ),
                )
    except Exception:
        return (
            EvaluationControlReadinessComponent(
                required=True,
                ready=False,
                state="unavailable",
                error="evaluation_database_unavailable",
            ),
            EvaluationControlReadinessComponent(
                required=True,
                ready=False,
                state="unavailable",
                error="evaluation_schema_unavailable",
            ),
        )
    return (
        EvaluationControlReadinessComponent(required=True, ready=True, state="ready", error=None),
        EvaluationControlReadinessComponent(required=True, ready=True, state="ready", error=None),
    )


async def build_evaluation_control_readiness() -> EvaluationControlReadinessResponse:
    try:
        database, schema_revision = await asyncio.wait_for(
            _database_and_schema_ready(),
            timeout=settings.READINESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        database = EvaluationControlReadinessComponent(
            required=True,
            ready=False,
            state="timeout",
            error="evaluation_database_unavailable",
        )
        schema_revision = EvaluationControlReadinessComponent(
            required=True,
            ready=False,
            state="unavailable",
            error="evaluation_schema_unavailable",
        )

    jwt_ready, _ = control_plane_jwt_readiness()
    jwt_ready = jwt_ready and bool(
        settings.EVALUATION_READ_SCOPE.strip()
        and settings.EVALUATION_WRITE_SCOPE.strip()
    )
    control_plane_jwt = EvaluationControlReadinessComponent(
        required=True,
        ready=jwt_ready,
        state="ready" if jwt_ready else "misconfigured",
        error=None if jwt_ready else "control_plane_jwt_misconfigured",
    )
    ready = database.ready and schema_revision.ready and control_plane_jwt.ready
    return EvaluationControlReadinessResponse(
        ready=ready,
        readiness_scope="evaluation_control",
        components=EvaluationControlReadinessComponents(
            evaluation_database=database,
            schema_revision=schema_revision,
            control_plane_jwt=control_plane_jwt,
        ),
    )


__all__ = ["EVALUATION_ALEMBIC_HEAD", "build_evaluation_control_readiness"]
