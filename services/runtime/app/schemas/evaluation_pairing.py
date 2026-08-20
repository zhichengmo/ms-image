"""Paired A/B comparison contracts for frozen Evaluation case rows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evaluation_execution import MedicalStatus, TechnicalStatus


ExperimentVariable = Literal["config", "profile_route", "prompt", "model"]


class PairedABSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_variable: ExperimentVariable
    random_seed: int = 20260819
    bootstrap_iterations: int = Field(default=1000, ge=100, le=10000)
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.999)


class PairedCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    comparison_status: Literal["paired", "invalid_comparison"]
    invalid_reasons: list[str] = Field(default_factory=list)
    control_status: MedicalStatus | None = None
    candidate_status: MedicalStatus | None = None
    control_technical_status: TechnicalStatus | None = None
    candidate_technical_status: TechnicalStatus | None = None
    control_correct: bool | None = None
    candidate_correct: bool | None = None
    correctness_delta: int | None = Field(default=None, ge=-1, le=1)
    unsafe_flip: bool = False
    technical_delta: int | None = Field(default=None, ge=-1, le=1)
    coverage_delta: int | None = Field(default=None, ge=-1, le=1)
    cost_delta: float | None = None
    latency_delta: int | None = None
    cluster_id: str | None = None


class ArmSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normal_false_positive: int = Field(ge=0)
    abnormal_miss: int = Field(ge=0)
    review_required: int = Field(ge=0)
    non_diagnostic: int = Field(ge=0)
    technical_failures: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    coverage_loss: int = Field(ge=0)
    receipt_completeness: float = Field(ge=0, le=1)
    total_cost: float = Field(ge=0)
    total_latency_ms: int = Field(ge=0)


class PairedABSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation-paired-ab.v1"] = "evaluation-paired-ab.v1"
    paired_count: int = Field(ge=0)
    missing_pair_count: int = Field(ge=0)
    invalid_comparison_count: int = Field(ge=0)
    unsafe_flips: int = Field(ge=0)
    control: ArmSummary
    candidate: ArmSummary
    mcnemar_b: int = Field(ge=0)
    mcnemar_c: int = Field(ge=0)
    mcnemar_chi_square: float | None = Field(default=None, ge=0)
    mcnemar_p_value: float | None = Field(default=None, ge=0, le=1)
    mean_correctness_delta: float | None = Field(default=None, ge=-1, le=1)
    cluster_bootstrap_ci_low: float | None = Field(default=None, ge=-1, le=1)
    cluster_bootstrap_ci_high: float | None = Field(default=None, ge=-1, le=1)
    confidence_level: float
    experiment_variable: ExperimentVariable
    results: list[PairedCaseResult]


__all__ = [
    "ArmSummary",
    "PairedABSpec",
    "PairedABSummary",
    "PairedCaseResult",
]
