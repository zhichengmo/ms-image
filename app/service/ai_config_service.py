from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline import StageRegistry, build_default_registry, compile_profile_contract
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
        return AIConfigResponse.model_validate(value)

    @staticmethod
    def _slot(payload: AIConfigCreate) -> str:
        return f"{payload.config_key}:global:global:{payload.modality_type}:{payload.task_type}"

    def _compile(self, payload: AIConfigCreate) -> tuple[dict[str, Any], str]:
        if payload.capability_manifest.get("provider_disabled") is not True or payload.provider_plan.get("enabled") is not False:
            raise AIConfigValidationError("provider_disabled_required")
        return compile_profile_contract(payload.profile_key, self.registry)

    async def create(self, payload: AIConfigCreate) -> AIConfigResponse:
        compiled, digest = self._compile(payload)
        values = {"id": new_opaque_id(), "config_key": payload.config_key, "version": payload.version, "activation_scope": "global", "scope_key": "global", "activation_slot": None, "modality_type": payload.modality_type, "task_type": payload.task_type, "capability_manifest_json": payload.capability_manifest, "compiled_pipeline_json": compiled, "compiled_pipeline_sha256": digest, "stage_registry_contract_version": self.registry.CONTRACT_VERSION, "provider_plan_json": payload.provider_plan, "budget_policy_json": payload.budget_policy, "status": "draft", "state_version": 0}
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
        slot = f"{item.config_key}:global:global:{item.modality_type}:{item.task_type}"
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

    async def get_active(self, *, config_key: str, modality_type: str, task_type: str) -> AIConfigResponse:
        item = await self.dal.get_active(f"{config_key}:global:global:{modality_type}:{task_type}")
        if item is None:
            raise AIConfigNotFoundError("ai_config_active_not_found")
        return self._response(item)
