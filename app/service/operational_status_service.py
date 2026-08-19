"""Aggregate non-sensitive operational facts from online and Evaluation DBs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai_call import AICallDal
from app.crud.evaluation import EvaluationJobDal, EvaluationOutboxDal, EvaluationRunDal
from app.crud.outbox import OutboxDal
from app.crud.report import ReportDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.schemas.operations import (
    CallOperationalStatus,
    EvaluationMetricOperationalStatus,
    ExecutionOperationalStatus,
    OperationalStatusResponse,
    QueueOperationalStatus,
    ReportOperationalStatus,
)


class OperationalStatusService:
    def __init__(self, *, online_db: AsyncSession, evaluation_db: AsyncSession):
        self.online_outbox_dal = OutboxDal(online_db)
        self.stage_dal = StageCheckpointDal(online_db)
        self.call_dal = AICallDal(online_db)
        self.report_dal = ReportDal(online_db)
        self.evaluation_job_dal = EvaluationJobDal(evaluation_db)
        self.evaluation_outbox_dal = EvaluationOutboxDal(evaluation_db)
        self.evaluation_run_dal = EvaluationRunDal(evaluation_db)

    async def snapshot(
        self, *, now: datetime | None = None, run_limit: int = 500
    ) -> OperationalStatusResponse:
        captured_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
        online_outbox = await self.online_outbox_dal.operational_snapshot(
            now=captured_at
        )
        stages = await self.stage_dal.operational_snapshot(now=captured_at)
        calls = await self.call_dal.operational_snapshot()
        reports = await self.report_dal.operational_snapshot()
        evaluation_jobs = await self.evaluation_job_dal.operational_snapshot(
            now=captured_at
        )
        evaluation_outbox = await self.evaluation_outbox_dal.operational_snapshot(
            now=captured_at
        )
        runs = await self.evaluation_run_dal.list_recent(limit=run_limit)
        metrics = self._aggregate_evaluation_metrics(runs)
        metrics["artifact_drift_failures"] = evaluation_jobs["artifact_drift_failures"]
        return OperationalStatusResponse(
            captured_at=captured_at,
            online_outbox=self._queue_status(online_outbox, captured_at),
            stage_execution=self._execution_status(stages, captured_at),
            ai_calls=CallOperationalStatus(
                counts=calls["counts"],
                oldest_unknown_age_seconds=self._age_seconds(
                    calls["oldest_unknown_created_at"], captured_at
                ),
            ),
            reports=ReportOperationalStatus(**reports),
            evaluation_jobs=self._execution_status(evaluation_jobs, captured_at),
            evaluation_outbox=self._queue_status(evaluation_outbox, captured_at),
            evaluation_metrics=EvaluationMetricOperationalStatus(**metrics),
        )

    @classmethod
    def _queue_status(
        cls, value: dict[str, Any], now: datetime
    ) -> QueueOperationalStatus:
        return QueueOperationalStatus(
            counts=value["counts"],
            expired_relay_leases=value["expired_relay_leases"],
            oldest_active_age_seconds=cls._age_seconds(
                value["oldest_active_created_at"], now
            ),
        )

    @classmethod
    def _execution_status(
        cls, value: dict[str, Any], now: datetime
    ) -> ExecutionOperationalStatus:
        return ExecutionOperationalStatus(
            counts=value["counts"],
            expired_running_leases=value["expired_running_leases"],
            oldest_active_age_seconds=cls._age_seconds(
                value["oldest_active_created_at"], now
            ),
        )

    @staticmethod
    def _aggregate_evaluation_metrics(runs: list[Any]) -> dict[str, int]:
        result = {
            "inspected_runs": 0,
            "missing_rows": 0,
            "invalid_comparisons": 0,
            "coverage_loss": 0,
            "technical_failures": 0,
            "receipt_complete_count": 0,
            "case_rows": 0,
        }
        for run in runs:
            summary = run.summary_json
            if not isinstance(summary, dict):
                continue
            result["inspected_runs"] += 1
            result["missing_rows"] += OperationalStatusService._non_negative_int(
                summary.get("missing_rows")
            )
            result["coverage_loss"] += OperationalStatusService._non_negative_int(
                summary.get("coverage_loss")
            )
            result["technical_failures"] += OperationalStatusService._non_negative_int(
                summary.get("technical_failures")
            )
            result["receipt_complete_count"] += (
                OperationalStatusService._non_negative_int(
                    summary.get("receipt_complete_count")
                )
            )
            result["case_rows"] += OperationalStatusService._non_negative_int(
                summary.get("case_count")
            )
            paired = summary.get("paired_ab")
            if isinstance(paired, dict):
                result["invalid_comparisons"] += (
                    OperationalStatusService._non_negative_int(
                        paired.get("invalid_comparison_count")
                    )
                )
        return result

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        return int(value) if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _age_seconds(value: datetime | None, now: datetime) -> int | None:
        if value is None:
            return None
        normalized_value = value.replace(tzinfo=None) if value.tzinfo else value
        normalized_now = now.replace(tzinfo=None) if now.tzinfo else now
        if normalized_value > normalized_now:
            return 0
        return int((normalized_now - normalized_value).total_seconds())


__all__ = ["OperationalStatusService"]
