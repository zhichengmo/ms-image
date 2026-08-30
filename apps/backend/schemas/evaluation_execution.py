"""Deterministic Evaluation execution and artifact contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.backend.core.ai.clinical_context import (
    CLINICAL_CONTEXT_LEGACY_NONE,
    CLINICAL_CONTEXT_V1,
    EMPTY_CLINICAL_CONTEXT_SHA256,
)


MedicalStatus = Literal[
    "normal",
    "abnormal",
    "review_required",
    "non_diagnostic",
    "not_produced",
]
TechnicalStatus = Literal[
    "completed",
    "technical_failure",
    "missing",
    "over_budget",
    "partial_sent",
    "provider_unknown",
    "schema_invalid",
]
CoverageStatus = Literal["complete", "coverage_loss", "missing"]
ReceiptStatus = Literal["complete", "incomplete", "unsupported", "not_applicable"]
ArmKey = Literal["control", "candidate"]


class EvaluationCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=64)
    report_id: str | None = Field(default=None, max_length=64)
    study_revision_id: str = Field(min_length=1, max_length=128)
    study_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    expected_status: MedicalStatus
    predicted_status: MedicalStatus
    technical_status: TechnicalStatus
    coverage_status: CoverageStatus
    missing_reason: str | None = Field(default=None, max_length=200)

    split: Literal["development", "failure_bank", "regression", "holdout"]
    failure_bank_role: str | None = Field(default=None, max_length=64)
    arm_key: ArmKey
    cluster_id: str | None = Field(default=None, max_length=128)

    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scorer_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    config_id: str = Field(min_length=1, max_length=64)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_key: str = Field(min_length=1, max_length=96)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_model: str = Field(min_length=1, max_length=128)
    actual_model: str | None = Field(default=None, max_length=128)
    provider: str = Field(min_length=1, max_length=64)
    connection: str = Field(min_length=1, max_length=128)
    schedule: str = Field(min_length=1, max_length=128)

    route_signal: str | None = Field(default=None, max_length=80)
    source_stage_id: str | None = Field(default=None, max_length=64)
    source_call_id: str | None = Field(default=None, max_length=64)
    receipt_status: ReceiptStatus

    clinical_context_policy_version: Literal[
        "legacy-none", "xray-clinical-context.v1"
    ] = Field(
        default=CLINICAL_CONTEXT_LEGACY_NONE,
    )
    clinical_context_sha256: str = Field(
        default=EMPTY_CLINICAL_CONTEXT_SHA256,
        pattern=r"^[0-9a-f]{64}$",
    )
    clinical_context_source_system: str | None = Field(default=None, max_length=64)
    clinical_context_recorded_at: str | None = Field(default=None, max_length=64)
    clinical_context_temporal_scope: Literal["available_at_request"] | None = None

    cost: float = Field(ge=0)
    latency_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_failure_boundary(self):
        if self.technical_status == "completed":
            if self.predicted_status == "not_produced":
                raise ValueError("completed_case_medical_status_invalid")
            if self.missing_reason is not None:
                raise ValueError("completed_case_missing_reason_invalid")
        else:
            if not self.missing_reason:
                raise ValueError("failed_case_missing_reason_required")
            if self.predicted_status != "not_produced":
                raise ValueError("technical_failure_medical_status_invalid")
        source_values = (
            self.clinical_context_source_system,
            self.clinical_context_recorded_at,
            self.clinical_context_temporal_scope,
        )
        if self.clinical_context_policy_version == CLINICAL_CONTEXT_LEGACY_NONE:
            if self.clinical_context_sha256 != EMPTY_CLINICAL_CONTEXT_SHA256 or any(
                value is not None for value in source_values
            ):
                raise ValueError("evaluation_clinical_context_legacy_invalid")
        elif self.clinical_context_policy_version == CLINICAL_CONTEXT_V1:
            if self.clinical_context_sha256 == EMPTY_CLINICAL_CONTEXT_SHA256:
                if any(value is not None for value in source_values):
                    raise ValueError("evaluation_clinical_context_empty_invalid")
            elif any(value is None for value in source_values):
                raise ValueError("evaluation_clinical_context_source_required")
        return self


class EvaluationInputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation-input.v1", "evaluation-input.v2"]
    cases: list[EvaluationCaseInput] = Field(min_length=1)


class EvaluationCaseRow(EvaluationCaseInput):
    medical_evaluable: bool
    medical_correct: bool | None
    population_included: Literal[True] = True


class EvaluationFailureRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    arm_key: ArmKey
    failure_reasons: list[str] = Field(min_length=1)
    technical_status: TechnicalStatus
    expected_status: MedicalStatus
    predicted_status: MedicalStatus
    coverage_status: CoverageStatus
    missing_reason: str | None = None


class EvaluationMetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation-metrics.v1"] = "evaluation-metrics.v1"
    case_count: int = Field(ge=1)
    medical_conditional_denominator: int = Field(ge=0)
    medical_correct_count: int = Field(ge=0)
    end_to_end_population_denominator: int = Field(ge=1)
    technical_failures: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    coverage_loss: int = Field(ge=0)
    receipt_complete_count: int = Field(ge=0)
    receipt_completeness: float = Field(ge=0, le=1)
    total_cost: float = Field(ge=0)
    total_latency_ms: int = Field(ge=0)
    status_counts: dict[str, int]
    technical_status_counts: dict[str, int]
    source_fingerprints: dict[str, str]


class EvaluationArtifactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_kind: Literal["case_result", "failure_summary", "metric_summary"]
    schema_version: str
    payload: dict[str, Any] | list[dict[str, Any]]


__all__ = [
    "EvaluationArtifactPayload",
    "EvaluationCaseInput",
    "EvaluationCaseRow",
    "EvaluationFailureRow",
    "EvaluationInputManifest",
    "EvaluationMetricSummary",
]
