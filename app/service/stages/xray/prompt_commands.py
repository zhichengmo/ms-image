"""Pure XRay Prompt command construction from frozen Task/Stage facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.ai.prompting import CompiledPrompt, PromptCompiler, PromptContractError


@dataclass(frozen=True)
class XRayPromptCommand:
    prompt_kind: str
    applicable_family_keys: tuple[str, ...]
    safe_context: dict[str, Any]
    family_key: str | None = None
    focus_key: str | None = None
    strategy_key: str | None = None
    primary_complete_result: dict[str, Any] | None = None

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
    safe_context = _base_context(task=task, stage=stage, snapshot=snapshot)
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


def build_targeted_ai_request_command(*, task: Any, stage: Any) -> XRayPromptCommand:
    snapshot = task.request_snapshot_json or {}
    previous_output = (stage.input_json or {}).get("previous_output") or {}
    family_key = (stage.input_json or {}).get("selected_family_key")
    focus_key = (stage.input_json or {}).get("selected_focus_key")
    strategy_key = (stage.input_json or {}).get("selected_strategy_key")
    if not isinstance(family_key, str) or not isinstance(focus_key, str):
        raise PromptContractError("targeted_prompt_selection_missing")
    safe_context = {
        **_base_context(task=task, stage=stage, snapshot=snapshot),
        "primary_complete_result": previous_output,
        "selected_family_key": family_key,
        "selected_focus_key": focus_key,
        "selected_strategy_key": strategy_key
        if isinstance(strategy_key, str)
        else None,
        "source_finding_ids": (stage.input_json or {}).get("source_finding_ids") or [],
        "coverage_proof": (stage.input_json or {}).get("coverage_proof") or {},
        "route_reason_codes": (stage.input_json or {}).get("route_reason_codes") or [],
    }
    return XRayPromptCommand(
        prompt_kind="targeted",
        applicable_family_keys=(family_key,),
        safe_context=safe_context,
        family_key=family_key,
        focus_key=focus_key,
        strategy_key=strategy_key if isinstance(strategy_key, str) else None,
        primary_complete_result=previous_output,
    )


def _base_context(*, task: Any, stage: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    series = snapshot.get("series") or []
    ordered_image_refs = [
        {
            "series_ref": item.get("series_id"),
            "manifest_sha256": item.get("manifest_sha256"),
            "image_count": item.get("actual_image_count"),
        }
        for item in series
        if isinstance(item, dict)
    ]
    return {
        "task_id": task.id,
        "study_revision_id": stage.input_json["study_revision_id"],
        "ordered_image_refs": ordered_image_refs,
        "species": snapshot.get("species") or "未知",
        "anatomy_regions": snapshot.get("anatomy_regions") or [],
        "view_positions": snapshot.get("view_positions") or [],
        "coverage": snapshot.get("coverage") or {},
        "technical_limitations": snapshot.get("technical_limitations") or [],
        "clinical_context_allowlist": snapshot.get("clinical_context_allowlist") or {},
        "technical_evidence_available": bool(
            snapshot.get("technical_evidence_available", False)
        ),
    }


__all__ = [
    "XRayPromptCommand",
    "build_primary_ai_request_command",
    "build_targeted_ai_request_command",
]
