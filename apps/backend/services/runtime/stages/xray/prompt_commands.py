"""Pure XRay Prompt command construction from frozen Task/Stage facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.backend.core.ai.config_contract import (
    TASK_REQUEST_SNAPSHOT_V2,
    TASK_REQUEST_SNAPSHOT_V3,
)
from apps.backend.core.ai.clinical_context import (
    ClinicalContextContractError,
    read_frozen_clinical_context,
)
from apps.backend.core.ai.prompting import (
    CompiledPrompt,
    PromptCompiler,
    PromptContractError,
)
from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.imaging.manifest import (
    ManifestContractError,
    validate_frozen_study_series,
)
from apps.backend.core.pipeline import XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1


_TARGETED_FOCUS_OPTIONS = {
    "thoracic": ("lung_pattern", "cardiovascular_contour"),
    "abdominal": ("gi_obstruction", "urinary_mineralization"),
    "appendicular_orthopedic": ("fracture_dislocation",),
    "axial_orthopedic": ("alignment",),
}


@dataclass(frozen=True)
class XRayPromptCommand:
    prompt_kind: str
    applicable_family_keys: tuple[str, ...]
    safe_context: dict[str, Any]
    family_key: str | None = None
    focus_key: str | None = None
    strategy_key: str | None = None
    primary_complete_result: dict[str, Any] | None = None
    quality_results: dict[str, Any] | None = None
    route_context: dict[str, Any] | None = None
    study_screening_result: dict[str, Any] | None = None
    system_analysis_result: dict[str, Any] | None = None
    final_medical_result: dict[str, Any] | None = None

    def compile(self, compiler: PromptCompiler) -> CompiledPrompt:
        safe_context = dict(self.safe_context)
        include_technical_evidence = bool(
            safe_context.pop("technical_evidence_available", False)
        )
        if self.prompt_kind == "primary":
            return compiler.compile_primary(
                applicable_family_keys=self.applicable_family_keys,
                safe_context=safe_context,
                include_technical_evidence=include_technical_evidence,
            )
        if self.prompt_kind == "targeted":
            if (
                self.family_key is None
                or self.focus_key is None
                or self.primary_complete_result is None
            ):
                raise PromptContractError("targeted_prompt_selection_missing")
            return compiler.compile_targeted(
                family_key=self.family_key,
                focus_key=self.focus_key,
                strategy_key=self.strategy_key,
                safe_context=safe_context,
                primary_complete_result=self.primary_complete_result,
                include_technical_evidence=include_technical_evidence,
            )
        raise PromptContractError("prompt_kind_not_supported")


def build_primary_ai_request_command(*, task: Any, stage: Any) -> XRayPromptCommand:
    snapshot = task.request_snapshot_json or {}
    safe_context = _base_context(
        task=task,
        stage=stage,
        snapshot=snapshot,
        prompt_mode="primary",
    )
    if snapshot.get("profile_key") == XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1:
        if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
            raise PromptContractError("primary_adjudication_snapshot_v3_required")
        safe_context["targeted_focus_options"] = {
            family: list(focuses) for family, focuses in _TARGETED_FOCUS_OPTIONS.items()
        }
        quality_review = snapshot.get("quality_review")
        quality_results = (
            quality_review.get("result") if isinstance(quality_review, dict) else None
        )
        if not isinstance(quality_results, dict):
            raise PromptContractError("primary_adjudication_quality_result_missing")
        upstream_results = (stage.input_json or {}).get("upstream_results")
        if not isinstance(upstream_results, dict):
            raise PromptContractError("primary_adjudication_upstream_results_missing")
        screening_result = _read_upstream_stage_result(
            upstream_results=upstream_results,
            stage_key="study_screening",
            result_key="study_screening_result",
        )
        system_result = _read_upstream_stage_result(
            upstream_results=upstream_results,
            stage_key="system_analysis",
            result_key="system_analysis_result",
        )
        return XRayPromptCommand(
            prompt_kind="primary",
            applicable_family_keys=(),
            safe_context=safe_context,
            quality_results=dict(quality_results),
            study_screening_result=screening_result,
            system_analysis_result=system_result,
        )
    if snapshot.get("snapshot_contract_version") in {
        TASK_REQUEST_SNAPSHOT_V2,
        TASK_REQUEST_SNAPSHOT_V3,
    }:
        # v2 Configs own exactly one frozen Prompt body.  Prompt family data
        # is no longer a selection input; this command only transports safe
        # Task/Stage context to the strict renderer.
        return XRayPromptCommand(
            prompt_kind="primary",
            applicable_family_keys=(),
            safe_context=safe_context,
        )
    families = snapshot.get("applicable_family_keys") or ()
    if not isinstance(families, list) or not all(
        isinstance(item, str) for item in families
    ):
        raise PromptContractError("primary_family_context_invalid")
    return XRayPromptCommand(
        prompt_kind="primary",
        applicable_family_keys=tuple(families),
        safe_context=safe_context,
    )


def _read_upstream_stage_result(
    *,
    upstream_results: dict[str, Any],
    stage_key: str,
    result_key: str,
) -> dict[str, Any]:
    lineage = upstream_results.get(stage_key)
    if not isinstance(lineage, dict):
        raise PromptContractError("primary_adjudication_upstream_results_missing")
    source_stage_id = lineage.get("source_stage_id")
    source_output_sha256 = lineage.get("source_output_sha256")
    stage_output = lineage.get("result")
    if (
        not isinstance(source_stage_id, str)
        or not source_stage_id
        or not isinstance(source_output_sha256, str)
        or len(source_output_sha256) != 64
        or not isinstance(stage_output, dict)
        or sha256_json(stage_output) != source_output_sha256
    ):
        raise PromptContractError("primary_adjudication_upstream_lineage_invalid")
    result = stage_output.get(result_key)
    if not isinstance(result, dict):
        raise PromptContractError("primary_adjudication_upstream_result_invalid")
    return dict(result)


def build_targeted_ai_request_command(*, task: Any, stage: Any) -> XRayPromptCommand:
    snapshot = task.request_snapshot_json or {}
    stage_input = stage.input_json or {}
    previous_output = stage_input.get("previous_output") or {}
    primary_complete_result = previous_output.get("complete_medical_result")
    if not isinstance(primary_complete_result, dict):
        raise PromptContractError("targeted_primary_result_missing")
    family_key = stage_input.get("selected_family_key")
    focus_key = stage_input.get("selected_focus_key")
    strategy_key = stage_input.get("selected_strategy_key")
    if not isinstance(family_key, str) or not isinstance(focus_key, str):
        raise PromptContractError("targeted_prompt_selection_missing")
    normalized_strategy_key = strategy_key if isinstance(strategy_key, str) else None
    source_finding_ids = stage_input.get("source_finding_ids")
    coverage_proof = stage_input.get("coverage_proof")
    route_reason_codes = stage_input.get("route_reason_codes")
    if (
        not isinstance(source_finding_ids, list)
        or not source_finding_ids
        or not all(isinstance(item, str) and item for item in source_finding_ids)
        or not isinstance(coverage_proof, dict)
        or not isinstance(route_reason_codes, list)
        or not route_reason_codes
        or not all(isinstance(item, str) and item for item in route_reason_codes)
    ):
        raise PromptContractError("targeted_route_context_invalid")
    route_context = {
        "selected_family_key": family_key,
        "selected_focus_key": focus_key,
        "selected_strategy_key": normalized_strategy_key,
        "source_finding_ids": list(source_finding_ids),
        "coverage_proof": dict(coverage_proof),
        "route_reason_codes": list(route_reason_codes),
    }
    base_context = _base_context(
        task=task,
        stage=stage,
        snapshot=snapshot,
        prompt_mode="targeted",
    )
    safe_context = {
        **base_context,
        "primary_complete_result": primary_complete_result,
        "selected_family_key": family_key,
        "selected_focus_key": focus_key,
        "selected_strategy_key": normalized_strategy_key,
        "source_finding_ids": route_context["source_finding_ids"],
        "coverage_proof": route_context["coverage_proof"],
        "route_reason_codes": route_context["route_reason_codes"],
    }
    if snapshot.get("snapshot_contract_version") in {
        TASK_REQUEST_SNAPSHOT_V2,
        TASK_REQUEST_SNAPSHOT_V3,
    }:
        bindings = snapshot.get("stage_ai_config_bindings") or {}
        binding = (
            bindings.get("targeted_review") if isinstance(bindings, dict) else None
        )
        dedicated_prompt = snapshot.get("runtime_config_source") == "code" or (
            binding.get("prompt_key") if isinstance(binding, dict) else None
        ) in {"xray_cat_targeted_review", "xray_dog_targeted_review"}
        quality_review = snapshot.get("quality_review")
        quality_results = (
            quality_review.get("result") if isinstance(quality_review, dict) else None
        )
        study_screening_result = stage_input.get("study_screening_result")
        system_analysis_result = stage_input.get("system_analysis_result")
        if dedicated_prompt:
            if not isinstance(quality_results, dict):
                raise PromptContractError("targeted_quality_result_missing")
            if not isinstance(study_screening_result, dict):
                raise PromptContractError("targeted_study_screening_result_missing")
            if not isinstance(system_analysis_result, dict):
                raise PromptContractError("targeted_system_analysis_result_missing")
        return XRayPromptCommand(
            prompt_kind="targeted",
            applicable_family_keys=(),
            safe_context=safe_context,
            family_key=family_key,
            focus_key=focus_key,
            strategy_key=normalized_strategy_key,
            primary_complete_result=primary_complete_result,
            quality_results=quality_results if dedicated_prompt else None,
            route_context=route_context if dedicated_prompt else None,
            study_screening_result=(
                study_screening_result if dedicated_prompt else None
            ),
            system_analysis_result=(
                system_analysis_result if dedicated_prompt else None
            ),
        )
    return XRayPromptCommand(
        prompt_kind="targeted",
        applicable_family_keys=(family_key,),
        safe_context=safe_context,
        family_key=family_key,
        focus_key=focus_key,
        strategy_key=normalized_strategy_key,
        primary_complete_result=primary_complete_result,
    )


def build_anatomy_localization_ai_request_command(
    *, task: Any, stage: Any
) -> XRayPromptCommand:
    """Build the minimal non-diagnostic context for one batch localization call."""

    snapshot = task.request_snapshot_json or {}
    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise PromptContractError("anatomy_localization_snapshot_v3_required")
    species = snapshot.get("species")
    if species not in {"cat", "dog"}:
        raise PromptContractError("xray_species_snapshot_invalid")
    ordered_image_refs = [
        {
            "image_id": item["image_id"],
            "series_id": item["series_id"],
            "sequence_no": item["sequence_no"],
            "projection": item["projection"],
            "series_manifest_sha256": item["series_manifest_sha256"],
        }
        for item in _v3_ordered_image_refs(snapshot=snapshot)
    ]
    resolved_manifest_sha256 = snapshot.get("resolved_manifest_sha256")
    if (
        not isinstance(resolved_manifest_sha256, str)
        or len(resolved_manifest_sha256) != 64
    ):
        raise PromptContractError("anatomy_localization_manifest_invalid")
    return XRayPromptCommand(
        prompt_kind="anatomy_localization",
        applicable_family_keys=(),
        safe_context={
            "task_id": task.id,
            "study_revision_id": stage.input_json["study_revision_id"],
            "species": species,
            "resolved_manifest_sha256": resolved_manifest_sha256,
            "ordered_image_refs": ordered_image_refs,
        },
    )


def build_xray_image_quality_ai_request_command(
    *, task: Any, stage: Any
) -> XRayPromptCommand:
    """Build minimal immutable context for one batch image-quality call."""

    snapshot = task.request_snapshot_json or {}
    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise PromptContractError("xray_image_quality_snapshot_v3_required")
    species = snapshot.get("species")
    if species not in {"cat", "dog"}:
        raise PromptContractError("xray_species_snapshot_invalid")
    ordered_image_refs = [
        {
            "image_id": item["image_id"],
            "sequence_no": item["sequence_no"],
            "declared_projection": item["projection"],
        }
        for item in _v3_ordered_image_refs(snapshot=snapshot)
    ]
    if not 2 <= len(ordered_image_refs) <= 5:
        raise PromptContractError("xray_image_quality_image_count_invalid")
    return XRayPromptCommand(
        prompt_kind="image_quality",
        applicable_family_keys=(),
        safe_context={
            "task_id": task.id,
            "study_revision_id": stage.input_json["study_revision_id"],
            "species": species,
            "ordered_image_refs": ordered_image_refs,
        },
    )


def build_study_screening_ai_request_command(
    *, task: Any, stage: Any
) -> XRayPromptCommand:
    """Build one StudyScreening call from frozen study and Quality facts."""

    snapshot = task.request_snapshot_json or {}
    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise PromptContractError("study_screening_snapshot_v3_required")
    species = snapshot.get("species")
    if species not in {"cat", "dog"}:
        raise PromptContractError("xray_species_snapshot_invalid")
    ordered_image_refs = _v3_ordered_image_refs(snapshot=snapshot)
    if not 2 <= len(ordered_image_refs) <= 5:
        raise PromptContractError("study_screening_image_count_invalid")
    quality_review = snapshot.get("quality_review")
    quality_results = (
        quality_review.get("result") if isinstance(quality_review, dict) else None
    )
    if not isinstance(quality_results, dict):
        raise PromptContractError("study_screening_quality_results_missing")
    safe_context = _base_context(
        task=task,
        stage=stage,
        snapshot=snapshot,
        prompt_mode="study_screening",
    )
    safe_context["resolved_manifest_sha256"] = snapshot.get("resolved_manifest_sha256")
    return XRayPromptCommand(
        prompt_kind="study_screening",
        applicable_family_keys=(),
        safe_context=safe_context,
        quality_results=dict(quality_results),
    )


def build_system_analysis_ai_request_command(
    *, task: Any, stage: Any
) -> XRayPromptCommand:
    """Build one SystemAnalysis call from frozen study and Quality facts."""

    snapshot = task.request_snapshot_json or {}
    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise PromptContractError("system_analysis_snapshot_v3_required")
    species = snapshot.get("species")
    if species not in {"cat", "dog"}:
        raise PromptContractError("xray_species_snapshot_invalid")
    ordered_image_refs = _v3_ordered_image_refs(snapshot=snapshot)
    if not 2 <= len(ordered_image_refs) <= 5:
        raise PromptContractError("system_analysis_image_count_invalid")
    quality_review = snapshot.get("quality_review")
    quality_results = (
        quality_review.get("result") if isinstance(quality_review, dict) else None
    )
    if not isinstance(quality_results, dict):
        raise PromptContractError("system_analysis_quality_results_missing")
    safe_context = _base_context(
        task=task,
        stage=stage,
        snapshot=snapshot,
        prompt_mode="system_analysis",
    )
    safe_context["resolved_manifest_sha256"] = snapshot.get("resolved_manifest_sha256")
    return XRayPromptCommand(
        prompt_kind="system_analysis",
        applicable_family_keys=(),
        safe_context=safe_context,
        quality_results=dict(quality_results),
    )


def build_report_generation_ai_request_command(
    *, task: Any, stage: Any
) -> XRayPromptCommand:
    """Build the zero-image report call from the frozen final decision."""

    snapshot = task.request_snapshot_json or {}
    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise PromptContractError("report_generation_snapshot_v3_required")
    stage_input = stage.input_json or {}
    previous_output = stage_input.get("previous_output")
    source_result_sha256 = stage_input.get("previous_output_sha256")
    if not isinstance(previous_output, dict):
        raise PromptContractError("report_generation_final_result_missing")
    final_medical_result = previous_output.get("complete_medical_result")
    if not isinstance(final_medical_result, dict):
        raise PromptContractError("report_generation_final_result_missing")
    if not isinstance(source_result_sha256, str) or len(source_result_sha256) != 64:
        raise PromptContractError("report_generation_source_sha_invalid")
    quality_review = snapshot.get("quality_review")
    quality_results = (
        quality_review.get("result") if isinstance(quality_review, dict) else None
    )
    if not isinstance(quality_results, dict):
        raise PromptContractError("report_generation_quality_results_missing")
    species = snapshot.get("species")
    if species not in {"cat", "dog"}:
        raise PromptContractError("xray_species_snapshot_invalid")
    return XRayPromptCommand(
        prompt_kind="report_generation",
        applicable_family_keys=(),
        safe_context={
            "task_id": task.id,
            "study_revision_id": stage_input.get("study_revision_id"),
            "species": species,
        },
        final_medical_result={
            "source_result_sha256": source_result_sha256,
            "final_medical_result": dict(final_medical_result),
        },
        quality_results=dict(quality_results),
    )


def _base_context(
    *,
    task: Any,
    stage: Any,
    snapshot: dict[str, Any],
    prompt_mode: str,
) -> dict[str, Any]:
    snapshot_version = snapshot.get("snapshot_contract_version")
    try:
        clinical_context = read_frozen_clinical_context(snapshot).payload
    except ClinicalContextContractError as exc:
        raise PromptContractError(str(exc)) from exc
    series = snapshot.get("series") or []
    if snapshot_version == TASK_REQUEST_SNAPSHOT_V3:
        ordered_image_refs = _v3_ordered_image_refs(snapshot=snapshot)
        view_positions = [item["projection"] for item in ordered_image_refs]
    else:
        ordered_image_refs = [
            {
                "series_ref": item.get("series_id"),
                "manifest_sha256": item.get("manifest_sha256"),
                "image_count": item.get("actual_image_count"),
            }
            for item in series
            if isinstance(item, dict)
        ]
        view_positions = snapshot.get("view_positions") or []
    if prompt_mode not in {
        "primary",
        "targeted",
        "study_screening",
        "system_analysis",
    }:
        raise PromptContractError("prompt_mode_invalid")
    species = snapshot.get("species")
    if snapshot_version in {TASK_REQUEST_SNAPSHOT_V2, TASK_REQUEST_SNAPSHOT_V3}:
        # New XRay snapshots must carry the caller-supplied, frozen species.
        # Never turn a missing/corrupted v2 value into an inferred fallback.
        if species not in {"cat", "dog"}:
            raise PromptContractError("xray_species_snapshot_invalid")
    elif not isinstance(species, str) or not species.strip():
        # Keep v1 frozen Task replay compatibility. New diagnose Tasks always
        # use the v2 branch above and therefore cannot reach this fallback.
        species = "unknown"
    context = {
        "task_id": task.id,
        "prompt_mode": prompt_mode,
        "study_revision_id": stage.input_json["study_revision_id"],
        "ordered_image_refs": ordered_image_refs,
        "species": species,
        "anatomy_regions": snapshot.get("anatomy_regions") or [],
        "view_positions": view_positions,
        "coverage": snapshot.get("coverage") or {},
        "technical_limitations": snapshot.get("technical_limitations") or [],
        "clinical_context_allowlist": clinical_context,
        "technical_evidence_available": bool(
            snapshot.get("technical_evidence_available", False)
        ),
    }
    pet_profile = snapshot.get("pet_profile")
    if isinstance(pet_profile, dict) and pet_profile:
        context["pet_profile"] = pet_profile
    return context


def _v3_ordered_image_refs(*, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        series = validate_frozen_study_series(
            snapshot.get("series"),
            resolved_manifest_sha256=snapshot.get("resolved_manifest_sha256"),
        )
    except ManifestContractError as exc:
        raise PromptContractError(str(exc)) from exc
    refs: list[dict[str, Any]] = []
    for series_item in series:
        for item in series_item["ordered_images"]:
            refs.append(
                {
                    "sequence_no": len(refs) + 1,
                    "series_id": series_item["series_id"],
                    "series_manifest_sha256": series_item["manifest_sha256"],
                    "image_id": item["image_id"],
                    "logical_image_key": item["logical_image_key"],
                    "image_version_no": item["image_version_no"],
                    "series_sequence_no": item["sequence_no"],
                    "projection": item["projection"],
                    "projection_provenance": item["projection_provenance"],
                    "sha256": item["sha256"],
                    "content_type": item["content_type"],
                }
            )
    return refs


__all__ = [
    "XRayPromptCommand",
    "build_anatomy_localization_ai_request_command",
    "build_primary_ai_request_command",
    "build_report_generation_ai_request_command",
    "build_study_screening_ai_request_command",
    "build_system_analysis_ai_request_command",
    "build_targeted_ai_request_command",
    "build_xray_image_quality_ai_request_command",
]
