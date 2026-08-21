"""Deterministic paired A/B aggregation with explicit invalid comparisons."""

from __future__ import annotations

from collections import defaultdict
import math
import random
from typing import Iterable

from apps.runtime.schemas.evaluation_execution import EvaluationCaseRow
from apps.runtime.schemas.evaluation_pairing import (
    ArmSummary,
    PairedABSpec,
    PairedABSummary,
    PairedCaseResult,
)


class PairedABError(ValueError):
    pass


class PairedABAggregator:
    _EXPERIMENT_FIELDS = {
        "config": {"config_id", "config_sha256"},
        "profile_route": {"profile_key", "profile_sha256", "route_signal"},
        "prompt": {"prompt_sha256"},
        "model": {"requested_model", "actual_model"},
    }
    _PAIR_FIELDS = {
        "study_revision_id",
        "study_manifest_sha256",
        "expected_status",
        "split",
        "failure_bank_role",
        "cluster_id",
        "dataset_fingerprint",
        "gold_fingerprint",
        "scorer_fingerprint",
        "config_id",
        "config_sha256",
        "profile_key",
        "profile_sha256",
        "prompt_sha256",
        "schema_sha256",
        "requested_model",
        "actual_model",
        "provider",
        "connection",
        "schedule",
        "route_signal",
    }

    def aggregate(
        self, *, rows: Iterable[EvaluationCaseRow], spec: PairedABSpec
    ) -> PairedABSummary:
        grouped: dict[str, dict[str, list[EvaluationCaseRow]]] = defaultdict(
            lambda: {"control": [], "candidate": []}
        )
        materialized = list(rows)
        if not materialized:
            raise PairedABError("paired_ab_rows_required")
        for row in materialized:
            grouped[row.case_id][row.arm_key].append(row)

        results: list[PairedCaseResult] = []
        paired_rows: list[tuple[EvaluationCaseRow, EvaluationCaseRow]] = []
        missing_pair_count = 0
        invalid_count = 0
        allowed = self._EXPERIMENT_FIELDS[spec.experiment_variable]
        for case_id in sorted(grouped):
            arms = grouped[case_id]
            reasons: list[str] = []
            if len(arms["control"]) != 1 or len(arms["candidate"]) != 1:
                missing_pair_count += 1
                reasons.append("missing_or_duplicate_arm")
                results.append(
                    PairedCaseResult(
                        case_id=case_id,
                        comparison_status="invalid_comparison",
                        invalid_reasons=reasons,
                    )
                )
                invalid_count += 1
                continue
            control = arms["control"][0]
            candidate = arms["candidate"][0]
            for field in sorted(self._PAIR_FIELDS - allowed):
                if getattr(control, field) != getattr(candidate, field):
                    reasons.append(f"mismatch:{field}")
            if control.actual_model and control.actual_model != control.requested_model:
                reasons.append("control_actual_model_drift")
            if (
                candidate.actual_model
                and candidate.actual_model != candidate.requested_model
            ):
                reasons.append("candidate_actual_model_drift")
            if reasons:
                results.append(
                    PairedCaseResult(
                        case_id=case_id,
                        comparison_status="invalid_comparison",
                        invalid_reasons=reasons,
                        control_status=control.predicted_status,
                        candidate_status=candidate.predicted_status,
                        control_technical_status=control.technical_status,
                        candidate_technical_status=candidate.technical_status,
                        control_correct=control.medical_correct,
                        candidate_correct=candidate.medical_correct,
                        cluster_id=control.cluster_id or control.case_id,
                    )
                )
                invalid_count += 1
                continue

            control_correct = control.medical_correct
            candidate_correct = candidate.medical_correct
            correctness_delta = (
                int(candidate_correct) - int(control_correct)
                if control_correct is not None and candidate_correct is not None
                else None
            )
            unsafe_flip = control_correct is True and candidate_correct is False
            result = PairedCaseResult(
                case_id=case_id,
                comparison_status="paired",
                control_status=control.predicted_status,
                candidate_status=candidate.predicted_status,
                control_technical_status=control.technical_status,
                candidate_technical_status=candidate.technical_status,
                control_correct=control_correct,
                candidate_correct=candidate_correct,
                correctness_delta=correctness_delta,
                unsafe_flip=unsafe_flip,
                technical_delta=self._indicator(
                    candidate.technical_status != "completed"
                )
                - self._indicator(control.technical_status != "completed"),
                coverage_delta=self._indicator(self._coverage_loss(candidate))
                - self._indicator(self._coverage_loss(control)),
                cost_delta=round(candidate.cost - control.cost, 8),
                latency_delta=candidate.latency_ms - control.latency_ms,
                cluster_id=control.cluster_id or control.case_id,
            )
            results.append(result)
            paired_rows.append((control, candidate))

        deltas = [
            result.correctness_delta
            for result in results
            if result.comparison_status == "paired"
            and result.correctness_delta is not None
        ]
        mcnemar_b = sum(
            control.medical_correct is True and candidate.medical_correct is False
            for control, candidate in paired_rows
        )
        mcnemar_c = sum(
            control.medical_correct is False and candidate.medical_correct is True
            for control, candidate in paired_rows
        )
        chi_square, p_value = self._mcnemar(mcnemar_b, mcnemar_c)
        ci_low, ci_high = self._cluster_bootstrap(
            results=results,
            seed=spec.random_seed,
            iterations=spec.bootstrap_iterations,
            confidence_level=spec.confidence_level,
        )
        return PairedABSummary(
            paired_count=len(paired_rows),
            missing_pair_count=missing_pair_count,
            invalid_comparison_count=invalid_count,
            unsafe_flips=sum(result.unsafe_flip for result in results),
            control=self._arm_summary(materialized, "control"),
            candidate=self._arm_summary(materialized, "candidate"),
            mcnemar_b=mcnemar_b,
            mcnemar_c=mcnemar_c,
            mcnemar_chi_square=chi_square,
            mcnemar_p_value=p_value,
            mean_correctness_delta=(sum(deltas) / len(deltas) if deltas else None),
            cluster_bootstrap_ci_low=ci_low,
            cluster_bootstrap_ci_high=ci_high,
            confidence_level=spec.confidence_level,
            experiment_variable=spec.experiment_variable,
            results=results,
        )

    @classmethod
    def _arm_summary(cls, rows: list[EvaluationCaseRow], arm_key: str) -> ArmSummary:
        arm = [row for row in rows if row.arm_key == arm_key]
        receipt_complete = sum(row.receipt_status == "complete" for row in arm)
        return ArmSummary(
            normal_false_positive=sum(
                row.expected_status == "normal"
                and row.predicted_status == "abnormal"
                and row.medical_evaluable
                for row in arm
            ),
            abnormal_miss=sum(
                row.expected_status == "abnormal"
                and row.predicted_status == "normal"
                and row.medical_evaluable
                for row in arm
            ),
            review_required=sum(
                row.predicted_status == "review_required" for row in arm
            ),
            non_diagnostic=sum(row.predicted_status == "non_diagnostic" for row in arm),
            technical_failures=sum(
                row.technical_status not in {"completed", "missing"} for row in arm
            ),
            missing_rows=sum(row.technical_status == "missing" for row in arm),
            coverage_loss=sum(cls._coverage_loss(row) for row in arm),
            receipt_completeness=(receipt_complete / len(arm) if arm else 0),
            total_cost=round(sum(row.cost for row in arm), 8),
            total_latency_ms=sum(row.latency_ms for row in arm),
        )

    @staticmethod
    def _coverage_loss(row: EvaluationCaseRow) -> bool:
        return row.coverage_status != "complete" or row.predicted_status in {
            "review_required",
            "non_diagnostic",
        }

    @staticmethod
    def _indicator(value: bool) -> int:
        return 1 if value else 0

    @staticmethod
    def _mcnemar(b: int, c: int) -> tuple[float | None, float | None]:
        discordant = b + c
        if discordant == 0:
            return None, None
        chi_square = (abs(b - c) - 1) ** 2 / discordant
        p_value = math.erfc(math.sqrt(chi_square / 2))
        return chi_square, p_value

    @staticmethod
    def _cluster_bootstrap(
        *,
        results: list[PairedCaseResult],
        seed: int,
        iterations: int,
        confidence_level: float,
    ) -> tuple[float | None, float | None]:
        clusters: dict[str, list[int]] = defaultdict(list)
        for result in results:
            if (
                result.comparison_status == "paired"
                and result.correctness_delta is not None
            ):
                clusters[result.cluster_id or result.case_id].append(
                    result.correctness_delta
                )
        if not clusters:
            return None, None
        keys = sorted(clusters)
        rng = random.Random(seed)
        samples: list[float] = []
        for _ in range(iterations):
            selected = [rng.choice(keys) for _ in keys]
            values = [value for key in selected for value in clusters[key]]
            samples.append(sum(values) / len(values))
        samples.sort()
        alpha = 1 - confidence_level
        low_index = max(0, int((alpha / 2) * (len(samples) - 1)))
        high_index = min(
            len(samples) - 1,
            int((1 - alpha / 2) * (len(samples) - 1)),
        )
        return samples[low_index], samples[high_index]


__all__ = ["PairedABAggregator", "PairedABError"]
