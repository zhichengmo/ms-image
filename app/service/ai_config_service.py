from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.prompting import PromptCatalog, PromptCompiler, PromptContractError
from app.core.ai.prompting.contracts import (
    PRIMARY_FAMILY_ORDER,
    schema_asset_payload,
    sha256_json,
)
from app.core.pipeline import (
    StageRegistry,
    build_default_registry,
    compile_profile_contract,
)
from app.crud.ai_config_record import AIConfigRecordDal
from app.models.ai_config_record import AIConfigRecord
from app.models.imaging_base import new_opaque_id
from app.schemas.ai_config import AIConfigCreate, AIConfigResponse


class AIConfigServiceError(ValueError):
    pass


class AIConfigNotFoundError(AIConfigServiceError):
    pass


class AIConfigStateConflictError(AIConfigServiceError):
    pass


class AIConfigValidationError(AIConfigServiceError):
    pass


class AIConfigService:
    def __init__(self, db: AsyncSession, registry: StageRegistry | None = None):
        self.dal = AIConfigRecordDal(db)
        self.registry = registry or build_default_registry()

    @staticmethod
    def _response(value: AIConfigRecord) -> AIConfigResponse:
        prompt_bundle = value.prompt_bundle_json
        schema_bundle = value.schema_bundle_json
        return AIConfigResponse(
            id=value.id,
            config_key=value.config_key,
            version=value.version,
            activation_scope=value.activation_scope,
            scope_key=value.scope_key,
            activation_slot=value.activation_slot,
            modality_type=value.modality_type,
            task_type=value.task_type,
            capability_manifest_json=value.capability_manifest_json,
            compiled_pipeline_sha256=value.compiled_pipeline_sha256,
            stage_registry_contract_version=value.stage_registry_contract_version,
            provider_plan_json=value.provider_plan_json,
            budget_policy_json=value.budget_policy_json,
            prompt_catalog_revision=prompt_bundle["catalog_revision"],
            prompt_bundle_sha256=prompt_bundle["bundle_sha256"],
            schema_catalog_revision=schema_bundle["schema_catalog_revision"],
            schema_bundle_sha256=schema_bundle["bundle_sha256"],
            model_policy_json=value.model_policy_json,
            release_fingerprint=value.release_fingerprint,
            config_sha256=value.config_sha256,
            status=value.status,
            state_version=value.state_version,
            error_code=value.error_code,
            created_at=value.created_at,
            updated_at=value.updated_at,
        )

    @staticmethod
    def _slot(payload: AIConfigCreate) -> str:
        return (
            f"{payload.config_key}:{payload.activation_scope}:{payload.scope_key}:"
            f"{payload.modality_type}:{payload.task_type}"
        )

    def _compile(self, payload: AIConfigCreate) -> dict[str, Any]:
        if (
            payload.capability_manifest.get("provider_disabled") is not True
            or payload.provider_plan.get("enabled") is not False
        ):
            raise AIConfigValidationError("provider_disabled_required")
        try:
            compiled_pipeline, pipeline_sha = compile_profile_contract(
                payload.profile_key, self.registry
            )
            prompt_policy = self._normalize_prompt_policy(payload)
            catalog = PromptCatalog.target_xray(payload.prompt_catalog_revision)
            prompt_bundle = catalog.bundle_payload(prompt_policy=prompt_policy)
            model_policy = self._normalize_model_policy(payload.model_policy)
            PromptCompiler(
                catalog,
                max_prompt_chars=model_policy["max_prompt_chars"],
                prompt_policy=prompt_policy,
            )
        except PromptContractError as exc:
            raise AIConfigValidationError(str(exc)) from exc
        schema_bundle = {
            "bundle_version": "xray-schema-bundle.v1",
            "schema_catalog_revision": payload.schema_catalog_revision,
            "language": "zh-CN",
            "complete_medical_result": schema_asset_payload(catalog.schema),
        }
        schema_bundle["bundle_sha256"] = sha256_json(schema_bundle)
        config_body = {
            "config_key": payload.config_key,
            "version": payload.version,
            "activation_scope": payload.activation_scope,
            "scope_key": payload.scope_key,
            "modality_type": payload.modality_type,
            "task_type": payload.task_type,
            "capability_manifest": payload.capability_manifest,
            "compiled_pipeline": compiled_pipeline,
            "compiled_pipeline_sha256": pipeline_sha,
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "prompt_bundle": prompt_bundle,
            "schema_bundle": schema_bundle,
            "model_policy": model_policy,
            "provider_plan": payload.provider_plan,
            "budget_policy": payload.budget_policy,
        }
        config_sha256 = sha256_json(config_body)
        release_fingerprint = sha256_json(
            {
                "config_sha256": config_sha256,
                "prompt_bundle_sha256": prompt_bundle["bundle_sha256"],
                "schema_bundle_sha256": schema_bundle["bundle_sha256"],
                "compiled_pipeline_sha256": pipeline_sha,
                "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
                "prompt_runtime_contract": "xray-prompt-runtime.v1",
            }
        )
        return {
            "compiled_pipeline": compiled_pipeline,
            "compiled_pipeline_sha256": pipeline_sha,
            "prompt_bundle": prompt_bundle,
            "schema_bundle": schema_bundle,
            "model_policy": model_policy,
            "config_sha256": config_sha256,
            "release_fingerprint": release_fingerprint,
        }

    def _normalize_prompt_policy(self, payload: AIConfigCreate) -> dict[str, Any]:
        raw = dict(payload.prompt_policy)
        families = raw.get("primary_family_keys") or list(PRIMARY_FAMILY_ORDER)
        if not isinstance(families, list) or any(
            item not in PRIMARY_FAMILY_ORDER for item in families
        ):
            raise AIConfigValidationError("prompt_policy_primary_family_invalid")
        targeted = raw.get("targeted") or {}
        if not isinstance(targeted, dict):
            raise AIConfigValidationError("prompt_policy_targeted_invalid")
        enabled = payload.profile_key == "xray_targeted_review_v1"
        if bool(targeted.get("enabled", False)) != enabled:
            raise AIConfigValidationError("prompt_policy_targeted_profile_mismatch")
        focus_keys = targeted.get("focus_keys") or []
        strategy_keys = targeted.get("strategy_keys") or []
        if not all(
            isinstance(item, str) and item for item in focus_keys + strategy_keys
        ):
            raise AIConfigValidationError("prompt_policy_targeted_invalid")
        if enabled and not focus_keys:
            raise AIConfigValidationError("targeted_focus_policy_required")
        return {
            "language": "zh-CN",
            "primary_family_keys": list(families),
            "allow_technical_evidence": bool(
                raw.get("allow_technical_evidence", False)
            ),
            "targeted": {
                "enabled": enabled,
                "focus_keys": list(focus_keys),
                "strategy_keys": list(strategy_keys),
            },
        }

    @staticmethod
    def _normalize_model_policy(value: dict[str, Any]) -> dict[str, Any]:
        policy = {
            "requested_model": str(value.get("requested_model") or "disabled"),
            "max_prompt_chars": int(value.get("max_prompt_chars") or 16000),
            "max_input_tokens": int(value.get("max_input_tokens") or 8192),
            "max_output_tokens": int(value.get("max_output_tokens") or 2048),
            "max_images": int(value.get("max_images") or 32),
            "max_calls": int(value.get("max_calls") or 1),
            "require_actual_model": bool(value.get("require_actual_model", False)),
        }
        if (
            not policy["requested_model"]
            or policy["max_prompt_chars"] <= 0
            or policy["max_input_tokens"] <= 0
            or policy["max_output_tokens"] <= 0
            or policy["max_images"] <= 0
            or policy["max_calls"] <= 0
        ):
            raise AIConfigValidationError("model_policy_invalid")
        return policy

    async def create(self, payload: AIConfigCreate) -> AIConfigResponse:
        compiled = self._compile(payload)
        values = {
            "id": new_opaque_id(),
            "config_key": payload.config_key,
            "version": payload.version,
            "activation_scope": payload.activation_scope,
            "scope_key": payload.scope_key,
            "activation_slot": None,
            "modality_type": payload.modality_type,
            "task_type": payload.task_type,
            "capability_manifest_json": payload.capability_manifest,
            "compiled_pipeline_json": compiled["compiled_pipeline"],
            "compiled_pipeline_sha256": compiled["compiled_pipeline_sha256"],
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "prompt_bundle_json": compiled["prompt_bundle"],
            "schema_bundle_json": compiled["schema_bundle"],
            "model_policy_json": compiled["model_policy"],
            "provider_plan_json": payload.provider_plan,
            "budget_policy_json": payload.budget_policy,
            "release_fingerprint": compiled["release_fingerprint"],
            "config_sha256": compiled["config_sha256"],
            "status": "draft",
            "state_version": 0,
        }
        created = await self.dal.create_idempotent(values)
        if created is None:
            raise AIConfigStateConflictError("ai_config_create_conflict")
        return self._response(created)

    async def validate(self, config_id: str, expected_version: int) -> AIConfigResponse:
        item = await self.dal.get_by_id(config_id)
        if item is None:
            raise AIConfigNotFoundError("ai_config_not_found")
        if item.status != "draft" or item.state_version != expected_version:
            raise AIConfigStateConflictError("ai_config_validate_conflict")
        updated = await self.dal.cas_update(
            config_id=item.id,
            expected_version=expected_version,
            values={"status": "validated", "error_code": None},
        )
        if updated is None:
            raise AIConfigStateConflictError("ai_config_validate_conflict")
        return self._response(updated)

    async def activate(self, config_id: str, expected_version: int) -> AIConfigResponse:
        item = await self.dal.get_by_id(config_id)
        if item is None:
            raise AIConfigNotFoundError("ai_config_not_found")
        if item.status == "active" and item.state_version == expected_version + 1:
            return self._response(item)
        if item.status != "validated" or item.state_version != expected_version:
            raise AIConfigStateConflictError("ai_config_activate_conflict")
        if (
            item.compiled_pipeline_json.get("profile_key") == "xray_targeted_review_v1"
            and item.activation_scope != "experiment"
        ):
            raise AIConfigValidationError("targeted_profile_experiment_scope_required")
        slot = (
            f"{item.config_key}:{item.activation_scope}:{item.scope_key}:"
            f"{item.modality_type}:{item.task_type}"
        )
        current = await self.dal.get_active(slot)
        if current is not None and current.id != item.id:
            retired = await self.dal.cas_update(
                config_id=current.id,
                expected_version=current.state_version,
                values={"status": "retired", "activation_slot": None},
            )
            if retired is None:
                raise AIConfigStateConflictError("ai_config_active_slot_conflict")
        updated = await self.dal.cas_update(
            config_id=item.id,
            expected_version=expected_version,
            values={"status": "active", "activation_slot": slot},
        )
        if updated is None:
            raise AIConfigStateConflictError("ai_config_activate_conflict")
        return self._response(updated)

    async def get_active(
        self, *, config_key: str, modality_type: str, task_type: str
    ) -> AIConfigResponse:
        item = await self.dal.get_active(
            f"{config_key}:global:global:{modality_type}:{task_type}"
        )
        if item is None:
            raise AIConfigNotFoundError("ai_config_active_not_found")
        return self._response(item)


__all__ = [
    "AIConfigNotFoundError",
    "AIConfigService",
    "AIConfigServiceError",
    "AIConfigStateConflictError",
    "AIConfigValidationError",
]
