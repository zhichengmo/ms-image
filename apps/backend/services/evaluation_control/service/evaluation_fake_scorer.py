"""Deterministic, non-medical scorer for Evaluation pipeline validation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from apps.backend.schemas.evaluation_execution import (
    EvaluationCaseRow,
    EvaluationFailureRow,
    EvaluationInputManifest,
    EvaluationMetricSummary,
)
from apps.backend.schemas.evaluation_pairing import PairedABSpec, PairedABSummary
from apps.backend.services.evaluation_control.service.evaluation_paired_ab import PairedABAggregator


class EvaluationScoringError(ValueError):
    pass


@dataclass(frozen=True)
class ScoredArtifact:
    artifact_kind: str
    schema_version: str
    content: bytes
    content_sha256: str


@dataclass(frozen=True)
class EvaluationScoreBundle:
    case_rows: tuple[EvaluationCaseRow, ...]
    failure_rows: tuple[EvaluationFailureRow, ...]
    metrics: EvaluationMetricSummary
    paired_summary: PairedABSummary | None
    artifacts: tuple[ScoredArtifact, ...]


class FakeEvaluationScorer:
    """Validate frozen rows and calculate reproducible engineering summaries.

    This scorer never infers or changes a medical status.  It only compares
    already-frozen expected/predicted values and preserves every scheduled row.
    """

    def score(
        self,
        *,
        manifest: EvaluationInputManifest,
        dataset_fingerprint: str,
        gold_fingerprint: str,
        scorer_fingerprint: str,
        experiment_fingerprint: str,
        case_split: dict[str, Any],
        denominator_contract: dict[str, Any],
    ) -> EvaluationScoreBundle:
        expected_count = case_split.get("case_count")
        expected_split = case_split.get("role")
        unique_case_count = len({case.case_id for case in manifest.cases})
        if expected_count != unique_case_count:
            raise EvaluationScoringError("evaluation_case_count_drift")
        if (
            denominator_contract.get("medical") is None
            or denominator_contract.get("population") is None
        ):
            raise EvaluationScoringError("evaluation_denominator_contract_invalid")

        seen: set[tuple[str, str]] = set()
        case_rows: list[EvaluationCaseRow] = []
        failure_rows: list[EvaluationFailureRow] = []
        for case in sorted(
            manifest.cases, key=lambda item: (item.case_id, item.arm_key)
        ):
            identity = (case.case_id, case.arm_key)
            if identity in seen:
                raise EvaluationScoringError("evaluation_case_arm_duplicate")
            seen.add(identity)
            if expected_split and case.split != expected_split:
                raise EvaluationScoringError("evaluation_case_split_drift")
            expected_fingerprints = {
                "dataset_fingerprint": dataset_fingerprint,
                "gold_fingerprint": gold_fingerprint,
                "scorer_fingerprint": scorer_fingerprint,
                "experiment_fingerprint": experiment_fingerprint,
            }
            for field, expected in expected_fingerprints.items():
                if getattr(case, field) != expected:
                    raise EvaluationScoringError(f"evaluation_{field}_drift")

            medical_evaluable = case.technical_status == "completed"
            medical_correct = (
                case.predicted_status == case.expected_status
                if medical_evaluable
                else None
            )
            row = EvaluationCaseRow(
                **case.model_dump(),
                medical_evaluable=medical_evaluable,
                medical_correct=medical_correct,
                population_included=True,
            )
            case_rows.append(row)

            reasons: list[str] = []
            if case.technical_status != "completed":
                reasons.append(f"technical:{case.technical_status}")
            if medical_correct is False:
                reasons.append("medical_incorrect")
            if case.coverage_status != "complete" or case.predicted_status in {
                "review_required",
                "non_diagnostic",
            }:
                reasons.append("coverage_loss")
            if case.receipt_status != "complete":
                reasons.append("receipt_incomplete")
            if reasons:
                failure_rows.append(
                    EvaluationFailureRow(
                        case_id=case.case_id,
                        arm_key=case.arm_key,
                        failure_reasons=sorted(set(reasons)),
                        technical_status=case.technical_status,
                        expected_status=case.expected_status,
                        predicted_status=case.predicted_status,
                        coverage_status=case.coverage_status,
                        missing_reason=case.missing_reason,
                    )
                )

        technical_counts = Counter(row.technical_status for row in case_rows)
        status_counts = Counter(row.predicted_status for row in case_rows)
        medical_rows = [row for row in case_rows if row.medical_evaluable]
        coverage_loss = sum(
            row.coverage_status != "complete"
            or row.predicted_status in {"review_required", "non_diagnostic"}
            for row in case_rows
        )
        receipt_complete_count = sum(
            row.receipt_status == "complete" for row in case_rows
        )
        metrics = EvaluationMetricSummary(
            case_count=len(case_rows),
            medical_conditional_denominator=len(medical_rows),
            medical_correct_count=sum(
                row.medical_correct is True for row in medical_rows
            ),
            end_to_end_population_denominator=len(case_rows),
            technical_failures=sum(
                row.technical_status not in {"completed", "missing"}
                for row in case_rows
            ),
            missing_rows=technical_counts.get("missing", 0),
            coverage_loss=coverage_loss,
            receipt_complete_count=receipt_complete_count,
            receipt_completeness=receipt_complete_count / len(case_rows),
            total_cost=round(sum(row.cost for row in case_rows), 8),
            total_latency_ms=sum(row.latency_ms for row in case_rows),
            status_counts=dict(sorted(status_counts.items())),
            technical_status_counts=dict(sorted(technical_counts.items())),
            source_fingerprints={
                "dataset_fingerprint": dataset_fingerprint,
                "gold_fingerprint": gold_fingerprint,
                "scorer_fingerprint": scorer_fingerprint,
                "experiment_fingerprint": experiment_fingerprint,
                "case_split_sha256": self.sha256_json(case_split),
                "denominator_contract_sha256": self.sha256_json(denominator_contract),
            },
        )
        artifacts = [
            self._artifact(
                "case_result",
                "evaluation-case-row.v1",
                [row.model_dump(mode="json") for row in case_rows],
            ),
            self._artifact(
                "failure_summary",
                "evaluation-failure-row.v1",
                [row.model_dump(mode="json") for row in failure_rows],
            ),
            self._artifact(
                "metric_summary",
                "evaluation-metrics.v1",
                metrics.model_dump(mode="json"),
            ),
        ]
        paired_summary = None
        arms = {row.arm_key for row in case_rows}
        if arms == {"control", "candidate"}:
            paired_contract = denominator_contract.get("paired_ab")
            if not isinstance(paired_contract, dict):
                raise EvaluationScoringError("paired_ab_contract_required")
            try:
                paired_spec = PairedABSpec.model_validate(paired_contract)
                paired_summary = PairedABAggregator().aggregate(
                    rows=case_rows, spec=paired_spec
                )
            except ValueError as exc:
                raise EvaluationScoringError("paired_ab_contract_invalid") from exc
            artifacts.append(
                self._artifact(
                    "paired_ab_summary",
                    "evaluation-paired-ab.v1",
                    paired_summary.model_dump(mode="json"),
                )
            )
        elif len(arms) != 1:
            raise EvaluationScoringError("evaluation_arm_contract_invalid")
        return EvaluationScoreBundle(
            case_rows=tuple(case_rows),
            failure_rows=tuple(failure_rows),
            metrics=metrics,
            paired_summary=paired_summary,
            artifacts=tuple(artifacts),
        )

    @classmethod
    def _artifact(
        cls, artifact_kind: str, schema_version: str, payload: Any
    ) -> ScoredArtifact:
        content = cls.canonical_json_bytes(
            {
                "artifact_kind": artifact_kind,
                "schema_version": schema_version,
                "payload": payload,
            }
        )
        return ScoredArtifact(
            artifact_kind=artifact_kind,
            schema_version=schema_version,
            content=content,
            content_sha256=hashlib.sha256(content).hexdigest(),
        )

    @staticmethod
    def canonical_json_bytes(value: Any) -> bytes:
        try:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise EvaluationScoringError("evaluation_serialization_failed") from exc

    @classmethod
    def sha256_json(cls, value: Any) -> str:
        return hashlib.sha256(cls.canonical_json_bytes(value)).hexdigest()


__all__ = [
    "EvaluationScoreBundle",
    "EvaluationScoringError",
    "FakeEvaluationScorer",
    "ScoredArtifact",
]
