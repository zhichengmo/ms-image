"""Deterministic Chinese Prompt compiler for target XRay primary/targeted calls."""

from __future__ import annotations

from typing import Any

from .catalog import PromptCatalog
from .contracts import (
    PRIMARY_FAMILY_ORDER,
    CompiledPrompt,
    PromptContractError,
    canonical_json,
    sha256_text,
)
from .leakage import validate_primary_context, validate_targeted_context


class PromptCompiler:
    def __init__(
        self,
        catalog: PromptCatalog,
        *,
        max_prompt_chars: int,
        prompt_policy: dict[str, Any] | None = None,
    ):
        if max_prompt_chars <= 0:
            raise PromptContractError("prompt_budget_invalid")
        self.catalog = catalog
        self.max_prompt_chars = max_prompt_chars
        self.prompt_policy = self._normalize_policy(prompt_policy or {})

    @staticmethod
    def _normalize_policy(value: dict[str, Any]) -> dict[str, Any]:
        families = value.get("primary_family_keys") or list(PRIMARY_FAMILY_ORDER)
        if not isinstance(families, list) or any(
            item not in PRIMARY_FAMILY_ORDER for item in families
        ):
            raise PromptContractError("prompt_policy_primary_family_invalid")
        targeted = value.get("targeted") or {}
        if not isinstance(targeted, dict):
            raise PromptContractError("prompt_policy_targeted_invalid")
        focus_keys = targeted.get("focus_keys") or []
        strategy_keys = targeted.get("strategy_keys") or []
        if not all(isinstance(item, str) for item in focus_keys + strategy_keys):
            raise PromptContractError("prompt_policy_targeted_invalid")
        return {
            "primary_family_keys": tuple(families),
            "allow_technical_evidence": bool(
                value.get("allow_technical_evidence", False)
            ),
            "targeted": {
                "enabled": bool(targeted.get("enabled", False)),
                "focus_keys": tuple(focus_keys),
                "strategy_keys": tuple(strategy_keys),
            },
        }

    def compile_primary(
        self,
        *,
        applicable_family_keys: tuple[str, ...],
        safe_context: dict[str, Any],
        include_technical_evidence: bool = False,
    ) -> CompiledPrompt:
        validate_primary_context(safe_context)
        unknown = set(applicable_family_keys) - set(PRIMARY_FAMILY_ORDER)
        not_allowed = set(applicable_family_keys) - set(
            self.prompt_policy["primary_family_keys"]
        )
        if (
            unknown
            or not_allowed
            or len(set(applicable_family_keys)) != len(applicable_family_keys)
        ):
            raise PromptContractError("primary_family_selection_invalid")
        if (
            include_technical_evidence
            and not self.prompt_policy["allow_technical_evidence"]
        ):
            raise PromptContractError("technical_evidence_not_allowed")
        assets = [self.catalog.asset(prompt_role="joint_primary_base")]
        selected_families = tuple(
            family
            for family in PRIMARY_FAMILY_ORDER
            if family in applicable_family_keys
        )
        assets.extend(
            self.catalog.asset(
                prompt_role="joint_primary_module",
                family_key=family,
                eligibility="primary",
            )
            for family in selected_families
        )
        if include_technical_evidence:
            assets.append(
                self.catalog.asset(
                    prompt_role="technical_evidence",
                    prompt_key="technical_evidence.source_lineage",
                    eligibility="online",
                )
            )
        return self._compile(
            prompt_kind="primary",
            assets=tuple(assets),
            safe_context=safe_context,
            selected_family_keys=selected_families,
            selected_focus_key=None,
            selected_strategy_key=None,
            primary_result=None,
        )

    def compile_targeted(
        self,
        *,
        family_key: str,
        focus_key: str,
        strategy_key: str | None,
        safe_context: dict[str, Any],
        primary_complete_result: dict[str, Any],
        include_technical_evidence: bool = False,
    ) -> CompiledPrompt:
        validate_targeted_context(safe_context)
        if (
            safe_context.get("selected_family_key") != family_key
            or safe_context.get("selected_focus_key") != focus_key
        ):
            raise PromptContractError("targeted_context_selection_mismatch")
        if safe_context.get("selected_strategy_key") != strategy_key:
            raise PromptContractError("targeted_context_strategy_mismatch")
        assets = [
            self.catalog.asset(
                prompt_role="targeted_focus",
                prompt_key="targeted_focus.base",
                eligibility="targeted_experimental",
            ),
            self.catalog.asset(
                prompt_role="targeted_focus",
                family_key=family_key,
                focus_key=focus_key,
                eligibility="targeted_experimental",
            ),
        ]
        if strategy_key is not None:
            assets.append(
                self.catalog.asset(
                    prompt_role="review_strategy",
                    strategy_key=strategy_key,
                    eligibility="targeted_experimental",
                )
            )
        if include_technical_evidence:
            assets.append(
                self.catalog.asset(
                    prompt_role="technical_evidence",
                    prompt_key="technical_evidence.source_lineage",
                    eligibility="online",
                )
            )
        return self._compile(
            prompt_kind="targeted",
            assets=tuple(assets),
            safe_context=safe_context,
            selected_family_keys=(family_key,),
            selected_focus_key=focus_key,
            selected_strategy_key=strategy_key,
            primary_result=primary_complete_result,
        )

    def _compile(
        self,
        *,
        prompt_kind: str,
        assets: tuple[Any, ...],
        safe_context: dict[str, Any],
        selected_family_keys: tuple[str, ...],
        selected_focus_key: str | None,
        selected_strategy_key: str | None,
        primary_result: dict[str, Any] | None,
    ) -> CompiledPrompt:
        schema = self.catalog.schema
        sections = [asset.content for asset in assets]
        sections.append(
            "输出合同：必须返回符合 COMPLETE_MEDICAL_RESULT_SCHEMA 的 JSON；"
            "JSON 字段名必须保持英文稳定；描述、原因和限制必须使用中文。"
        )
        if primary_result is not None:
            sections.append(
                "PRIMARY_COMPLETE_RESULT_JSON=" + canonical_json(primary_result)
            )
        sections.append("SAFE_STUDY_CONTEXT_JSON=" + canonical_json(safe_context))
        rendered_text = "\n\n".join(sections)
        if len(rendered_text) > self.max_prompt_chars:
            raise PromptContractError("prompt_budget_exceeded")
        selected_prompt_keys = tuple(asset.prompt_key for asset in assets)
        return CompiledPrompt(
            prompt_kind=prompt_kind,
            rendered_text=rendered_text,
            rendered_sha256=sha256_text(rendered_text),
            context_sha256=sha256_text(canonical_json(safe_context)),
            schema_sha256=schema.schema_sha256,
            selected_prompt_keys=selected_prompt_keys,
            selected_family_keys=selected_family_keys,
            selected_focus_key=selected_focus_key,
            selected_strategy_key=selected_strategy_key,
            estimated_tokens=max(1, len(rendered_text) // 4),
            bundle_sha256=self.catalog.build_bundle().bundle_sha256,
        )


__all__ = ["PromptCompiler"]
