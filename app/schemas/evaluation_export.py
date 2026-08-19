"""Control-plane contracts for exporting frozen online facts to Evaluation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.evaluation import EvaluationJobResponse
from app.schemas.evaluation_execution import ArmKey, MedicalStatus
from app.schemas.imaging_common import normalize_required_text


class EvaluationCaseExportSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=64)
    report_id: str | None = Field(default=None, max_length=64)
    expected_status: MedicalStatus
    split: Literal["development", "failure_bank", "holdout"]
    failure_bank_role: str | None = Field(default=None, max_length=64)
    arm_key: ArmKey = "control"
    cluster_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_truth_status(self):
        if self.expected_status == "not_produced":
            raise ValueError("evaluation_expected_status_invalid")
        return self


class EvaluationExportJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scorer_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    denominator_contract: dict[str, Any]
    schedule: str = Field(min_length=1, max_length=128)
    sanitization_policy_version: str = Field(
        default="evaluation-export.v1", min_length=1, max_length=64
    )
    cases: list[EvaluationCaseExportSpec] = Field(min_length=1, max_length=1000)

    @field_validator("request_id", "schedule", "sanitization_policy_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @model_validator(mode="after")
    def validate_cases(self):
        identities = [(item.case_id, item.arm_key) for item in self.cases]
        if len(identities) != len(set(identities)):
            raise ValueError("evaluation_export_case_arm_duplicate")
        if len({item.split for item in self.cases}) != 1:
            raise ValueError("evaluation_export_split_mixed")
        arms = {item.arm_key for item in self.cases}
        if len(arms) > 1 and arms != {"control", "candidate"}:
            raise ValueError("evaluation_export_arm_contract_invalid")
        if (
            self.denominator_contract.get("medical") is None
            or self.denominator_contract.get("population") is None
        ):
            raise ValueError("evaluation_denominator_contract_invalid")
        return self


class EvaluationExportJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: EvaluationJobResponse
    input_manifest_sha256: str
    sanitization_sha256: str
    exported_case_count: int


__all__ = [
    "EvaluationCaseExportSpec",
    "EvaluationExportJobCreate",
    "EvaluationExportJobResponse",
]
