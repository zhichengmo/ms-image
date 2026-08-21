"""Aggregate non-sensitive operational facts from online and Evaluation DBs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.evaluation import (
    EvaluationJobDal,
    EvaluationOutboxDal,
    EvaluationRunDal,
)
from apps.backend.crud.ai_call import AICallDal
from apps.backend.crud.outbox import OutboxDal
from apps.backend.crud.report import ReportDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.core.config import settings
from apps.backend.schemas.operations import (
    CallOperationalStatus,
    EvaluationMetricOperationalStatus,
    ExecutionOperationalStatus,
    OperationalAlert,
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
        self,
        *,
        now: datetime | None = None,
        run_limit: int = 500,
        readiness: dict[str, Any] | None = None,
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
        online_outbox_status = self._queue_status(online_outbox, captured_at)
        stage_status = self._execution_status(stages, captured_at)
        ai_call_status = CallOperationalStatus(
            counts=calls["counts"],
            oldest_unknown_age_seconds=self._age_seconds(
                calls["oldest_unknown_created_at"], captured_at
            ),
        )
        evaluation_job_status = self._execution_status(evaluation_jobs, captured_at)
        evaluation_outbox_status = self._queue_status(
            evaluation_outbox, captured_at
        )
        return OperationalStatusResponse(
            captured_at=captured_at,
            online_outbox=online_outbox_status,
            stage_execution=stage_status,
            ai_calls=ai_call_status,
            reports=ReportOperationalStatus(**reports),
            evaluation_jobs=evaluation_job_status,
            evaluation_outbox=evaluation_outbox_status,
            evaluation_metrics=EvaluationMetricOperationalStatus(**metrics),
            alerts=self._build_alerts(
                captured_at=captured_at,
                online_outbox=online_outbox_status,
                stage_execution=stage_status,
                ai_calls=ai_call_status,
                evaluation_jobs=evaluation_job_status,
                evaluation_outbox=evaluation_outbox_status,
                evaluation_metrics=metrics,
                readiness=readiness,
            ),
        )

    @classmethod
    def _build_alerts(
        cls,
        *,
        captured_at: datetime,
        online_outbox: QueueOperationalStatus,
        stage_execution: ExecutionOperationalStatus,
        ai_calls: CallOperationalStatus,
        evaluation_jobs: ExecutionOperationalStatus,
        evaluation_outbox: QueueOperationalStatus,
        evaluation_metrics: dict[str, int],
        readiness: dict[str, Any] | None,
    ) -> list[OperationalAlert]:
        if not settings.OPERATIONAL_ALERTS_ENABLED:
            return []

        alerts: list[OperationalAlert] = []
        cls._append_count_alert(
            alerts,
            code="online_outbox_expired_relay_leases",
            source="online_outbox",
            observed=online_outbox.expired_relay_leases,
            threshold=settings.OPERATIONAL_ALERT_LEASE_COUNT_THRESHOLD,
            severity="critical",
            summary="在线 Outbox 存在过期 Relay lease",
            captured_at=captured_at,
        )
        cls._append_age_alert(
            alerts,
            code="online_outbox_active_age_high",
            source="online_outbox",
            observed=online_outbox.oldest_active_age_seconds,
            threshold=settings.OPERATIONAL_ALERT_ACTIVE_AGE_SECONDS,
            severity="warning",
            summary="在线 Outbox 最早活动事件超过年龄阈值",
            captured_at=captured_at,
        )
        cls._append_count_alert(
            alerts,
            code="online_stage_expired_running_leases",
            source="online_stage",
            observed=stage_execution.expired_running_leases,
            threshold=settings.OPERATIONAL_ALERT_LEASE_COUNT_THRESHOLD,
            severity="critical",
            summary="在线 Stage 存在过期运行 lease",
            captured_at=captured_at,
        )
        cls._append_age_alert(
            alerts,
            code="online_stage_active_age_high",
            source="online_stage",
            observed=stage_execution.oldest_active_age_seconds,
            threshold=settings.OPERATIONAL_ALERT_ACTIVE_AGE_SECONDS,
            severity="warning",
            summary="在线 Stage 最早活动执行超过年龄阈值",
            captured_at=captured_at,
        )
        cls._append_age_alert(
            alerts,
            code="online_ai_call_unknown_age_high",
            source="online_ai_calls",
            observed=ai_calls.oldest_unknown_age_seconds,
            threshold=settings.OPERATIONAL_ALERT_AI_UNKNOWN_AGE_SECONDS,
            severity="warning",
            summary="在线 AI Call unknown 状态超过年龄阈值",
            captured_at=captured_at,
        )
        cls._append_count_alert(
            alerts,
            code="evaluation_job_expired_running_leases",
            source="evaluation_jobs",
            observed=evaluation_jobs.expired_running_leases,
            threshold=settings.OPERATIONAL_ALERT_LEASE_COUNT_THRESHOLD,
            severity="critical",
            summary="Evaluation Job 存在过期运行 lease",
            captured_at=captured_at,
        )
        cls._append_age_alert(
            alerts,
            code="evaluation_job_active_age_high",
            source="evaluation_jobs",
            observed=evaluation_jobs.oldest_active_age_seconds,
            threshold=settings.OPERATIONAL_ALERT_ACTIVE_AGE_SECONDS,
            severity="warning",
            summary="Evaluation Job 最早活动执行超过年龄阈值",
            captured_at=captured_at,
        )
        cls._append_count_alert(
            alerts,
            code="evaluation_outbox_expired_relay_leases",
            source="evaluation_outbox",
            observed=evaluation_outbox.expired_relay_leases,
            threshold=settings.OPERATIONAL_ALERT_LEASE_COUNT_THRESHOLD,
            severity="critical",
            summary="Evaluation Outbox 存在过期 Relay lease",
            captured_at=captured_at,
        )
        cls._append_age_alert(
            alerts,
            code="evaluation_outbox_active_age_high",
            source="evaluation_outbox",
            observed=evaluation_outbox.oldest_active_age_seconds,
            threshold=settings.OPERATIONAL_ALERT_ACTIVE_AGE_SECONDS,
            severity="warning",
            summary="Evaluation Outbox 最早活动事件超过年龄阈值",
            captured_at=captured_at,
        )

        for metric, threshold, code, severity, summary in (
            (
                "missing_rows",
                settings.OPERATIONAL_ALERT_MISSING_ROWS,
                "evaluation_missing_rows",
                "warning",
                "Evaluation 结果存在 missing rows",
            ),
            (
                "invalid_comparisons",
                settings.OPERATIONAL_ALERT_INVALID_COMPARISONS,
                "evaluation_invalid_comparisons",
                "warning",
                "Evaluation 存在 invalid comparison",
            ),
            (
                "coverage_loss",
                settings.OPERATIONAL_ALERT_COVERAGE_LOSS,
                "evaluation_coverage_loss",
                "warning",
                "Evaluation 存在 coverage loss",
            ),
            (
                "technical_failures",
                settings.OPERATIONAL_ALERT_TECHNICAL_FAILURES,
                "evaluation_technical_failures",
                "warning",
                "Evaluation 存在 technical failures",
            ),
            (
                "artifact_drift_failures",
                settings.OPERATIONAL_ALERT_ARTIFACT_DRIFT,
                "evaluation_artifact_drift",
                "critical",
                "Evaluation Artifact 存在 hash drift",
            ),
        ):
            cls._append_count_alert(
                alerts,
                code=code,
                source="evaluation_metrics",
                observed=evaluation_metrics.get(metric),
                threshold=threshold,
                severity=severity,
                summary=summary,
                captured_at=captured_at,
            )

        cls._append_dependency_alerts(
            alerts, readiness=readiness, captured_at=captured_at
        )
        cls._append_broker_alerts(alerts, readiness=readiness, captured_at=captured_at)
        return alerts

    @staticmethod
    def _append_dependency_alerts(
        alerts: list[OperationalAlert],
        *,
        readiness: dict[str, Any] | None,
        captured_at: datetime,
    ) -> None:
        if not isinstance(readiness, dict):
            return
        components = readiness.get("components")
        if not isinstance(components, dict):
            return
        for component_name, code, summary in (
            ("database", "online_database_unavailable", "在线数据库依赖未就绪"),
            (
                "evaluation_database",
                "evaluation_database_unavailable",
                "Evaluation 数据库依赖未就绪",
            ),
            ("redis", "redis_unavailable", "Redis 依赖未就绪"),
        ):
            component = components.get(component_name)
            if not isinstance(component, dict) or component.get("ready") is not False:
                continue
            OperationalStatusService._append_alert(
                alerts,
                code=code,
                source=component_name,
                observed=None,
                threshold=None,
                unit="state",
                severity="critical",
                summary=summary,
                captured_at=captured_at,
            )

    @classmethod
    def _append_broker_alerts(
        cls,
        alerts: list[OperationalAlert],
        *,
        readiness: dict[str, Any] | None,
        captured_at: datetime,
    ) -> None:
        if not isinstance(readiness, dict):
            return
        components = readiness.get("components")
        if not isinstance(components, dict):
            return
        for domain in ("imaging", "evaluation"):
            component = components.get(f"{domain}_broker")
            if not isinstance(component, dict) or not component.get("required"):
                continue
            if (
                component.get("ready") is not True
                and settings.OPERATIONAL_ALERT_CONSUMER_MINIMUM > 0
            ):
                cls._append_alert(
                    alerts,
                    code=f"{domain}_broker_consumer_unavailable",
                    source=f"{domain}_broker",
                    observed=cls._non_negative_int_or_none(
                        component.get("consumer_count")
                    ),
                    threshold=settings.OPERATIONAL_ALERT_CONSUMER_MINIMUM,
                    unit="consumer",
                    severity="critical",
                    summary=f"{domain} 消息域 Worker consumer 未就绪",
                    captured_at=captured_at,
                )
            cls._append_count_alert(
                alerts,
                code=f"{domain}_broker_queue_depth_high",
                source=f"{domain}_broker",
                observed=component.get("queue_message_count"),
                threshold=settings.OPERATIONAL_ALERT_QUEUE_DEPTH,
                severity="warning",
                summary=f"{domain} Broker queue depth 超过阈值",
                captured_at=captured_at,
            )
            cls._append_count_alert(
                alerts,
                code=f"{domain}_broker_dlq_depth_high",
                source=f"{domain}_broker",
                observed=component.get("dead_letter_message_count"),
                threshold=settings.OPERATIONAL_ALERT_DLQ_DEPTH,
                severity="critical",
                summary=f"{domain} Broker DLQ depth 超过阈值",
                captured_at=captured_at,
            )

    @classmethod
    def _append_count_alert(
        cls,
        alerts: list[OperationalAlert],
        *,
        code: str,
        source: str,
        observed: Any,
        threshold: int,
        severity: str,
        summary: str,
        captured_at: datetime,
    ) -> None:
        value = cls._non_negative_int_or_none(observed)
        if value is None or threshold <= 0 or value < threshold:
            return
        cls._append_alert(
            alerts,
            code=code,
            source=source,
            observed=value,
            threshold=threshold,
            unit="count",
            severity=severity,
            summary=summary,
            captured_at=captured_at,
        )

    @classmethod
    def _append_age_alert(
        cls,
        alerts: list[OperationalAlert],
        *,
        code: str,
        source: str,
        observed: Any,
        threshold: int,
        severity: str,
        summary: str,
        captured_at: datetime,
    ) -> None:
        value = cls._non_negative_int_or_none(observed)
        if value is None or threshold <= 0 or value < threshold:
            return
        cls._append_alert(
            alerts,
            code=code,
            source=source,
            observed=value,
            threshold=threshold,
            unit="seconds",
            severity=severity,
            summary=summary,
            captured_at=captured_at,
        )

    @staticmethod
    def _append_alert(
        alerts: list[OperationalAlert],
        *,
        code: str,
        source: str,
        observed: int | None,
        threshold: int | None,
        unit: str,
        severity: str,
        summary: str,
        captured_at: datetime,
    ) -> None:
        alerts.append(
            OperationalAlert(
                code=code,
                severity=severity,
                source=source,
                observed_value=observed,
                threshold=threshold,
                unit=unit,
                captured_at=captured_at,
                summary=summary,
            )
        )

    @staticmethod
    def _non_negative_int_or_none(value: Any) -> int | None:
        return int(value) if type(value) is int and value >= 0 else None

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
