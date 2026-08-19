"""Operational status response contracts without resource-level data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QueueOperationalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts: dict[str, int]
    expired_relay_leases: int = Field(ge=0)
    oldest_active_age_seconds: int | None = Field(default=None, ge=0)


class ExecutionOperationalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts: dict[str, int]
    expired_running_leases: int = Field(ge=0)
    oldest_active_age_seconds: int | None = Field(default=None, ge=0)


class CallOperationalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts: dict[str, int]
    oldest_unknown_age_seconds: int | None = Field(default=None, ge=0)


class ReportOperationalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_counts: dict[str, int]
    medical_status_counts: dict[str, int]


class EvaluationMetricOperationalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inspected_runs: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    invalid_comparisons: int = Field(ge=0)
    coverage_loss: int = Field(ge=0)
    technical_failures: int = Field(ge=0)
    receipt_complete_count: int = Field(ge=0)
    case_rows: int = Field(ge=0)
    artifact_drift_failures: int = Field(ge=0)


class OperationalStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    online_outbox: QueueOperationalStatus
    stage_execution: ExecutionOperationalStatus
    ai_calls: CallOperationalStatus
    reports: ReportOperationalStatus
    evaluation_jobs: ExecutionOperationalStatus
    evaluation_outbox: QueueOperationalStatus
    evaluation_metrics: EvaluationMetricOperationalStatus


__all__ = [
    "CallOperationalStatus",
    "EvaluationMetricOperationalStatus",
    "ExecutionOperationalStatus",
    "OperationalStatusResponse",
    "QueueOperationalStatus",
    "ReportOperationalStatus",
]
