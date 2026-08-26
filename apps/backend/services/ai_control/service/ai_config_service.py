"""Control-plane lifecycle for the immutable ``ai-config.v2`` runtime snapshot.

The service is deliberately the only owner of Config state transitions.  It
keeps legacy v1 rows readable for historical Task execution, but all creation
and lifecycle write commands in this module target only ``ai-config.v2``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.config_contract import (
    activation_slot_sha256,
    is_v2_config,
    legacy_activation_slot,
)
from apps.backend.core.async_db import session_factory
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.pipeline import StageRegistry, build_default_registry
from apps.backend.crud.ai_api_connection import AIAPIConnectionDal
from apps.backend.crud.ai_config_record import AIConfigRecordDal
from apps.backend.crud.ai_model_pool import AIModelPoolDal
from apps.backend.crud.ai_prompt_template import AIPromptTemplateDal
from apps.backend.models.ai_config_record import AIConfigRecord
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_config import (
    AIConfigActivateRequest,
    AIConfigCompilePreview,
    AIConfigCreate,
    AIConfigResponse,
    AIConfigRollbackRequest,
    AIConfigStateRequest,
)
from apps.backend.schemas.ai_control import PageResult, RetireCommandRequest
from apps.backend.services.ai_control.service.config_compiler import (
    AIConfigCompiler,
    CompiledAIConfig,
)
from apps.backend.services.ai_control.service.control_audit_service import (
    AIControlAuditService,
)
from apps.backend.services.ai_control.service.errors import (
    AIControlNotFoundError,
    AIControlStateConflictError,
    AIControlValidationError,
)

# These aliases preserve the old error import surface while routing all new
# errors through the shared control-plane mapping.
AIConfigNotFoundError = AIControlNotFoundError
AIConfigStateConflictError = AIControlStateConflictError
AIConfigValidationError = AIControlValidationError


class _RejectedValidationReplayRequired(RuntimeError):
    """Internal marker used to roll back an isolated rejected-validation write."""


class AIConfigService:
    RESOURCE_TYPE = "ai_config"

    def __init__(self, db: AsyncSession, registry: StageRegistry | None = None):
        self.dal = AIConfigRecordDal(db)
        self.prompt_dal = AIPromptTemplateDal(db)
        self.pool_dal = AIModelPoolDal(db)
        self.connection_dal = AIAPIConnectionDal(db)
        self.audit = AIControlAuditService(db)
        self.registry = registry or build_default_registry()
        self.compiler = AIConfigCompiler(self.registry)

    @staticmethod
    def _safe_mapping(value: Any) -> dict[str, Any] | None:
        """Return a recursively redacted compatibility summary for v1 JSON."""
        if not isinstance(value, Mapping):
            return None
        forbidden = (
            "secret",
            "token",
            "authorization",
            "password",
            "api_key",
            "credential",
        )

        def walk(item: Any) -> Any:
            if isinstance(item, Mapping):
                return {
                    str(key): walk(nested)
                    for key, nested in item.items()
                    if not any(marker in str(key).casefold() for marker in forbidden)
                }
            if isinstance(item, list):
                return [walk(nested) for nested in item]
            return item

        return walk(value)

    @classmethod
    def _response(cls, value: AIConfigRecord) -> AIConfigResponse:
        prompt_bundle = value.prompt_bundle_json or {}
        schema_bundle = value.schema_bundle_json or {}
        prompt_revision = (
            prompt_bundle.get("catalog_revision")
            if isinstance(prompt_bundle, Mapping)
            else None
        )
        prompt_sha = (
            prompt_bundle.get("bundle_sha256")
            if isinstance(prompt_bundle, Mapping)
            else None
        )
        schema_revision = (
            schema_bundle.get("schema_catalog_revision")
            if isinstance(schema_bundle, Mapping)
            else None
        )
        schema_sha = (
            schema_bundle.get("bundle_sha256")
            if isinstance(schema_bundle, Mapping)
            else None
        )
        return AIConfigResponse(
            id=value.id,
            config_key=value.config_key,
            version=value.version,
            name=value.name,
            config_contract_version=value.config_contract_version,
            modality_type=value.modality_type,
            task_type=value.task_type,
            profile_key=value.profile_key,
            activation_scope=value.activation_scope,
            scope_key=value.scope_key,
            activation_slot=value.activation_slot,
            prompt_template_id=value.prompt_template_id,
            prompt_key=value.prompt_key,
            prompt_version=value.prompt_version,
            prompt_content_sha256=value.prompt_content_sha256,
            prompt_message_contract_json=value.prompt_message_contract_json,
            prompt_source_receipt_sha256=value.prompt_source_receipt_sha256,
            model_pool_id=value.model_pool_id,
            model_pool_key=value.model_pool_key,
            model_pool_version=value.model_pool_version,
            model_snapshot_sha256=value.model_snapshot_sha256,
            output_schema_sha256=value.output_schema_sha256,
            gateway_profile_json=value.gateway_profile_json,
            capability_manifest_json=value.capability_manifest_json,
            compiled_pipeline_sha256=value.compiled_pipeline_sha256,
            stage_registry_contract_version=value.stage_registry_contract_version,
            budget_policy_json=value.budget_policy_json,
            release_fingerprint=value.release_fingerprint,
            config_sha256=value.config_sha256,
            status=value.status,
            state_version=value.state_version,
            error_code=value.error_code,
            validated_at=value.validated_at,
            activated_at=value.activated_at,
            retired_at=value.retired_at,
            created_by_id=value.created_by_id,
            updated_by_id=value.updated_by_id,
            created_at=value.created_at,
            updated_at=value.updated_at,
            prompt_catalog_revision=prompt_revision,
            prompt_bundle_sha256=prompt_sha,
            schema_catalog_revision=schema_revision,
            schema_bundle_sha256=schema_sha,
            model_policy_json=cls._safe_mapping(value.model_policy_json),
            provider_plan_json=cls._safe_mapping(value.provider_plan_json),
        )

    async def _replay_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIConfigRecord | None:
        """Fast-path replay from this request transaction."""
        audit = await self.audit.find_command(
            request_id=request_id,
            resource_type=self.RESOURCE_TYPE,
            action_type=action_type,
        )
        if audit is None:
            return None
        if audit.result_type != "succeeded":
            raise AIControlValidationError(
                audit.error_code or "ai_config_command_rejected"
            )
        item = await self.dal.get_by_id(audit.resource_id)
        if item is None:
            raise AIControlStateConflictError("ai_control_audit_resource_missing")
        return item

    async def _replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIConfigRecord | None:
        """Read a previously committed command in a fresh transaction snapshot.

        A duplicate command can lose an insert/CAS/audit uniqueness race while
        its original request transaction cannot yet observe the first commit.
        Replaying through a separate session preserves the Audit idempotency
        contract without reapplying the business mutation.
        """
        async with session_factory() as replay_db:
            replay_audit = AIControlAuditService(replay_db)
            audit = await replay_audit.find_command(
                request_id=request_id,
                resource_type=self.RESOURCE_TYPE,
                action_type=action_type,
            )
            if audit is None:
                return None
            if audit.result_type != "succeeded":
                raise AIControlValidationError(
                    audit.error_code or "ai_config_command_rejected"
                )
            item = await AIConfigRecordDal(replay_db).get_by_id(audit.resource_id)
            if item is None:
                raise AIControlStateConflictError("ai_control_audit_resource_missing")
            return item

    async def _rollback_and_replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIConfigRecord | None:
        """Undo local business changes before returning another command's replay."""
        await self.dal.db.rollback()
        return await self._replay_committed_or_none(
            request_id=request_id, action_type=action_type
        )

    @staticmethod
    def _source_from_create(payload: AIConfigCreate) -> dict[str, Any]:
        return payload.model_dump(mode="json")

    @staticmethod
    def _source_from_config(config: AIConfigRecord) -> dict[str, Any]:
        return {
            "config_key": config.config_key,
            "version": config.version,
            "name": config.name,
            "modality_type": config.modality_type,
            "task_type": config.task_type,
            "profile_key": config.profile_key,
            "activation_scope": config.activation_scope,
            "scope_key": config.scope_key,
            "prompt_template_id": config.prompt_template_id,
            "model_pool_id": config.model_pool_id,
            "budget_policy_json": config.budget_policy_json,
        }

    async def _source_rows(
        self,
        *,
        prompt_template_id: str,
        model_pool_id: str,
    ) -> tuple[Any, Any, list[Any]]:
        prompt = await self.prompt_dal.get_by_id(prompt_template_id)
        if prompt is None:
            raise AIControlNotFoundError("ai_prompt_template_not_found")
        pool = await self.pool_dal.get_by_id(model_pool_id)
        if pool is None:
            raise AIControlNotFoundError("ai_model_pool_not_found")
        lane_plan = pool.lane_plan_json
        lanes = lane_plan.get("lanes") if isinstance(lane_plan, Mapping) else None
        if not isinstance(lanes, list):
            raise AIControlValidationError("config_pool_lane_contract_invalid")
        connection_ids = [
            item.get("connection_id")
            for item in lanes
            if isinstance(item, Mapping) and isinstance(item.get("connection_id"), str)
        ]
        connections: list[Any] = []
        for connection_id in connection_ids:
            connection = await self.connection_dal.get_by_id(connection_id)
            if connection is None:
                raise AIControlNotFoundError("ai_api_connection_not_found")
            connections.append(connection)
        return prompt, pool, connections

    async def _compile(
        self,
        *,
        source: Mapping[str, Any],
        require_validated_sources: bool,
    ) -> CompiledAIConfig:
        prompt, pool, connections = await self._source_rows(
            prompt_template_id=str(source["prompt_template_id"]),
            model_pool_id=str(source["model_pool_id"]),
        )
        return self.compiler.compile(
            source=source,
            prompt=prompt,
            pool=pool,
            connections=connections,
            require_validated_sources=require_validated_sources,
        )

    @staticmethod
    def _assert_compilation_matches(
        *, config: AIConfigRecord, compiled: CompiledAIConfig
    ) -> None:
        for field, expected in compiled.values.items():
            if field in {"activation_slot"}:
                continue
            if getattr(config, field) != expected:
                raise AIControlValidationError("config_frozen_source_drift")

    async def _verify_v2(
        self,
        *,
        config: AIConfigRecord,
        require_validated_sources: bool,
    ) -> None:
        if not is_v2_config(config):
            raise AIControlStateConflictError("ai_config_v2_required")
        self.compiler.verify_frozen_integrity(config)
        compiled = await self._compile(
            source=self._source_from_config(config),
            require_validated_sources=require_validated_sources,
        )
        self._assert_compilation_matches(config=config, compiled=compiled)

    async def _has_committed_rejected_validation(
        self, *, request_id: str, resource_id: str
    ) -> bool:
        """Check a duplicate rejected validate command in a fresh snapshot."""
        async with session_factory() as replay_db:
            audit = await AIControlAuditService(replay_db).find_command(
                request_id=request_id,
                resource_type=self.RESOURCE_TYPE,
                action_type="validate",
            )
            return (
                audit is not None
                and audit.result_type == "rejected"
                and audit.resource_id == resource_id
            )

    async def _mark_rejected_validation(
        self,
        *,
        config: AIConfigRecord,
        payload: AIConfigStateRequest,
        actor: ControlPlaneContext,
        error_code: str,
    ) -> None:
        """Atomically persist Config validation failure and its rejected audit.

        The endpoint's request transaction is rolled back for a validation
        response.  This short independent transaction deliberately owns both
        the stable error-code CAS and the audit insert.  On a duplicate audit
        key it rolls back its own CAS before replaying the first durable result.
        """
        stable_error_code = error_code[:80]
        replay_required = False
        try:
            async with session_factory.begin() as rejected_db:
                rejected_dal = AIConfigRecordDal(rejected_db)
                rejected_audit = AIControlAuditService(rejected_db)
                updated = await rejected_dal.cas_update(
                    config_id=config.id,
                    expected_version=payload.expected_state_version,
                    values={
                        "error_code": stable_error_code,
                        "updated_by_id": actor.subject_id,
                    },
                )
                if updated is None:
                    replay_required = True
                else:
                    audit = await rejected_audit.append_rejected(
                        resource_type=self.RESOURCE_TYPE,
                        resource_id=config.id,
                        resource_key=config.config_key,
                        action_type="validate",
                        request_id=payload.request_id,
                        actor=actor,
                        before_sha256=config.config_sha256,
                        error_code=stable_error_code,
                    )
                    if audit is not None:
                        return
                    raise _RejectedValidationReplayRequired
        except _RejectedValidationReplayRequired:
            replay_required = True
        if replay_required and await self._has_committed_rejected_validation(
            request_id=payload.request_id,
            resource_id=config.id,
        ):
            return
        raise AIControlStateConflictError("ai_config_validate_conflict")

    async def compile_preview(
        self, *, payload: AIConfigCreate
    ) -> AIConfigCompilePreview:
        compiled = await self._compile(
            source=self._source_from_create(payload),
            require_validated_sources=True,
        )
        return AIConfigCompilePreview(**compiled.preview())

    async def create(
        self, *, payload: AIConfigCreate, actor: ControlPlaneContext
    ) -> AIConfigResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="create"
        )
        if replay is not None:
            return self._response(replay)
        existing = await self.dal.get_by_key_version(
            config_key=payload.config_key, version=payload.version
        )
        if existing is not None:
            raise AIControlStateConflictError("ai_config_key_version_exists")
        compiled = await self._compile(
            source=self._source_from_create(payload),
            require_validated_sources=True,
        )
        values = {
            **compiled.values,
            "id": new_opaque_id(),
            "status": "draft",
            "state_version": 0,
            "error_code": None,
            "validated_at": None,
            "activated_at": None,
            "retired_at": None,
            "created_by_id": actor.subject_id,
            "updated_by_id": actor.subject_id,
            # New v2 Configs never write legacy bundles.
            "prompt_bundle_json": None,
            "schema_bundle_json": None,
            "model_policy_json": None,
            "provider_plan_json": None,
        }
        item = await self.dal.create_idempotent(values)
        if item is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_config_create_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=item.id,
            resource_key=item.config_key,
            action_type="create",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=None,
            after_sha256=item.config_sha256,
            changed_fields=["immutable_snapshot", "status"],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(item)

    async def detail(self, *, config_id: str) -> AIConfigResponse:
        item = await self.dal.get_by_id(config_id)
        if item is None:
            raise AIControlNotFoundError("ai_config_not_found")
        return self._response(item)

    async def page(
        self, *, page: int, limit: int, config_key: str | None, status: str | None
    ) -> PageResult[AIConfigResponse]:
        items, total = await self.dal.page(
            page=page,
            limit=limit,
            config_key=config_key,
            status=status,
        )
        return PageResult(
            data=[self._response(item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )

    async def get_active(
        self,
        *,
        config_key: str,
        modality_type: str,
        task_type: str,
        activation_scope: str = "global",
        scope_key: str = "global",
    ) -> AIConfigResponse:
        slot = activation_slot_sha256(
            config_key=config_key,
            modality_type=modality_type,
            task_type=task_type,
            activation_scope=activation_scope,
            scope_key=scope_key,
        )
        item = await self.dal.get_active(slot)
        if item is None:
            legacy_slot = legacy_activation_slot(
                config_key=config_key,
                modality_type=modality_type,
                task_type=task_type,
                activation_scope=activation_scope,
                scope_key=scope_key,
            )
            item = await self.dal.get_active(legacy_slot)
            if item is not None and is_v2_config(item):
                raise AIControlStateConflictError("ai_config_v2_legacy_slot_invalid")
        if item is None:
            raise AIControlNotFoundError("ai_config_active_not_found")
        return self._response(item)

    async def validate(
        self, *, payload: AIConfigStateRequest, actor: ControlPlaneContext
    ) -> AIConfigResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="validate"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_config_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError("ai_config_validate_draft_required")
        try:
            await self._verify_v2(config=item, require_validated_sources=True)
        except AIControlValidationError as exc:
            await self._mark_rejected_validation(
                config=item,
                payload=payload,
                actor=actor,
                error_code=str(exc),
            )
            raise
        updated = await self.dal.cas_update(
            config_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "status": "validated",
                "error_code": None,
                "validated_at": datetime.utcnow(),
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="validate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_config_validate_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.config_key,
            action_type="validate",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.config_sha256,
            after_sha256=updated.config_sha256,
            changed_fields=["status", "error_code", "validated_at"],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="validate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def _current_active_for(
        self, *, config: AIConfigRecord
    ) -> tuple[AIConfigRecord | None, str]:
        slot = activation_slot_sha256(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
        )
        current = await self.dal.get_active(slot)
        if current is None:
            legacy_slot = legacy_activation_slot(
                config_key=config.config_key,
                modality_type=config.modality_type,
                task_type=config.task_type,
                activation_scope=config.activation_scope,
                scope_key=config.scope_key,
            )
            current = await self.dal.get_active(legacy_slot)
        return current, slot

    @staticmethod
    def _assert_current_expectation(
        *,
        current: AIConfigRecord | None,
        expected_id: str | None,
        expected_state_version: int | None,
    ) -> None:
        if (expected_id is None) != (expected_state_version is None):
            raise AIControlValidationError(
                "ai_config_current_active_expectation_pair_required"
            )
        if current is None:
            if expected_id is not None:
                raise AIControlStateConflictError("ai_config_current_active_missing")
            return
        if expected_id is None:
            raise AIControlStateConflictError(
                "ai_config_current_active_expectation_required"
            )
        if current.id != expected_id or current.state_version != expected_state_version:
            raise AIControlStateConflictError("ai_config_current_active_conflict")

    async def _retire_current(
        self,
        *,
        current: AIConfigRecord,
        expected_state_version: int,
        actor: ControlPlaneContext,
    ) -> AIConfigRecord:
        retired = await self.dal.cas_update(
            config_id=current.id,
            expected_version=expected_state_version,
            values={
                "activation_slot": None,
                "status": "retired",
                "retired_at": datetime.utcnow(),
                "updated_by_id": actor.subject_id,
            },
        )
        if retired is None:
            raise AIControlStateConflictError("ai_config_current_retire_conflict")
        return retired

    async def activate(
        self, *, payload: AIConfigActivateRequest, actor: ControlPlaneContext
    ) -> AIConfigResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="activate"
        )
        if replay is not None:
            return self._response(replay)
        target = await self.dal.get_by_id(payload.id)
        if target is None:
            raise AIControlNotFoundError("ai_config_not_found")
        if target.status != "validated":
            raise AIControlStateConflictError("ai_config_activate_validated_required")
        await self._verify_v2(config=target, require_validated_sources=True)
        current, slot = await self._current_active_for(config=target)
        self._assert_current_expectation(
            current=current,
            expected_id=payload.expected_current_active_id,
            expected_state_version=payload.expected_current_active_state_version,
        )
        if current is not None:
            try:
                await self._retire_current(
                    current=current,
                    expected_state_version=payload.expected_current_active_state_version,
                    actor=actor,
                )
            except AIControlStateConflictError:
                # A competing request may have committed this same command after
                # our initial lookup.  Abort this transaction before a fresh
                # Audit replay so no partial lifecycle mutation can survive.
                replayed = await self._rollback_and_replay_committed_or_none(
                    request_id=payload.request_id, action_type="activate"
                )
                if replayed is not None:
                    return self._response(replayed)
                raise
        updated = await self.dal.cas_update(
            config_id=target.id,
            expected_version=payload.expected_state_version,
            values={
                "activation_slot": slot,
                "status": "active",
                "error_code": None,
                "activated_at": datetime.utcnow(),
                "retired_at": None,
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="activate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_config_activate_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.config_key,
            action_type="activate",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=target.config_sha256,
            after_sha256=updated.config_sha256,
            changed_fields=["activation_slot", "status", "activated_at", "retired_at"],
            reason=payload.reason,
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="activate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def retire(
        self, *, payload: RetireCommandRequest, actor: ControlPlaneContext
    ) -> AIConfigResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="retire"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_config_not_found")
        if not is_v2_config(item):
            raise AIControlStateConflictError("ai_config_v2_required")
        if item.status not in {"draft", "validated", "active"}:
            raise AIControlStateConflictError("ai_config_retire_state_invalid")
        values = {
            "status": "retired",
            "retired_at": datetime.utcnow(),
            "updated_by_id": actor.subject_id,
        }
        if item.status == "active":
            values["activation_slot"] = None
        updated = await self.dal.cas_update(
            config_id=item.id,
            expected_version=payload.expected_state_version,
            values=values,
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="retire"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_config_retire_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.config_key,
            action_type="retire",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.config_sha256,
            after_sha256=updated.config_sha256,
            changed_fields=sorted(values),
            reason=payload.reason,
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="retire"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def rollback(
        self, *, payload: AIConfigRollbackRequest, actor: ControlPlaneContext
    ) -> AIConfigResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="rollback"
        )
        if replay is not None:
            return self._response(replay)
        target = await self.dal.get_by_id(payload.target_config_id)
        if target is None:
            raise AIControlNotFoundError("ai_config_not_found")
        if target.status != "retired" or not is_v2_config(target):
            raise AIControlStateConflictError("ai_config_rollback_retired_v2_required")
        # Historical source rows may be retired, but they must still exist and
        # recompile to the exact frozen hashes.  This checks the Secret *ref*
        # syntax held in the immutable Connection source without resolving it.
        await self._verify_v2(config=target, require_validated_sources=False)
        current, slot = await self._current_active_for(config=target)
        self._assert_current_expectation(
            current=current,
            expected_id=payload.expected_current_active_id,
            expected_state_version=payload.expected_current_active_state_version,
        )
        if current is None:
            raise AIControlStateConflictError(
                "ai_config_rollback_current_active_required"
            )
        try:
            await self._retire_current(
                current=current,
                expected_state_version=payload.expected_current_active_state_version,
                actor=actor,
            )
        except AIControlStateConflictError:
            # Keep rollback atomic: if the current active Config changed, this
            # request must roll back before checking whether it is an idempotent
            # replay of a command that already committed elsewhere.
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="rollback"
            )
            if replayed is not None:
                return self._response(replayed)
            raise
        updated = await self.dal.cas_update(
            config_id=target.id,
            expected_version=payload.expected_target_state_version,
            values={
                "activation_slot": slot,
                "status": "active",
                "error_code": None,
                "activated_at": datetime.utcnow(),
                "retired_at": None,
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="rollback"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_config_rollback_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.config_key,
            action_type="rollback",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=target.config_sha256,
            after_sha256=updated.config_sha256,
            changed_fields=["activation_slot", "status", "activated_at", "retired_at"],
            reason=payload.reason,
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="rollback"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)


__all__ = [
    "AIConfigNotFoundError",
    "AIConfigService",
    "AIConfigStateConflictError",
    "AIConfigValidationError",
]
