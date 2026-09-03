"""Provider-disabled AI request preparation for immutable v1/v2 Configs."""

from __future__ import annotations

import hashlib
import json
import secrets
from time import monotonic
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

import httpx

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.config_contract import (
    TASK_REQUEST_SNAPSHOT_V2,
    TASK_REQUEST_SNAPSHOT_V3,
    is_v2_config,
)
from apps.backend.core.ai.anatomy_localization_contract import (
    ANATOMY_LOCALIZATION_CONTRACT_V1,
    AnatomyLocalizationContractError,
    validate_anatomy_localization_result_contract,
)
from apps.backend.core.ai.image_quality_contract import (
    XRAY_IMAGE_QUALITY_CONTRACT_V1,
    XRayImageQualityContractError,
    validate_xray_image_quality_result_contract,
)
from apps.backend.core.ai.study_screening_contract import (
    XRAY_STUDY_SCREENING_CONTRACT_V1,
    XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
    XRayStudyScreeningContractError,
    validate_xray_study_screening_provider_result_contract,
    validate_xray_study_screening_result_contract,
)
from apps.backend.core.ai.system_analysis_contract import (
    XRAY_SYSTEM_ANALYSIS_CONTRACT_V1,
    XRaySystemAnalysisContractError,
    validate_xray_system_analysis_result_contract,
)
from apps.backend.core.ai.report_generation_contract import (
    XRAY_FINAL_REPORT_CONTRACT_V1,
    XRayReportGenerationContractError,
    validate_xray_report_generation_result_contract,
)
from apps.backend.core.ai.prompting import (
    PromptCatalog,
    PromptCompiler,
    PromptContractError,
    PromptMessageAssembler,
    PromptMessageContractError,
    PromptRenderError,
    PromptRenderer,
    validate_prompt_message_template,
)
from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.ai.xray_result_contract import (
    XRayResultContractError,
    validate_xray_result_contract,
)
from apps.backend.core.ai.gateway.contracts import (
    AI_IMAGE_RECEIPT_V1,
    AI_IMAGE_RECEIPT_V2,
    GatewayContractError,
    GatewayDefiniteResponseError,
    GatewayExecutionResult,
    GatewayImageInput,
    GatewayRejectedError,
    GatewayRequest,
    GatewayUnknownDeliveryError,
    normalize_gateway_profile,
    response_sha256,
    schema_validate_result,
)
from apps.backend.core.ai.gateway.image_signer import (
    AttemptImageSigner,
    build_oss_attempt_image_signer,
)
from apps.backend.core.ai.gateway_client import GatewayClient, GatewayResponseParseError
from apps.backend.core.ai.model_route import AiModelRoute
from apps.backend.core.config import settings
from apps.backend.core.pipeline import (
    XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
    XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    XRAY_REPORT_GENERATION_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V2,
    XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
    XRAY_TARGETED_REVIEW_PROFILE_V2,
    build_default_registry,
)
from apps.backend.crud.ai_call import AICallDal
from apps.backend.crud.ai_call_attempt import AICallAttemptDal
from apps.backend.crud.ai_config_record import AIConfigRecordDal
from apps.backend.crud.image import ImageDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.crud.task import TaskDal
from apps.backend.core.imaging.manifest import (
    ManifestContractError,
    build_series_manifest_legacy,
    validate_frozen_study_series,
)
from apps.backend.core.imaging.xray_contract import (
    require_xray_study_image_count,
    requires_xray_runtime_image_contract,
)
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.services.ai_control.service.config_compiler import AIConfigCompiler
from apps.backend.services.ai_control.service.errors import AIControlValidationError
from apps.backend.services.runtime.stages.xray.prompt_commands import XRayPromptCommand


class AIRequestServiceError(ValueError):
    pass


class AIRequestStateConflict(AIRequestServiceError):
    pass


class AIRequestService:
    """Create durable Logical Call facts without contacting a Provider in Phase C."""

    STUDY_SCREENING_CONFIG_KEYS = {
        "cat": "xray_study_screening_cat",
        "dog": "xray_study_screening_dog",
    }
    STUDY_SCREENING_PROMPT_KEYS = {
        "cat": "xray_cat_study_screening",
        "dog": "xray_dog_study_screening",
    }
    TARGETED_REVIEW_CONFIG_KEYS = {
        "cat": "xray_targeted_review_cat",
        "dog": "xray_targeted_review_dog",
    }
    TARGETED_REVIEW_PROMPT_KEYS = {
        "cat": "xray_cat_targeted_review",
        "dog": "xray_dog_targeted_review",
    }
    SYSTEM_ANALYSIS_CONFIG_KEYS = {
        "cat": "xray_system_analysis_cat",
        "dog": "xray_system_analysis_dog",
    }
    SYSTEM_ANALYSIS_PROMPT_KEYS = {
        "cat": "xray_cat_system_analysis",
        "dog": "xray_dog_system_analysis",
    }
    REPORT_GENERATION_CONFIG_KEYS = {
        "cat": "xray_report_generation_cat",
        "dog": "xray_report_generation_dog",
    }
    REPORT_GENERATION_PROMPT_KEYS = {
        "cat": "xray_cat_report_generation",
        "dog": "xray_dog_report_generation",
    }

    def __init__(self, db: AsyncSession):
        self.call_dal = AICallDal(db)
        self.attempt_dal = AICallAttemptDal(db)
        self.config_dal = AIConfigRecordDal(db)
        self.image_dal = ImageDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.task_dal = TaskDal(db)
        # This verifier is pure: it only checks the already-frozen v2 Config and
        # code-owned Pipeline/Schema contracts.  It never reads mutable sources.
        self.config_compiler = AIConfigCompiler(build_default_registry())

    @classmethod
    def _legacy_route_for_config(cls, *, config: Any) -> AiModelRoute:
        """Compatibility only for old provider-disabled Config tasks."""
        if is_v2_config(config):
            model = cls._frozen_lane(config=config).get("requested_model")
        else:
            model = (config.model_policy_json or {}).get("requested_model")
        if not isinstance(model, str) or not model.strip():
            raise AIRequestStateConflict("ai_call_requested_model_invalid")
        return AiModelRoute(models=(model,), mode="race")

    async def prepare_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
        trace_id: str,
        request_id: str,
        route: AiModelRoute | None = None,
        prompt_key: str | None = None,
        module_code: str = "xray",
        locale: str = "zh-CN",
        variant: str = "default",
        rendered_prompt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Prepare one durable Logical Call and state whether network I/O is required."""
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        if rendered_prompt is not None:
            if route is None or not prompt_key:
                raise AIRequestStateConflict("ai_prompt_runtime_request_invalid")
            return await self.prepare_structured_call(
                task_id=task_id,
                stage_checkpoint_id=stage_checkpoint_id,
                prompt_command=prompt_command,
                trace_id=trace_id,
                request_id=request_id,
                route=route,
                prompt_key=prompt_key,
                module_code=module_code,
                locale=locale,
                variant=variant,
                rendered_prompt=rendered_prompt,
            )

        config = await self._resolve_task_stage_config(task=task, stage=stage)
        effective_route = route or self._legacy_route_for_config(config=config)
        if not is_v2_config(config):
            result = await self._prepare_v1_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
                route=effective_route,
            )
            return {
                **result,
                "attempt_id": None,
                "winner": False,
                "network_required": False,
            }
        try:
            gateway_profile = normalize_gateway_profile(config.gateway_profile_json)
        except GatewayContractError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        if not gateway_profile["provider_enabled"]:
            return await self._prepare_v2_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
                route=effective_route,
            )
        if not self._runtime_gate_allows():
            return await self._prepare_v2_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
                terminal_error_code="ai_gateway_runtime_gate_denied",
                provider_disabled_required=False,
                route=effective_route,
            )
        raise AIRequestStateConflict("ai_prompt_runtime_render_required")

    async def prepare_provider_disabled_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
        route: AiModelRoute | None = None,
    ) -> dict[str, Any]:
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        # Runtime is intentionally bound to the Task's immutable Config reference,
        # never to the currently active Config or mutable Prompt/Pool/Connection rows.
        config = await self._resolve_task_stage_config(task=task, stage=stage)
        route = route or self._legacy_route_for_config(config=config)
        if is_v2_config(config):
            return await self._prepare_v2_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
                route=route,
            )
        return await self._prepare_v1_provider_disabled_call(
            task=task,
            stage=stage,
            config=config,
            prompt_command=prompt_command,
            route=route,
        )

    async def _prepare_v1_provider_disabled_call(
        self,
        *,
        task: Any,
        stage: Any,
        config: Any,
        prompt_command: XRayPromptCommand,
        route: AiModelRoute,
    ) -> dict[str, Any]:
        """Preserve the legacy Bundle path for historical v1 Tasks unchanged."""
        if config.status != "active":
            raise AIRequestStateConflict("ai_call_config_not_active")
        if (
            config.capability_manifest_json.get("provider_disabled") is not True
            or config.provider_plan_json.get("enabled") is not False
        ):
            raise AIRequestStateConflict("provider_disabled_required")
        self._validate_v1_task_config_snapshot(task=task, config=config)
        try:
            catalog = PromptCatalog.from_bundle_payload(config.prompt_bundle_json)
            compiled_prompt = prompt_command.compile(
                PromptCompiler(
                    catalog,
                    max_prompt_chars=config.model_policy_json["max_prompt_chars"],
                    prompt_policy=config.prompt_bundle_json["prompt_policy"],
                )
            )
        except (KeyError, PromptContractError) as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        schema_sha256 = config.schema_bundle_json["complete_medical_result"][
            "schema_sha256"
        ]
        if compiled_prompt.schema_sha256 != schema_sha256:
            raise AIRequestStateConflict("ai_call_schema_bundle_mismatch")
        manifest_sha = self._stage_manifest_sha256(stage=stage)
        model_policy = config.model_policy_json
        request = {
            "task_id": task.id,
            "stage_id": stage.id,
            "config_id": config.id,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "prompt_kind": prompt_command.prompt_kind,
            "rendered_prompt_sha256": compiled_prompt.rendered_sha256,
            "schema_sha256": schema_sha256,
            "manifest_sha256": manifest_sha,
            "model_policy_sha256": sha256_json(model_policy),
        }
        request_sha = self._sha(request)
        logical_key = self._sha(
            {
                "stage": stage.id,
                "input": stage.input_sha256,
                "config": config.config_sha256,
                "prompt": compiled_prompt.rendered_sha256,
                "schema": schema_sha256,
                "manifest": manifest_sha,
                "model_policy": request["model_policy_sha256"],
            }
        )
        existing = await self.call_dal.get_by_logical_key(logical_key)
        if existing is not None:
            return self._call_response(existing)
        image_count = sum(
            int(item.get("actual_image_count") or 0)
            for item in (task.request_snapshot_json or {}).get("series", [])
            if isinstance(item, dict)
        )
        prepared = await self.call_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "task_id": task.id,
                "stage_checkpoint_id": stage.id,
                "task_attempt_no": task.attempt_no,
                "stage_attempt_no": stage.retry_count + 1,
                "node_call_no": 1,
                "logical_call_key": logical_key,
                "idempotency_key": logical_key,
                "ai_config_id": config.id,
                "config_sha256": config.config_sha256,
                "provider_type": "disabled",
                "requested_model": model_policy["requested_model"],
                "request_sha256": request_sha,
                "rendered_prompt_sha256": compiled_prompt.rendered_sha256,
                "schema_sha256": schema_sha256,
                "requested_image_manifest_sha256": manifest_sha,
                "image_count_requested": image_count,
                "budget_reservation_json": {},
                "status": "prepared",
                "result_disposition": "pending",
                "prepared_at": datetime.utcnow(),
            }
        )
        if prepared is None:
            raise AIRequestStateConflict("ai_call_create_conflict")
        failed = await self.call_dal.cas_update(
            call_id=prepared.id,
            expected_version=prepared.state_version,
            values={
                "status": "failed",
                "result_disposition": "rejected",
                "error_code": "provider_disabled",
                "finished_at": datetime.utcnow(),
            },
        )
        if failed is None:
            raise AIRequestStateConflict("ai_call_disabled_transition_conflict")
        return self._call_response(failed)

    async def _prepare_v2_provider_disabled_call(
        self,
        *,
        task: Any,
        stage: Any,
        config: Any,
        prompt_command: XRayPromptCommand,
        route: AiModelRoute,
        terminal_error_code: str = "provider_disabled",
        provider_disabled_required: bool = True,
    ) -> dict[str, Any]:
        """Render one frozen Prompt body and persist a terminal Logical Call.

        No Secret is resolved and no network/Provider adapter is invoked on this
        path.  ``provider_disabled`` is a durable runtime fact, not a fake Attempt.
        """
        if config.status not in {"active", "retired"}:
            raise AIRequestStateConflict("ai_call_config_state_invalid")
        if not isinstance(config.capability_manifest_json, Mapping):
            raise AIRequestStateConflict("ai_call_capability_manifest_invalid")
        if (
            provider_disabled_required
            and config.capability_manifest_json.get("provider_disabled") is not True
        ):
            raise AIRequestStateConflict("provider_disabled_required")
        try:
            self.config_compiler.verify_frozen_integrity(config)
        except AIControlValidationError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        self._validate_v2_task_config_snapshot(
            task=task,
            stage=stage,
            config=config,
        )

        model_snapshot = config.model_snapshot_json
        if not isinstance(model_snapshot, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lanes = model_snapshot.get("lanes")
        if not isinstance(lanes, list) or len(lanes) != 1:
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lane = lanes[0]
        if not isinstance(lane, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        requested_model = route.models[0]
        if not isinstance(requested_model, str) or not requested_model:
            raise AIRequestStateConflict("ai_call_requested_model_invalid")

        budget_policy = config.budget_policy_json
        (
            max_prompt_chars,
            max_input_images,
            _,
            _,
            _,
        ) = self._validate_v2_budget_policy(budget_policy=budget_policy)
        (
            _,
            _,
            max_total_calls,
            max_total_attempts,
            task_deadline_ms,
        ) = self._validate_v2_budget_policy(
            budget_policy=task.budget_snapshot_json
        )

        manifest_sha = self._stage_manifest_sha256(stage=stage)
        image_count = self._v2_image_count(task=task, stage=stage)
        self._require_xray_image_count(
            config=config,
            task=task,
            stage=stage,
            image_count=image_count,
        )
        if image_count > max_input_images:
            raise AIRequestStateConflict("ai_call_image_budget_exceeded")

        generation_params = lane.get("generation_params")
        if not isinstance(generation_params, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        rendered, rendered_messages, _ = self._render_v2_messages(
            config=config,
            prompt_command=prompt_command,
            max_prompt_chars=max_prompt_chars,
        )

        request, request_sha, logical_key = self._build_v2_request_facts(
            task=task,
            stage=stage,
            config=config,
            prompt_command=prompt_command,
            rendered=rendered,
            rendered_messages=rendered_messages,
            manifest_sha=manifest_sha,
            generation_params=generation_params,
            budget_policy=budget_policy,
            route=route,
        )
        budget_policy_sha256 = sha256_json(task.budget_snapshot_json)
        now = datetime.utcnow()
        task_created_at = task.created_at
        if not isinstance(task_created_at, datetime):
            raise AIRequestStateConflict("task_created_at_invalid")
        # Deadline belongs to the frozen Task execution window, never to a
        # later retry/replay time.  The reservation helper checks this deadline
        # only for a genuinely new logical call; an existing terminal Call must
        # remain replayable after the window has elapsed.
        deadline_at = task_created_at + timedelta(milliseconds=task_deadline_ms)
        reservation = {
            "contract_version": "ai-budget-reservation.v1",
            "budget_policy_sha256": budget_policy_sha256,
            "reserved_call_units": 1,
            "reserved_attempts": 1,
            "prompt_chars": len(rendered.rendered_text),
            "image_count": image_count,
            "deadline_at": deadline_at.isoformat(timespec="microseconds") + "Z",
            "reservation_status": "reserved",
        }
        prepared = await self._reserve_v2_budget_and_create_call(
            task_id=task.id,
            logical_call_key=logical_key,
            budget_policy_sha256=budget_policy_sha256,
            max_total_calls=max_total_calls,
            max_total_attempts=max_total_attempts,
            deadline_at=deadline_at,
            reservation=reservation,
            call_values={
                "id": new_opaque_id(),
                "task_id": task.id,
                "stage_checkpoint_id": stage.id,
                "task_attempt_no": task.attempt_no,
                "stage_attempt_no": stage.retry_count + 1,
                "node_call_no": 1,
                "logical_call_key": logical_key,
                "idempotency_key": logical_key,
                "ai_config_id": config.id,
                "config_sha256": config.config_sha256,
                "release_fingerprint": config.release_fingerprint,
                "execution_mode": "single",
                "context_sha256": rendered.context_sha256,
                "provider_type": (
                    "disabled"
                    if provider_disabled_required
                    else str(lane.get("provider_type") or "gateway")
                ),
                "requested_model": requested_model,
                "request_sha256": request_sha,
                "rendered_prompt_sha256": rendered.rendered_prompt_sha256,
                "rendered_messages_json": rendered_messages.messages_json,
                "schema_sha256": config.output_schema_sha256,
                "requested_image_manifest_sha256": manifest_sha,
                "image_count_requested": image_count,
                "budget_reservation_json": reservation,
                "status": "prepared",
                "result_disposition": "pending",
                "prepared_at": now,
            },
        )
        if prepared.status != "prepared":
            if (
                prepared.status == "failed"
                and prepared.result_disposition == "failed"
                and prepared.error_code == terminal_error_code
            ):
                return self._call_response(prepared)
            raise AIRequestStateConflict("ai_call_existing_state_conflict")
        failed = await self.call_dal.cas_update(
            call_id=prepared.id,
            expected_version=prepared.state_version,
            values={
                "status": "failed",
                "result_disposition": "failed",
                "error_code": terminal_error_code[:80],
                "finished_at": datetime.utcnow(),
            },
        )
        if failed is None:
            raise AIRequestStateConflict("ai_call_terminal_transition_conflict")
        return self._call_response(failed)

    async def _reserve_v2_budget_and_create_call(
        self,
        *,
        task_id: str,
        logical_call_key: str,
        budget_policy_sha256: str,
        max_total_calls: int,
        max_total_attempts: int,
        deadline_at: datetime,
        reservation: dict[str, Any],
        call_values: dict[str, Any],
    ) -> Any:
        """Persist one Logical Call with the Task-level budget reservation.

        The locking reads establish a single serial order for the same logical
        key and for all reservations of one Task.  The Task CAS and Call insert
        share a savepoint, so a duplicate Call cannot leave a consumed Task
        budget behind.
        """
        existing = await self.call_dal.get_by_logical_key_for_update(logical_call_key)
        current_task = await self.task_dal.get_by_id_for_update(task_id)
        self._ensure_task_accepts_new_attempt(current_task)
        if existing is not None:
            return existing
        if datetime.utcnow() > deadline_at:
            raise AIRequestStateConflict("ai_call_task_deadline_exceeded")
        next_reserved = self._next_task_budget_reservation(
            current=current_task.budget_reserved_json,
            budget_policy_sha256=budget_policy_sha256,
            max_total_calls=max_total_calls,
            max_total_attempts=max_total_attempts,
            call_reservation=reservation,
        )

        try:
            async with self.call_dal.db.begin_nested():
                reserved_task = await self.task_dal.cas_update(
                    task_id=current_task.id,
                    expected_version=current_task.state_version,
                    values={"budget_reserved_json": next_reserved},
                )
                if reserved_task is None:
                    raise AIRequestStateConflict("ai_call_budget_reservation_conflict")
                return await self.call_dal.create_data(call_values, v_return_obj=True)
        except IntegrityError as exc:
            # The savepoint rolls back the Task CAS with the failed insert.  A
            # current locking read then returns the single durable Call fact.
            existing = await self.call_dal.get_by_logical_key_for_update(
                logical_call_key
            )
            if existing is not None:
                return existing
            raise AIRequestStateConflict("ai_call_create_conflict") from exc

    @staticmethod
    def _task_attempt_rejection_code(task: Any | None) -> str | None:
        if task is None:
            return "ai_call_task_not_found"
        if task.cancel_requested_at is not None or task.execution_status == "cancelled":
            return "task_cancelled"
        if task.execution_status in {"completed", "failed", "dead_letter"}:
            return "task_terminal"
        return None

    @classmethod
    def _ensure_task_accepts_new_attempt(cls, task: Any | None) -> None:
        rejection_code = cls._task_attempt_rejection_code(task)
        if rejection_code is not None:
            raise AIRequestStateConflict(rejection_code)

    async def _cancel_pending_call_for_task(
        self,
        *,
        call: Any,
        task: Any | None,
        now: datetime,
    ) -> Any:
        rejection_code = self._task_attempt_rejection_code(task)
        if rejection_code is None:
            return call
        if (
            call.winner_attempt_id is not None
            or call.status
            in {
                "succeeded",
                "failed",
                "cancelled",
            }
            or call.result_disposition
            in {
                "accepted",
                "rejected",
                "failed",
                "cancelled",
            }
        ):
            return call
        updated = await self.call_dal.cas_update(
            call_id=call.id,
            expected_version=call.state_version,
            values={
                "status": "cancelled",
                "result_disposition": "cancelled",
                "error_code": rejection_code,
                "finished_at": now,
            },
        )
        if updated is None:
            raise AIRequestStateConflict("ai_call_cancel_cas_conflict")
        return updated

    @staticmethod
    def _runtime_gate_allows() -> bool:
        """Use the same AI Platform configuration gate as ms-ai-fast."""
        from apps.backend.core.config import settings

        return settings.ai_platform_configured

    @staticmethod
    def _new_provider_idempotency_key() -> str:
        return f"ai-{secrets.token_hex(32)}"

    @staticmethod
    def _physical_attempt_key(
        *, call_id: str, attempt_no: int, request_sha256: str
    ) -> str:
        return hashlib.sha256(
            f"{call_id}:{attempt_no}:{request_sha256}".encode()
        ).hexdigest()

    @staticmethod
    def _runtime_request_snapshot(*, call: Any) -> dict[str, Any]:
        reservation = call.budget_reservation_json
        runtime = (
            reservation.get("runtime_request")
            if isinstance(reservation, Mapping)
            else None
        )
        if not isinstance(runtime, Mapping):
            raise AIRequestStateConflict("ai_call_runtime_snapshot_missing")
        required_strings = (
            "connection_id",
            "connection_sha256",
            "provider_type",
            "api_format",
            "streaming_mode",
        )
        if any(
            not isinstance(runtime.get(key), str) or not runtime.get(key)
            for key in required_strings
        ):
            raise AIRequestStateConflict("ai_call_runtime_snapshot_invalid")
        if (
            not isinstance(runtime.get("generation_params"), Mapping)
            or not isinstance(runtime.get("response_schema"), Mapping)
            or not isinstance(runtime.get("route"), Mapping)
            or not isinstance(runtime.get("allowed_actual_models"), list)
            or not isinstance(runtime.get("timeout_ms"), int)
            or not isinstance(runtime.get("image_url_ttl_seconds"), int)
        ):
            raise AIRequestStateConflict("ai_call_runtime_snapshot_invalid")
        return dict(runtime)

    @staticmethod
    def _frozen_lane(*, config: Any) -> dict[str, Any]:
        model_snapshot = config.model_snapshot_json
        if not isinstance(model_snapshot, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lanes = model_snapshot.get("lanes")
        if not isinstance(lanes, list) or len(lanes) != 1:
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lane = lanes[0]
        if not isinstance(lane, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        return dict(lane)

    @staticmethod
    def _image_receipt(
        *,
        images: Sequence[GatewayImageInput],
        image_inputs: Any = None,
        snapshot_contract_version: Any = None,
    ) -> dict[str, Any]:
        if snapshot_contract_version == TASK_REQUEST_SNAPSHOT_V3:
            if not isinstance(image_inputs, (tuple, list)) or len(image_inputs) != len(
                images
            ):
                raise GatewayContractError("ai_image_receipt_input_mismatch")
            receipt_items: list[dict[str, Any]] = []
            for image, frozen in zip(images, image_inputs, strict=True):
                if (
                    not isinstance(frozen, Mapping)
                    or frozen.get("sequence_no") != image.sequence_no
                    or frozen.get("mime_type") != image.mime_type
                ):
                    raise GatewayContractError("ai_image_receipt_input_mismatch")
                receipt_items.append(
                    {
                        "sequence_no": image.sequence_no,
                        "series_id": frozen.get("series_id"),
                        "series_manifest_sha256": frozen.get("series_manifest_sha256"),
                        "series_sequence_no": frozen.get("series_sequence_no"),
                        "image_id": frozen.get("image_id"),
                        "logical_image_key": frozen.get("logical_image_key"),
                        "image_version_no": frozen.get("image_version_no"),
                        "projection": frozen.get("projection"),
                        "projection_provenance": frozen.get("projection_provenance"),
                        "sha256": frozen.get("sha256"),
                        "size_bytes": frozen.get("size_bytes"),
                        "mime_type": image.mime_type,
                    }
                )
            return {
                "contract_version": AI_IMAGE_RECEIPT_V2,
                "image_count": len(images),
                "images": receipt_items,
            }
        return {
            "contract_version": AI_IMAGE_RECEIPT_V1,
            "image_count": len(images),
            "images": [
                {"sequence_no": image.sequence_no, "mime_type": image.mime_type}
                for image in images
            ],
        }

    @staticmethod
    def _messages_with_images(*, request: GatewayRequest) -> list[dict[str, Any]]:
        messages = [dict(message) for message in request.messages]
        if not messages:
            raise GatewayContractError("gateway_messages_missing")
        user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].get("role") == "user"
            ),
            None,
        )
        if user_index is None:
            raise GatewayContractError("gateway_user_message_missing")
        if not request.images:
            return messages
        user_message = dict(messages[user_index])
        content = user_message.get("content")
        if isinstance(content, str):
            parts: list[dict[str, Any]] = [{"type": "text", "text": content}]
        elif isinstance(content, list) and all(
            isinstance(part, Mapping) for part in content
        ):
            parts = [dict(part) for part in content]
        else:
            raise GatewayContractError("gateway_message_content_invalid")
        parts.extend(
            {"type": "image_url", "image_url": {"url": image.signed_url}}
            for image in request.images
        )
        user_message["content"] = parts
        messages[user_index] = user_message
        return messages

    @classmethod
    def _build_gateway_payload(cls, *, request: GatewayRequest) -> dict[str, Any]:
        api_format = request.api_format.strip().casefold().replace("_", "-")
        if api_format not in {
            "chat",
            "chat-completions",
            "openai-chat-completions",
        }:
            raise GatewayContractError("gateway_api_format_unsupported")
        generation = dict(request.generation_params)
        reserved = {
            "model",
            "strategy",
            "messages",
            "metadata",
            "response_format",
            "stream",
        }
        if reserved.intersection(generation):
            raise GatewayContractError("gateway_generation_params_invalid")
        max_output_tokens = generation.pop("max_output_tokens", None)
        if max_output_tokens is not None and (
            not isinstance(max_output_tokens, int)
            or isinstance(max_output_tokens, bool)
            or max_output_tokens < 1
        ):
            raise GatewayContractError("gateway_generation_params_invalid")
        temperature = generation.pop("temperature", 0.2)
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            raise GatewayContractError("gateway_generation_params_invalid")
        payload: dict[str, Any] = {
            "model": request.requested_model,
            # Keep ms-image's frozen single-lane execution separate from the
            # ms-ai-platform scheduling contract.  The Platform only accepts
            # ``round_robin`` or ``race``; ms-ai-fast uses ``race`` by default.
            "strategy": request.strategy,
            "messages": cls._messages_with_images(request=request),
            "temperature": temperature,
            "metadata": {
                "task_id": request.task_id,
                "attempt_id": request.attempt_id,
                "request_id": request.request_id,
                "trace_id": request.trace_id,
                "idempotency_key": request.provider_idempotency_key,
            },
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ms_image_structured_result",
                    "strict": True,
                    "schema": cls._normalize_strict_schema(
                        dict(request.response_schema)
                    ),
                },
            },
            **generation,
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        return payload

    @classmethod
    def _normalize_strict_schema(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._normalize_strict_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        normalized = {
            key: cls._normalize_strict_schema(item) for key, item in value.items()
        }
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            existing_required = normalized.get("required")
            required = (
                [item for item in existing_required if isinstance(item, str)]
                if isinstance(existing_required, list)
                else []
            )
            normalized["required"] = list(
                dict.fromkeys([*required, *properties.keys()])
            )
            normalized.setdefault("additionalProperties", False)
        return normalized

    @staticmethod
    def _provider_message_content(body: Mapping[str, Any]) -> str | dict[str, Any]:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise GatewayContractError("provider_response_content_missing")
        first = choices[0]
        if not isinstance(first, Mapping):
            raise GatewayContractError("provider_response_content_missing")
        message = first.get("message")
        if not isinstance(message, Mapping):
            raise GatewayContractError("provider_response_content_missing")
        content = message.get("content")
        if isinstance(content, dict):
            return dict(content)
        if not isinstance(content, str) or not content.strip():
            raise GatewayContractError("provider_response_content_missing")
        return content

    @staticmethod
    def _provider_http_error_code(response: httpx.Response) -> str:
        provider_code: str | None = None
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            body = None
        if isinstance(body, Mapping) and isinstance(body.get("error"), Mapping):
            error = body["error"]
            candidate = error.get("code") or error.get("type")
            if isinstance(candidate, str) and candidate.strip():
                provider_code = candidate.strip().replace(" ", "_")[:40]
        suffix = f"_{provider_code}" if provider_code else ""
        return f"provider_http_{response.status_code}{suffix}"[:80]

    @staticmethod
    def _validate_v2_budget_policy(
        *, budget_policy: Mapping[str, Any]
    ) -> tuple[int, int, int, int, int]:
        if not isinstance(budget_policy, Mapping):
            raise AIRequestStateConflict("ai_call_budget_policy_invalid")
        values = (
            budget_policy.get("max_prompt_chars"),
            budget_policy.get("max_input_images"),
            budget_policy.get("max_total_calls"),
            budget_policy.get("max_total_attempts"),
            budget_policy.get("task_deadline_ms"),
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in values
        ):
            raise AIRequestStateConflict("ai_call_budget_policy_invalid")
        return values  # type: ignore[return-value]

    @staticmethod
    def _render_v2_messages(
        *,
        config: Any,
        prompt_command: XRayPromptCommand,
        max_prompt_chars: int,
    ) -> tuple[Any, Any, dict[str, Any]]:
        try:
            validate_prompt_message_template(
                content=config.prompt_content,
                message_contract_json=config.prompt_message_contract_json,
            )
            safe_variables = AIRequestService._v2_safe_variables(
                config=config,
                prompt_command=prompt_command,
            )
            rendered = PromptRenderer.render(
                content=config.prompt_content,
                variables_json=config.prompt_variables_json,
                safe_variables=safe_variables,
                max_prompt_chars=max_prompt_chars,
            )
            rendered_messages = PromptMessageAssembler.assemble(
                rendered_text=rendered.rendered_text,
                message_contract_json=config.prompt_message_contract_json,
                safe_variables=safe_variables,
            )
        except (PromptRenderError, PromptMessageContractError) as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        return rendered, rendered_messages, safe_variables

    @staticmethod
    def _build_v2_request_facts(
        *,
        task: Any,
        stage: Any,
        config: Any,
        prompt_command: XRayPromptCommand,
        rendered: Any,
        rendered_messages: Any,
        manifest_sha: str,
        generation_params: Mapping[str, Any],
        budget_policy: Mapping[str, Any],
        route: AiModelRoute,
    ) -> tuple[dict[str, Any], str, str]:
        budget_policy_sha256 = sha256_json(budget_policy)
        request = {
            "task_id": task.id,
            "stage_id": stage.id,
            "config_id": config.id,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "prompt_kind": prompt_command.prompt_kind,
            "execution_mode": "single",
            "rendered_prompt_sha256": rendered.rendered_prompt_sha256,
            "rendered_messages_sha256": rendered_messages.messages_sha256,
            "context_sha256": rendered.context_sha256,
            "schema_sha256": config.output_schema_sha256,
            "manifest_sha256": manifest_sha,
            "model_snapshot_sha256": config.model_snapshot_sha256,
            "code_model_route": {"models": list(route.models), "mode": route.mode},
            "generation_params_sha256": sha256_json(generation_params),
            "budget_policy_sha256": budget_policy_sha256,
        }
        request_sha = AIRequestService._sha(request)
        logical_key = AIRequestService._sha(
            {
                "stage": stage.id,
                "input": stage.input_sha256,
                "config": config.config_sha256,
                "prompt": rendered.rendered_prompt_sha256,
                "messages": rendered_messages.messages_sha256,
                "context": rendered.context_sha256,
                "schema": config.output_schema_sha256,
                "manifest": manifest_sha,
                "model": config.model_snapshot_sha256,
                "code_model_route": {"models": list(route.models), "mode": route.mode},
                "execution_mode": "single",
                "prompt_kind": prompt_command.prompt_kind,
            }
        )
        return request, request_sha, logical_key

    @staticmethod
    def prompt_runtime_variables(
        *, prompt_command: XRayPromptCommand
    ) -> dict[str, Any]:
        """Build the same permissive variables payload style used by ms-ai-fast."""
        variables: dict[str, Any] = {
            "SAFE_STUDY_CONTEXT_JSON": prompt_command.safe_context,
            "base_info": prompt_command.safe_context,
            "study_context": prompt_command.safe_context,
        }
        optional = {
            "PRIMARY_RESULT_JSON": prompt_command.primary_complete_result,
            "previous_answer": prompt_command.primary_complete_result,
            "primary_result": prompt_command.primary_complete_result,
            "QUALITY_RESULTS_JSON": prompt_command.quality_results,
            "ROUTE_CONTEXT_JSON": prompt_command.route_context,
            "STUDY_SCREENING_RESULT_JSON": prompt_command.study_screening_result,
            "SYSTEM_ANALYSIS_RESULT_JSON": prompt_command.system_analysis_result,
            "FINAL_MEDICAL_RESULT_JSON": prompt_command.final_medical_result,
        }
        variables.update({key: value for key, value in optional.items() if value is not None})
        return variables

    @staticmethod
    def _normalize_prompt_runtime_result(
        *, rendered_prompt: Mapping[str, Any]
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
        messages = rendered_prompt.get("messages")
        prompt = rendered_prompt.get("prompt")
        if not isinstance(messages, list) and isinstance(prompt, Mapping):
            messages = prompt.get("messages")
        if not isinstance(messages, list) or not messages or not all(
            isinstance(item, Mapping) for item in messages
        ):
            content = (
                rendered_prompt.get("rendered_prompt")
                or rendered_prompt.get("content")
            )
            if not isinstance(content, str) or not content:
                raise AIRequestStateConflict("prompt_runtime_messages_invalid")
            messages = [{"role": "user", "content": content}]
        normalized_messages = [dict(item) for item in messages]
        response_schema = rendered_prompt.get("output_schema")
        response_format = rendered_prompt.get("response_format")
        if not isinstance(response_schema, Mapping) and isinstance(
            response_format, Mapping
        ):
            json_schema = response_format.get("json_schema")
            if isinstance(json_schema, Mapping):
                response_schema = json_schema.get("schema")
        if not isinstance(response_schema, Mapping) or not response_schema:
            raise AIRequestStateConflict("prompt_runtime_output_schema_missing")
        generation_params: dict[str, Any] = {
            "temperature": rendered_prompt.get("temperature", 0.2)
        }
        for key in ("top_p", "max_output_tokens"):
            value = rendered_prompt.get(key)
            if value is not None:
                generation_params[key] = value
        metadata = (
            rendered_prompt.get("metadata")
            if isinstance(rendered_prompt.get("metadata"), Mapping)
            else {}
        )
        audit = {
            "prompt_version_public_id": rendered_prompt.get(
                "prompt_version_public_id"
            )
            or rendered_prompt.get("version_public_id"),
            "prompt_content_hash": rendered_prompt.get("prompt_content_hash")
            or rendered_prompt.get("content_hash"),
            "prompt_release_public_id": rendered_prompt.get("release_public_id"),
            "prompt_requested_variant": rendered_prompt.get("requested_variant")
            or metadata.get("requested_variant"),
            "prompt_resolved_variant": rendered_prompt.get("resolved_variant")
            or metadata.get("resolved_variant"),
            "prompt_fallback_used": bool(
                rendered_prompt.get("fallback_used")
                or metadata.get("fallback_used", False)
            ),
        }
        return normalized_messages, generation_params, dict(response_schema), audit

    async def prepare_structured_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
        trace_id: str,
        request_id: str,
        route: AiModelRoute,
        prompt_key: str,
        module_code: str,
        locale: str,
        variant: str,
        rendered_prompt: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Boundary A: persist one code-routed, Prompt-Runtime-rendered call."""
        if not self._runtime_gate_allows():
            raise AIRequestStateConflict("ai_gateway_runtime_gate_denied")
        if len(route.models) != 1:
            raise AIRequestStateConflict("ai_model_route_single_model_required")
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")

        variables = self.prompt_runtime_variables(prompt_command=prompt_command)
        messages, generation_params, response_schema, prompt_runtime_audit = (
            self._normalize_prompt_runtime_result(rendered_prompt=rendered_prompt)
        )
        budget_policy = task.budget_snapshot_json
        (
            max_prompt_chars,
            max_input_images,
            max_total_calls,
            max_total_attempts,
            task_deadline_ms,
        ) = self._validate_v2_budget_policy(budget_policy=budget_policy)
        prompt_chars = len(json.dumps(messages, ensure_ascii=False, default=str))
        if prompt_chars > max_prompt_chars:
            raise AIRequestStateConflict("ai_call_prompt_budget_exceeded")

        manifest_sha = self._stage_manifest_sha256(stage=stage)
        image_count = self._v2_image_count(task=task, stage=stage)
        self._require_xray_image_count(
            config=None, task=task, stage=stage, image_count=image_count
        )
        if image_count > max_input_images:
            raise AIRequestStateConflict("ai_call_image_budget_exceeded")

        requested_model = route.models[0]
        connection_id = "ms-ai-platform"
        provider_type = "ms-ai-platform"
        api_format = "chat-completions"
        connection_sha256 = sha256_json(
            {
                "connection_id": connection_id,
                "base_url": settings.AI_PLATFORM_OPENAI_BASE_URL.rstrip("/"),
                "provider_type": provider_type,
                "api_format": api_format,
            }
        )
        timeout_ms = max(1, round(settings.AI_PLATFORM_TIMEOUT_SECONDS * 1000))
        image_url_ttl_seconds = 300
        snapshot = task.request_snapshot_json or {}
        bindings = snapshot.get("stage_ai_config_bindings")
        binding = (
            bindings.get(stage.stage_key) if isinstance(bindings, Mapping) else None
        )
        config_id = (
            binding.get("ai_config_id")
            if isinstance(binding, Mapping)
            else task.ai_config_id
        )
        config_sha256 = (
            binding.get("config_sha256")
            if isinstance(binding, Mapping)
            else snapshot.get("config_sha256")
        )
        if not isinstance(config_id, str) or not config_id:
            config_id = task.ai_config_id
        if not isinstance(config_sha256, str) or len(config_sha256) != 64:
            config_sha256 = task.request_sha256
        release_fingerprint = (
            binding.get("release_fingerprint")
            if isinstance(binding, Mapping)
            else snapshot.get("release_fingerprint")
        )
        context_sha256 = sha256_json(variables)
        rendered_messages_sha256 = sha256_json(messages)
        schema_sha256 = sha256_json(response_schema)
        route_fact = {"models": list(route.models), "mode": route.mode}
        prompt_fact = {
            "service_code": settings.PROMPT_SERVICE_CODE,
            "module_code": module_code,
            "prompt_key": prompt_key,
            "locale": locale,
            "variant": variant,
            "variables_sha256": context_sha256,
            **prompt_runtime_audit,
        }
        request_fact = {
            "task_id": task.id,
            "stage_id": stage.id,
            "prompt": prompt_fact,
            "route": route_fact,
            "messages_sha256": rendered_messages_sha256,
            "schema_sha256": schema_sha256,
            "manifest_sha256": manifest_sha,
            "generation_params_sha256": sha256_json(generation_params),
        }
        request_sha = self._sha(request_fact)
        logical_key = self._sha(
            {
                "stage": stage.id,
                "input": stage.input_sha256,
                "prompt_identity": {
                    "service_code": settings.PROMPT_SERVICE_CODE,
                    "module_code": module_code,
                    "prompt_key": prompt_key,
                    "locale": locale,
                    "variant": variant,
                    "variables_sha256": context_sha256,
                },
                "route": route_fact,
                "manifest": manifest_sha,
            }
        )
        budget_policy_sha256 = sha256_json(budget_policy)
        now = datetime.utcnow()
        if not isinstance(task.created_at, datetime):
            raise AIRequestStateConflict("task_created_at_invalid")
        deadline_at = task.created_at + timedelta(milliseconds=task_deadline_ms)
        runtime_request = {
            "contract_version": "ms-image-ai-runtime.v1",
            "prompt": prompt_fact,
            "route": route_fact,
            "connection_id": connection_id,
            "connection_sha256": connection_sha256,
            "provider_type": provider_type,
            "api_format": api_format,
            "generation_params": generation_params,
            "response_schema": response_schema,
            "allowed_actual_models": list(route.models),
            "streaming_mode": "json",
            "timeout_ms": timeout_ms,
            "image_url_ttl_seconds": image_url_ttl_seconds,
        }
        reservation = {
            "contract_version": "ai-budget-reservation.v1",
            "budget_policy_sha256": budget_policy_sha256,
            "reserved_call_units": 1,
            "reserved_attempts": 1,
            "prompt_chars": prompt_chars,
            "image_count": image_count,
            "deadline_at": deadline_at.isoformat(timespec="microseconds") + "Z",
            "reservation_status": "reserved",
            "runtime_request": runtime_request,
        }
        call_values = {
            "id": new_opaque_id(),
            "task_id": task.id,
            "stage_checkpoint_id": stage.id,
            "task_attempt_no": task.attempt_no,
            "stage_attempt_no": stage.retry_count + 1,
            "node_call_no": 1,
            "logical_call_key": logical_key,
            "idempotency_key": logical_key,
            "ai_config_id": config_id,
            "config_sha256": config_sha256,
            "release_fingerprint": release_fingerprint,
            "execution_mode": route.mode,
            "context_sha256": context_sha256,
            "provider_type": provider_type,
            "requested_model": requested_model,
            "request_sha256": request_sha,
            "rendered_prompt_sha256": rendered_messages_sha256,
            "rendered_messages_json": messages,
            "schema_sha256": schema_sha256,
            "requested_image_manifest_sha256": manifest_sha,
            "image_count_requested": image_count,
            "attempt_count": 1,
            "budget_reservation_json": reservation,
            "status": "prepared",
            "result_disposition": "pending",
            "prepared_at": now,
        }
        prepared = await self._reserve_v2_budget_and_create_call(
            task_id=task.id,
            logical_call_key=logical_key,
            budget_policy_sha256=budget_policy_sha256,
            max_total_calls=max_total_calls,
            max_total_attempts=max_total_attempts,
            deadline_at=deadline_at,
            reservation=reservation,
            call_values=call_values,
        )
        if prepared.status != "prepared":
            return self._structured_call_response(
                call=prepared, attempt=None, winner=False
            )
        existing_attempt = await self.attempt_dal.get_by_call_attempt_no(
            ai_call_id=prepared.id, attempt_no=1
        )
        if existing_attempt is not None:
            return self._structured_call_response(
                call=prepared, attempt=existing_attempt, winner=False
            )
        attempt = await self.attempt_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "ai_call_id": prepared.id,
                "attempt_no": 1,
                "physical_attempt_key": self._physical_attempt_key(
                    call_id=prepared.id,
                    attempt_no=1,
                    request_sha256=request_sha,
                ),
                "provider_idempotency_key": self._new_provider_idempotency_key(),
                "trace_id": trace_id,
                "request_id": request_id,
                "connection_id": connection_id,
                "connection_sha256": connection_sha256,
                "provider_type": provider_type,
                "api_format": api_format,
                "requested_model": requested_model,
                "request_sha256": request_sha,
                "image_count_sent": 0,
                "status": "prepared",
                "prepared_at": now,
            }
        )
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_create_conflict")
        return self._structured_call_response(
            call=prepared, attempt=attempt, winner=False
        )

    async def prepare_retry_attempt(
        self, *, call_id: str, trace_id: str, request_id: str
    ) -> dict[str, Any]:
        """Boundary A: retry from the persisted invocation facts, never DB Config."""
        call = await self.call_dal.get_by_id_for_update(call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        self._ensure_task_accepts_new_attempt(task)
        if call.winner_attempt_id is not None:
            raise AIRequestStateConflict("ai_call_winner_already_selected")
        if call.status not in {"prepared", "running"}:
            raise AIRequestStateConflict("ai_call_retry_state_invalid")
        reservation = call.budget_reservation_json
        runtime = self._runtime_request_snapshot(call=call)
        reserved_attempts = reservation.get("reserved_attempts")
        next_attempt_no = int(await self.attempt_dal.get_count(ai_call_id=call.id)) + 1
        if (
            not isinstance(reserved_attempts, int)
            or isinstance(reserved_attempts, bool)
            or next_attempt_no > reserved_attempts
        ):
            raise AIRequestStateConflict("ai_call_attempt_budget_exceeded")
        now = datetime.utcnow()
        attempt = await self.attempt_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "ai_call_id": call.id,
                "attempt_no": next_attempt_no,
                "physical_attempt_key": self._physical_attempt_key(
                    call_id=call.id,
                    attempt_no=next_attempt_no,
                    request_sha256=call.request_sha256,
                ),
                "provider_idempotency_key": self._new_provider_idempotency_key(),
                "trace_id": trace_id,
                "request_id": request_id,
                "connection_id": runtime["connection_id"],
                "connection_sha256": runtime["connection_sha256"],
                "provider_type": runtime["provider_type"],
                "api_format": runtime["api_format"],
                "requested_model": call.requested_model,
                "request_sha256": call.request_sha256,
                "image_count_sent": 0,
                "status": "prepared",
                "prepared_at": now,
            }
        )
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_create_conflict")
        updated_call = await self.call_dal.cas_update(
            call_id=call.id,
            expected_version=call.state_version,
            values={
                "attempt_count": next_attempt_no,
                "status": "running",
                "started_at": call.started_at or now,
            },
        )
        if updated_call is None:
            raise AIRequestStateConflict("ai_call_attempt_count_conflict")
        return self._structured_call_response(
            call=updated_call, attempt=attempt, winner=False
        )

    async def load_attempt_for_network(self, *, attempt_id: str) -> dict[str, Any]:
        """Freeze Boundary-B facts from the persisted invocation snapshot."""
        attempt = await self.attempt_dal.get_by_id(attempt_id)
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_not_found")
        call = await self.call_dal.get_by_id(attempt.ai_call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        runtime = self._runtime_request_snapshot(call=call)
        if (
            runtime["connection_id"] != attempt.connection_id
            or runtime["connection_sha256"] != attempt.connection_sha256
        ):
            raise AIRequestStateConflict("ai_call_attempt_connection_mismatch")
        if attempt.status != "prepared":
            raise AIRequestStateConflict("ai_call_attempt_network_state_invalid")
        if call.status not in {"prepared", "running"} or call.result_disposition != "pending":
            raise AIRequestStateConflict("ai_call_network_state_invalid")
        messages = call.rendered_messages_json
        if not isinstance(messages, list) or not messages:
            raise AIRequestStateConflict("ai_call_rendered_messages_missing")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        self._ensure_task_accepts_new_attempt(task)
        stage = await self.stage_dal.get_by_id(call.stage_checkpoint_id)
        if stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        if call.winner_attempt_id is not None:
            raise AIRequestStateConflict("ai_call_winner_already_selected")
        self._require_xray_image_count(
            config=None,
            task=task,
            stage=stage,
            image_count=call.image_count_requested,
        )
        image_inputs = await self._load_attempt_image_inputs(
            task=task,
            expected_manifest_sha256=call.requested_image_manifest_sha256,
            expected_image_count=call.image_count_requested,
        )
        return {
            "attempt_id": attempt.id,
            "logical_call_id": call.id,
            "task_id": call.task_id,
            "stage_checkpoint_id": call.stage_checkpoint_id,
            "trace_id": attempt.trace_id,
            "request_id": attempt.request_id,
            "connection_sha256": attempt.connection_sha256,
            "provider_type": attempt.provider_type,
            "api_format": attempt.api_format,
            "requested_model": attempt.requested_model,
            "allowed_actual_models": tuple(runtime["allowed_actual_models"]),
            "strategy": runtime["route"]["mode"],
            "generation_params": dict(runtime["generation_params"]),
            "response_schema": dict(runtime["response_schema"]),
            "messages": tuple(dict(item) for item in messages),
            "streaming_mode": runtime["streaming_mode"],
            "timeout_ms": runtime["timeout_ms"],
            "provider_idempotency_key": attempt.provider_idempotency_key,
            "image_manifest_sha256": call.requested_image_manifest_sha256,
            "image_count_requested": call.image_count_requested,
            "image_inputs": image_inputs,
            "xray_image_contract_required": self._xray_image_contract_required(
                config=None, task=task, stage=stage
            ),
            "snapshot_contract_version": (task.request_snapshot_json or {}).get(
                "snapshot_contract_version"
            ),
            "expected_species": (task.request_snapshot_json or {}).get("species"),
            "image_url_ttl_seconds": runtime["image_url_ttl_seconds"],
            "report_generation_expected": self._report_generation_expected(stage=stage),
        }

    @staticmethod
    async def execute_gateway_attempt_network(
        *,
        network_plan: Mapping[str, Any],
        gateway_client: GatewayClient | None = None,
        image_signer: AttemptImageSigner | None = None,
    ) -> dict[str, Any]:
        """Boundary B: call ms-ai-platform from frozen facts with no DB access."""
        xray_image_contract_required = (
            network_plan.get("xray_image_contract_required") is True
        )
        if xray_image_contract_required:
            try:
                require_xray_study_image_count(
                    network_plan.get("image_count_requested")
                )
            except ValueError as exc:
                raise GatewayContractError(
                    "ai_call_xray_image_count_out_of_range"
                ) from exc
        signer = image_signer or build_oss_attempt_image_signer()
        images = await signer.sign(
            attempt_plan=network_plan,
            ttl_seconds=int(network_plan["image_url_ttl_seconds"]),
        )
        if len(images) != network_plan.get("image_count_requested"):
            raise GatewayContractError("ai_call_image_count_mismatch")
        if xray_image_contract_required:
            try:
                require_xray_study_image_count(len(images))
            except ValueError as exc:
                raise GatewayContractError(
                    "ai_call_xray_image_count_out_of_range"
                ) from exc
        gateway_request = GatewayRequest(
            attempt_id=str(network_plan["attempt_id"]),
            logical_call_id=str(network_plan["logical_call_id"]),
            task_id=str(network_plan["task_id"]),
            trace_id=str(network_plan["trace_id"]),
            request_id=str(network_plan["request_id"]),
            connection_sha256=str(network_plan["connection_sha256"]),
            provider_type=str(network_plan["provider_type"]),
            api_format=str(network_plan["api_format"]),
            requested_model=str(network_plan["requested_model"]),
            allowed_actual_models=tuple(network_plan["allowed_actual_models"]),
            generation_params=dict(network_plan["generation_params"]),
            response_schema=dict(network_plan["response_schema"]),
            messages=tuple(dict(item) for item in network_plan["messages"]),
            images=tuple(images),
            timeout_ms=int(network_plan["timeout_ms"]),
            provider_idempotency_key=str(network_plan["provider_idempotency_key"]),
            image_manifest_sha256=network_plan.get("image_manifest_sha256"),
            strategy=str(network_plan.get("strategy") or "race"),
        )
        payload = AIRequestService._build_gateway_payload(request=gateway_request)
        image_receipt = AIRequestService._image_receipt(
            images=images,
            image_inputs=network_plan.get("image_inputs"),
            snapshot_contract_version=network_plan.get("snapshot_contract_version"),
        )
        image_manifest_sha256 = network_plan.get("image_manifest_sha256")
        image_count_sent = len(images)
        gateway = gateway_client or GatewayClient()
        started = monotonic()
        try:
            gateway_result = await gateway.chat_completions(
                payload,
                idempotency_key=gateway_request.provider_idempotency_key,
            )
        except httpx.HTTPStatusError as exc:
            raise GatewayRejectedError(
                AIRequestService._provider_http_error_code(exc.response),
                image_receipt=image_receipt,
                image_manifest_sha256=image_manifest_sha256,
                image_count_sent=image_count_sent,
            ) from exc
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.RequestError,
        ) as exc:
            raise GatewayUnknownDeliveryError("provider_delivery_unknown") from exc
        except GatewayResponseParseError as exc:
            raise GatewayDefiniteResponseError(
                str(exc),
                image_receipt=image_receipt,
                image_manifest_sha256=image_manifest_sha256,
                image_count_sent=image_count_sent,
            ) from exc
        except RuntimeError as exc:
            raise GatewayContractError("provider_response_payload_invalid") from exc

        provider_request_id_audit: str | None = None
        actual_model_audit: str | None = None
        usage_json_audit: dict[str, Any] | None = None
        response_sha256_audit: str | None = None
        try:
            if not isinstance(gateway_result, Mapping):
                raise GatewayContractError("provider_response_payload_invalid")
            body = gateway_result.get("body")
            provider_request_id = gateway_result.get("request_id")
            if not isinstance(body, Mapping):
                raise GatewayContractError("provider_response_payload_invalid")
            if (
                not isinstance(provider_request_id, str)
                or not provider_request_id.strip()
            ):
                raise GatewayContractError("provider_request_id_missing")
            provider_request_id_audit = provider_request_id.strip()
            content = AIRequestService._provider_message_content(body)
            actual_model = body.get("model") or gateway_request.requested_model
            if not isinstance(actual_model, str) or not actual_model.strip():
                raise GatewayContractError("provider_actual_model_missing")
            actual_model = actual_model.strip()
            actual_model_audit = actual_model
            response_sha256_audit = response_sha256(body)
            allowed_models = set(gateway_request.allowed_actual_models) or {
                gateway_request.requested_model
            }
            if actual_model not in allowed_models:
                raise GatewayContractError("provider_actual_model_mismatch")
            usage = body.get("usage")
            if usage is not None and not isinstance(usage, Mapping):
                raise GatewayContractError("provider_usage_invalid")
            usage_json_audit = dict(usage) if isinstance(usage, Mapping) else None
            parsed_result = schema_validate_result(
                value=content,
                schema=gateway_request.response_schema,
            )
            schema_contract_version = gateway_request.response_schema.get(
                "x-ms-image-contract-version"
            )
            try:
                if schema_contract_version in {
                    "complete-medical-result.v1",
                    "complete-medical-result.v2",
                }:
                    parsed_result = validate_xray_result_contract(
                        result=parsed_result,
                        schema_contract_version=schema_contract_version,
                        image_receipt=image_receipt,
                    )
                elif schema_contract_version == ANATOMY_LOCALIZATION_CONTRACT_V1:
                    parsed_result = validate_anatomy_localization_result_contract(
                        result=parsed_result,
                        schema_contract_version=schema_contract_version,
                        image_receipt=image_receipt,
                        expected_species=network_plan.get("expected_species"),
                    )
                elif schema_contract_version == XRAY_IMAGE_QUALITY_CONTRACT_V1:
                    parsed_result = validate_xray_image_quality_result_contract(
                        result=parsed_result,
                        schema_contract_version=schema_contract_version,
                        image_receipt=image_receipt,
                        expected_species=network_plan.get("expected_species"),
                    )
                elif schema_contract_version == XRAY_STUDY_SCREENING_CONTRACT_V1:
                    parsed_result = validate_xray_study_screening_result_contract(
                        result=parsed_result,
                        schema_contract_version=schema_contract_version,
                        image_receipt=image_receipt,
                        expected_species=network_plan.get("expected_species"),
                    )
                elif (
                    schema_contract_version
                    == XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2
                ):
                    parsed_result = (
                        validate_xray_study_screening_provider_result_contract(
                            result=parsed_result,
                            schema_contract_version=schema_contract_version,
                            image_receipt=image_receipt,
                            expected_species=network_plan.get("expected_species"),
                        )
                    )
                elif schema_contract_version == XRAY_SYSTEM_ANALYSIS_CONTRACT_V1:
                    parsed_result = validate_xray_system_analysis_result_contract(
                        result=parsed_result,
                        schema_contract_version=schema_contract_version,
                        image_receipt=image_receipt,
                        expected_species=network_plan.get("expected_species"),
                    )
                elif schema_contract_version == XRAY_FINAL_REPORT_CONTRACT_V1:
                    expected_report = network_plan.get(
                        "report_generation_expected"
                    )
                    if not isinstance(expected_report, Mapping):
                        raise XRayReportGenerationContractError(
                            "report_generation_expected_result_missing"
                        )
                    parsed_result = (
                        validate_xray_report_generation_result_contract(
                            result=parsed_result,
                            schema_contract_version=schema_contract_version,
                            expected_source_result_sha256=expected_report.get(
                                "source_result_sha256"
                            ),
                            expected_final_medical_result=expected_report.get(
                                "final_medical_result"
                            ),
                        )
                    )
                else:
                    raise GatewayContractError(
                        "provider_result_contract_version_unsupported"
                    )
            except (
                XRayResultContractError,
                AnatomyLocalizationContractError,
                XRayImageQualityContractError,
                XRayStudyScreeningContractError,
                XRaySystemAnalysisContractError,
                XRayReportGenerationContractError,
            ) as exc:
                raise GatewayContractError(str(exc)) from exc
            execution = GatewayExecutionResult(
                provider_request_id=provider_request_id_audit,
                actual_model=actual_model,
                usage_json=usage_json_audit,
                parsed_result_json=parsed_result,
                response_sha256=response_sha256_audit,
                duration_ms=max(0, round((monotonic() - started) * 1000)),
                transport_mode="json",
            )
        except GatewayContractError as exc:
            provider_response_observed = all(
                value is not None
                for value in (
                    provider_request_id_audit,
                    actual_model_audit,
                    response_sha256_audit,
                )
            )
            raise GatewayDefiniteResponseError(
                str(exc),
                image_receipt=image_receipt,
                image_manifest_sha256=image_manifest_sha256,
                image_count_sent=image_count_sent,
                provider_request_id=(
                    provider_request_id_audit if provider_response_observed else None
                ),
                actual_model=actual_model_audit if provider_response_observed else None,
                usage_json=usage_json_audit if provider_response_observed else None,
                response_sha256=(
                    response_sha256_audit if provider_response_observed else None
                ),
            ) from exc
        return {
            "execution": execution,
            "image_receipt": image_receipt,
            "image_manifest_sha256": image_manifest_sha256,
            "image_count_sent": image_count_sent,
        }

    async def finalize_attempt(
        self,
        *,
        attempt_id: str,
        execution: GatewayExecutionResult,
        image_receipt: Mapping[str, Any],
        image_manifest_sha256: str | None,
        image_count_sent: int,
    ) -> dict[str, Any]:
        """Boundary C: persist an accepted Attempt and CAS the Logical Call winner."""
        attempt = await self.attempt_dal.get_by_id_for_update(attempt_id)
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_not_found")
        call = await self.call_dal.get_by_id_for_update(attempt.ai_call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        if attempt.status in {"succeeded", "failed", "cancelled"}:
            return self._structured_call_response(
                call=call,
                attempt=attempt,
                winner=call.winner_attempt_id == attempt.id,
            )
        if attempt.status not in {"prepared", "unknown"}:
            raise AIRequestStateConflict("ai_call_attempt_finalize_state_invalid")
        now = datetime.utcnow()
        updated_attempt = await self.attempt_dal.cas_update(
            attempt_id=attempt.id,
            expected_version=attempt.state_version,
            values={
                "actual_model": execution.actual_model,
                "usage_json": execution.usage_json,
                "response_sha256": execution.response_sha256,
                "parsed_result_json": execution.parsed_result_json,
                "provider_request_id": execution.provider_request_id,
                "sent_image_manifest_sha256": image_manifest_sha256,
                "image_count_sent": image_count_sent,
                "image_receipt_json": dict(image_receipt),
                "error_code": None,
                "status": "succeeded",
                "finished_at": now,
                "next_reconcile_at": None,
            },
        )
        if updated_attempt is None:
            terminal = await self._terminal_attempt_response_or_conflict(
                attempt_id=attempt.id,
            )
            if terminal is not None:
                return terminal
            raise AIRequestStateConflict("ai_call_attempt_finalize_conflict")
        call = await self._cancel_pending_call_for_task(
            call=call,
            task=task,
            now=now,
        )
        if (
            call.winner_attempt_id is not None
            or call.status
            in {
                "succeeded",
                "failed",
                "cancelled",
            }
            or call.result_disposition
            in {
                "accepted",
                "rejected",
                "failed",
                "cancelled",
            }
        ):
            return self._structured_call_response(
                call=call,
                attempt=updated_attempt,
                winner=False,
            )
        updated_call = await self.call_dal.cas_update(
            call_id=call.id,
            expected_version=call.state_version,
            values={
                "status": "succeeded",
                "result_disposition": "accepted",
                "winner_attempt_id": updated_attempt.id,
                "provider_request_id": execution.provider_request_id,
                "actual_model": execution.actual_model,
                "sent_image_manifest_sha256": image_manifest_sha256,
                "image_count_sent": image_count_sent,
                "image_receipt_json": dict(image_receipt),
                "parsed_result_json": execution.parsed_result_json,
                "response_sha256": execution.response_sha256,
                "finished_at": now,
            },
        )
        if updated_call is None:
            raise AIRequestStateConflict("ai_call_winner_cas_conflict")
        return self._structured_call_response(
            call=updated_call,
            attempt=updated_attempt,
            winner=True,
        )

    async def finalize_attempt_failure(
        self,
        *,
        attempt_id: str,
        error_code: str,
        unknown: bool,
        reconcile_after_seconds: int = 300,
        image_receipt: Mapping[str, Any] | None = None,
        image_manifest_sha256: str | None = None,
        image_count_sent: int | None = None,
        provider_request_id: str | None = None,
        actual_model: str | None = None,
        usage_json: Mapping[str, Any] | None = None,
        response_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Boundary C: persist a definite failure or an uncertain delivery."""
        delivery_values: dict[str, Any] = {}
        delivery_facts = (
            image_receipt,
            image_manifest_sha256,
            image_count_sent,
        )
        if any(value is not None for value in delivery_facts):
            if (
                unknown
                or not isinstance(image_receipt, Mapping)
                or not isinstance(image_manifest_sha256, str)
                or len(image_manifest_sha256) != 64
                or not isinstance(image_count_sent, int)
                or isinstance(image_count_sent, bool)
                or image_count_sent < 0
                or image_receipt.get("image_count") != image_count_sent
            ):
                raise AIRequestStateConflict("ai_call_attempt_delivery_audit_invalid")
            delivery_values = {
                "sent_image_manifest_sha256": image_manifest_sha256,
                "image_count_sent": image_count_sent,
                "image_receipt_json": dict(image_receipt),
            }
        provider_response_values: dict[str, Any] = {}
        provider_call_values: dict[str, Any] = {}
        provider_response_facts = (
            provider_request_id,
            actual_model,
            usage_json,
            response_sha256,
        )
        if any(value is not None for value in provider_response_facts):
            normalized_provider_request_id = (
                provider_request_id.strip()
                if isinstance(provider_request_id, str)
                else ""
            )
            normalized_actual_model = (
                actual_model.strip() if isinstance(actual_model, str) else ""
            )
            if (
                unknown
                or not normalized_provider_request_id
                or len(normalized_provider_request_id) > 160
                or not normalized_actual_model
                or len(normalized_actual_model) > 128
                or not isinstance(response_sha256, str)
                or len(response_sha256) != 64
                or response_sha256 != response_sha256.lower()
                or any(
                    character not in "0123456789abcdef"
                    for character in response_sha256
                )
                or (usage_json is not None and not isinstance(usage_json, Mapping))
            ):
                raise AIRequestStateConflict(
                    "ai_call_attempt_provider_response_audit_invalid"
                )
            provider_response_values = {
                "provider_request_id": normalized_provider_request_id,
                "actual_model": normalized_actual_model,
                "usage_json": (
                    dict(usage_json) if isinstance(usage_json, Mapping) else None
                ),
                "response_sha256": response_sha256,
            }
            provider_call_values = {
                "provider_request_id": normalized_provider_request_id,
                "actual_model": normalized_actual_model,
                "response_sha256": response_sha256,
            }
        attempt = await self.attempt_dal.get_by_id_for_update(attempt_id)
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_not_found")
        call = await self.call_dal.get_by_id_for_update(attempt.ai_call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        if attempt.status in {"succeeded", "failed", "cancelled"} or (
            attempt.status == "unknown" and unknown
        ):
            return self._structured_call_response(
                call=call,
                attempt=attempt,
                winner=call.winner_attempt_id == attempt.id,
            )
        if attempt.status not in {"prepared", "unknown"}:
            raise AIRequestStateConflict("ai_call_attempt_failure_state_invalid")
        now = datetime.utcnow()
        values: dict[str, Any] = {
            "error_code": (error_code or "provider_unknown")[:80],
            "finished_at": now,
            **delivery_values,
            **provider_response_values,
        }
        if unknown:
            values["status"] = "unknown"
            if attempt.first_unknown_at is None:
                values["first_unknown_at"] = now
            values["next_reconcile_at"] = now + timedelta(
                seconds=max(30, reconcile_after_seconds)
            )
        else:
            values["status"] = "failed"
            values["next_reconcile_at"] = None
        updated_attempt = await self.attempt_dal.cas_update(
            attempt_id=attempt.id,
            expected_version=attempt.state_version,
            values=values,
        )
        if updated_attempt is None:
            terminal = await self._terminal_attempt_response_or_conflict(
                attempt_id=attempt.id,
            )
            if terminal is not None:
                return terminal
            raise AIRequestStateConflict("ai_call_attempt_failure_conflict")
        call = await self._cancel_pending_call_for_task(
            call=call,
            task=task,
            now=now,
        )
        call_values: dict[str, Any] = {}
        if delivery_values and call.winner_attempt_id is None:
            call_values.update(delivery_values)
        if provider_call_values and call.winner_attempt_id is None:
            call_values.update(provider_call_values)
        if (
            not unknown
            and call.winner_attempt_id is None
            and call.status in {"prepared", "running"}
            and call.result_disposition == "pending"
        ):
            call_values.update(
                {
                    "status": "failed",
                    "result_disposition": "failed",
                    "error_code": values["error_code"],
                    "finished_at": now,
                }
            )
        if call_values:
            updated_call = await self.call_dal.cas_update(
                call_id=call.id,
                expected_version=call.state_version,
                values=call_values,
            )
            if updated_call is None:
                raise AIRequestStateConflict("ai_call_failure_cas_conflict")
            call = updated_call
        return self._structured_call_response(
            call=call,
            attempt=updated_attempt,
            winner=False,
        )

    async def _terminal_attempt_response_or_conflict(
        self, *, attempt_id: str
    ) -> dict[str, Any] | None:
        """Return an already-terminal Attempt's facts, or None if it is still live."""
        current = await self.attempt_dal.get_by_id(attempt_id)
        if current is None or current.status not in {
            "succeeded",
            "failed",
            "unknown",
            "cancelled",
        }:
            return None
        call = await self.call_dal.get_by_id(current.ai_call_id)
        if call is None:
            return None
        return self._structured_call_response(
            call=call,
            attempt=current,
            winner=call.winner_attempt_id == current.id,
        )

    @classmethod
    def _structured_call_response(
        cls,
        *,
        call: Any,
        attempt: Any | None,
        winner: bool,
    ) -> dict[str, Any]:
        return {
            "call_id": call.id,
            "attempt_id": attempt.id if attempt is not None else None,
            "attempt_status": attempt.status if attempt is not None else None,
            "status": call.status,
            "result_disposition": call.result_disposition,
            "winner": winner,
            "error_code": call.error_code
            or (attempt.error_code if attempt is not None else None),
            "parsed_result_json": call.parsed_result_json,
            "image_receipt_json": getattr(call, "image_receipt_json", None),
            "rendered_prompt_sha256": call.rendered_prompt_sha256,
            "schema_sha256": call.schema_sha256,
            "network_required": bool(
                attempt is not None
                and attempt.status == "prepared"
                and call.status in {"prepared", "running"}
                and call.result_disposition == "pending"
            ),
        }

    @staticmethod
    def _next_task_budget_reservation(
        *,
        current: Any,
        budget_policy_sha256: str,
        max_total_calls: int,
        max_total_attempts: int,
        call_reservation: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate the immutable aggregate and reserve one single-lane Call."""
        expected_keys = {
            "contract_version",
            "budget_policy_sha256",
            "reserved_call_units",
            "reserved_attempts",
        }
        if not isinstance(current, Mapping) or set(current) != expected_keys:
            raise AIRequestStateConflict("task_budget_reservation_invalid")
        if (
            current.get("contract_version") != "task-budget-reservation.v1"
            or current.get("budget_policy_sha256") != budget_policy_sha256
        ):
            raise AIRequestStateConflict("task_budget_reservation_snapshot_mismatch")
        reserved_call_units = current.get("reserved_call_units")
        reserved_attempts = current.get("reserved_attempts")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (reserved_call_units, reserved_attempts)
        ):
            raise AIRequestStateConflict("task_budget_reservation_invalid")
        call_units = call_reservation.get("reserved_call_units")
        call_attempts = call_reservation.get("reserved_attempts")
        if (
            call_units != 1
            or call_attempts != 1
            or not isinstance(call_units, int)
            or not isinstance(call_attempts, int)
        ):
            raise AIRequestStateConflict("ai_call_budget_reservation_invalid")
        if reserved_call_units + call_units > max_total_calls:
            raise AIRequestStateConflict("ai_call_budget_reservation_exceeded")
        if reserved_attempts + call_attempts > max_total_attempts:
            raise AIRequestStateConflict("ai_call_budget_reservation_exceeded")
        return {
            "contract_version": "task-budget-reservation.v1",
            "budget_policy_sha256": budget_policy_sha256,
            "reserved_call_units": reserved_call_units + call_units,
            "reserved_attempts": reserved_attempts + call_attempts,
        }

    async def _load_attempt_image_inputs(
        self,
        *,
        task: Any,
        expected_manifest_sha256: str,
        expected_image_count: int,
    ) -> tuple[dict[str, Any], ...]:
        """Resolve immutable image object facts and verify every frozen series hash."""
        if (
            not isinstance(expected_image_count, int)
            or isinstance(expected_image_count, bool)
            or expected_image_count < 0
        ):
            raise AIRequestStateConflict("ai_call_image_count_invalid")
        snapshot = task.request_snapshot_json or {}
        if snapshot.get("resolved_manifest_sha256") != expected_manifest_sha256:
            raise AIRequestStateConflict("ai_call_image_manifest_mismatch")
        if expected_image_count == 0:
            return ()
        if snapshot.get("snapshot_contract_version") == TASK_REQUEST_SNAPSHOT_V3:
            try:
                frozen_series = validate_frozen_study_series(
                    snapshot.get("series"),
                    resolved_manifest_sha256=expected_manifest_sha256,
                )
            except ManifestContractError as exc:
                raise AIRequestStateConflict(str(exc)) from exc
            image_inputs: list[dict[str, Any]] = []
            for series_item in frozen_series:
                for item in series_item["ordered_images"]:
                    image_inputs.append(
                        {
                            "sequence_no": len(image_inputs) + 1,
                            "series_id": series_item["series_id"],
                            "series_manifest_sha256": series_item["manifest_sha256"],
                            "series_sequence_no": item["sequence_no"],
                            "image_id": item["image_id"],
                            "logical_image_key": item["logical_image_key"],
                            "image_version_no": item["image_version_no"],
                            "projection": item["projection"],
                            "projection_provenance": item["projection_provenance"],
                            "storage_profile": item["storage_profile"],
                            "object_key": item["object_key"],
                            "object_version_id": item["object_version_id"],
                            "mime_type": item["content_type"],
                            "sha256": item["sha256"],
                            "size_bytes": item["size_bytes"],
                        }
                    )
            if len(image_inputs) != expected_image_count:
                raise AIRequestStateConflict("ai_call_image_count_mismatch")
            return tuple(image_inputs)
        series_snapshot = snapshot.get("series")
        if not isinstance(series_snapshot, list):
            raise AIRequestStateConflict("ai_call_image_manifest_invalid")

        image_inputs: list[dict[str, Any]] = []
        sequence_no = 1
        for series_item in series_snapshot:
            if not isinstance(series_item, Mapping):
                raise AIRequestStateConflict("ai_call_image_manifest_invalid")
            series_id = series_item.get("series_id")
            manifest_sha256 = series_item.get("manifest_sha256")
            actual_image_count = series_item.get("actual_image_count")
            if (
                not isinstance(series_id, str)
                or not series_id
                or not isinstance(manifest_sha256, str)
                or len(manifest_sha256) != 64
                or not isinstance(actual_image_count, int)
                or isinstance(actual_image_count, bool)
                or actual_image_count < 0
            ):
                raise AIRequestStateConflict("ai_call_image_manifest_invalid")
            images = await self.image_dal.list_ready_for_series(series_id)
            try:
                manifest = build_series_manifest_legacy(images)
            except ManifestContractError as exc:
                raise AIRequestStateConflict(str(exc)) from exc
            if (
                manifest.sha256 != manifest_sha256
                or len(manifest.items) != actual_image_count
            ):
                raise AIRequestStateConflict("ai_call_image_manifest_mismatch")
            for item in manifest.items:
                image_inputs.append(
                    {
                        "sequence_no": sequence_no,
                        "series_id": series_id,
                        "image_id": item["image_id"],
                        "storage_profile": item["storage_profile"],
                        "object_key": item["object_key"],
                        "object_version_id": item["object_version_id"],
                        "mime_type": item["content_type"],
                        "sha256": item["sha256"],
                        "size_bytes": item["size_bytes"],
                    }
                )
                sequence_no += 1
        if len(image_inputs) != expected_image_count:
            raise AIRequestStateConflict("ai_call_image_count_mismatch")
        return tuple(image_inputs)

    @staticmethod
    def _stage_manifest_sha256(*, stage: Any) -> str:
        manifest_sha = (stage.input_json or {}).get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise AIRequestStateConflict("ai_call_manifest_missing")
        return manifest_sha

    @staticmethod
    def _xray_image_contract_required(
        *, config: Any, task: Any, stage: Any | None = None
    ) -> bool:
        if getattr(stage, "stage_key", None) == "report_generation":
            return False
        snapshot = task.request_snapshot_json or {}
        if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
            return False
        if config is None:
            return True
        return requires_xray_runtime_image_contract(
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=snapshot.get("profile_key", config.profile_key),
        )

    @staticmethod
    def _require_xray_image_count(
        *, config: Any, task: Any, image_count: int, stage: Any | None = None
    ) -> None:
        if not AIRequestService._xray_image_contract_required(
            config=config,
            task=task,
            stage=stage,
        ):
            return
        try:
            require_xray_study_image_count(image_count)
        except ValueError as exc:
            raise AIRequestStateConflict(
                "ai_call_xray_image_count_out_of_range"
            ) from exc

    @staticmethod
    def _v2_image_count(*, task: Any, stage: Any) -> int:
        if getattr(stage, "stage_key", None) == "report_generation":
            return 0
        snapshot = task.request_snapshot_json or {}
        series = snapshot.get("series")
        if not isinstance(series, list):
            raise AIRequestStateConflict("task_config_snapshot_mismatch")
        image_count = 0
        for item in series:
            if not isinstance(item, Mapping):
                raise AIRequestStateConflict("task_config_snapshot_mismatch")
            count = item.get("actual_image_count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise AIRequestStateConflict("task_config_snapshot_mismatch")
            image_count += count
        return image_count

    @staticmethod
    def _v2_safe_variables(
        *, config: Any, prompt_command: XRayPromptCommand
    ) -> dict[str, Any]:
        try:
            required, optional = PromptRenderer.declared_variables(
                config.prompt_variables_json
            )
        except PromptRenderError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        candidates: dict[str, Any] = {
            "SAFE_STUDY_CONTEXT_JSON": prompt_command.safe_context,
            "base_info": prompt_command.safe_context,
            "study_context": prompt_command.safe_context,
            "OUTPUT_SCHEMA_JSON": config.output_schema_json,
            "output_schema": config.output_schema_json,
            "schema": config.output_schema_json,
        }
        if prompt_command.primary_complete_result is not None:
            candidates.update(
                {
                    "PRIMARY_RESULT_JSON": prompt_command.primary_complete_result,
                    "previous_answer": prompt_command.primary_complete_result,
                    "primary_result": prompt_command.primary_complete_result,
                }
            )
        if prompt_command.quality_results is not None:
            candidates["QUALITY_RESULTS_JSON"] = prompt_command.quality_results
        if prompt_command.route_context is not None:
            candidates["ROUTE_CONTEXT_JSON"] = prompt_command.route_context
        if prompt_command.study_screening_result is not None:
            candidates["STUDY_SCREENING_RESULT_JSON"] = (
                prompt_command.study_screening_result
            )
        if prompt_command.system_analysis_result is not None:
            candidates["SYSTEM_ANALYSIS_RESULT_JSON"] = (
                prompt_command.system_analysis_result
            )
        if prompt_command.final_medical_result is not None:
            candidates["FINAL_MEDICAL_RESULT_JSON"] = (
                prompt_command.final_medical_result
            )
        candidates["REPORT_SCHEMA_JSON"] = config.output_schema_json
        allowed = required | optional
        return {name: candidates[name] for name in allowed if name in candidates}

    @staticmethod
    def _report_generation_expected(*, stage: Any) -> dict[str, Any] | None:
        if stage.stage_key != "report_generation":
            return None
        stage_input = stage.input_json or {}
        previous_output = stage_input.get("previous_output")
        source_result_sha256 = stage_input.get("previous_output_sha256")
        final_medical_result = (
            previous_output.get("complete_medical_result")
            if isinstance(previous_output, Mapping)
            else None
        )
        if (
            not isinstance(source_result_sha256, str)
            or len(source_result_sha256) != 64
            or not isinstance(final_medical_result, Mapping)
        ):
            raise AIRequestStateConflict(
                "report_generation_expected_result_missing"
            )
        return {
            "source_result_sha256": source_result_sha256,
            "final_medical_result": dict(final_medical_result),
        }

    @staticmethod
    def _validate_v1_task_config_snapshot(*, task: Any, config: Any) -> None:
        snapshot = task.request_snapshot_json or {}
        expected = {
            "ai_config_id": config.id,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "prompt_bundle_sha256": config.prompt_bundle_json["bundle_sha256"],
            "schema_bundle_sha256": config.schema_bundle_json["bundle_sha256"],
        }
        if any(snapshot.get(key) != value for key, value in expected.items()):
            raise AIRequestStateConflict("task_config_snapshot_mismatch")

    async def _resolve_task_stage_config(self, *, task: Any, stage: Any) -> Any:
        snapshot = task.request_snapshot_json or {}
        bindings = snapshot.get("stage_ai_config_bindings")
        config_id = task.ai_config_id
        if bindings is not None:
            if not isinstance(bindings, Mapping):
                raise AIRequestStateConflict("task_config_snapshot_mismatch")
            binding = bindings.get(stage.stage_key)
            if binding is not None:
                if not isinstance(binding, Mapping):
                    raise AIRequestStateConflict("task_config_snapshot_mismatch")
                config_id = binding.get("ai_config_id")
                if not isinstance(config_id, str) or not config_id:
                    raise AIRequestStateConflict("task_config_snapshot_mismatch")
        config = await self.config_dal.get_by_id(config_id)
        if config is None:
            raise AIRequestStateConflict("ai_call_config_not_found")
        return config

    @classmethod
    def _validate_v2_task_config_snapshot(
        cls, *, task: Any, stage: Any, config: Any
    ) -> None:
        snapshot = task.request_snapshot_json or {}
        if snapshot.get("snapshot_contract_version") not in {
            TASK_REQUEST_SNAPSHOT_V2,
            TASK_REQUEST_SNAPSHOT_V3,
        }:
            raise AIRequestStateConflict("task_config_snapshot_mismatch")

        bindings = snapshot.get("stage_ai_config_bindings")
        if bindings is not None and not isinstance(bindings, Mapping):
            raise AIRequestStateConflict("task_config_snapshot_mismatch")
        binding = bindings.get(stage.stage_key) if isinstance(bindings, Mapping) else None
        if binding is None:
            expected = {
                "ai_config_id": config.id,
                "config_key": config.config_key,
                "config_version": config.version,
                "config_contract_version": config.config_contract_version,
                "config_sha256": config.config_sha256,
                "release_fingerprint": config.release_fingerprint,
                "prompt_content_sha256": config.prompt_content_sha256,
                "model_snapshot_sha256": config.model_snapshot_sha256,
                "output_schema_sha256": config.output_schema_sha256,
                "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
                "stage_registry_contract_version": (
                    config.stage_registry_contract_version
                ),
            }
            if (
                any(snapshot.get(key) != value for key, value in expected.items())
                or task.ai_config_id != config.id
                or task.compiled_pipeline_sha256
                != config.compiled_pipeline_sha256
                or task.stage_registry_contract_version
                != config.stage_registry_contract_version
            ):
                raise AIRequestStateConflict("task_config_snapshot_mismatch")
            return

        if not isinstance(binding, Mapping):
            raise AIRequestStateConflict("task_config_snapshot_mismatch")
        species = snapshot.get("species")
        if stage.stage_key == "study_screening":
            expected_root_profile = snapshot.get("profile_key")
            if expected_root_profile == XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1:
                expected_stage_profile = XRAY_STUDY_SCREENING_PROFILE_V2
            else:
                expected_root_profile = XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1
                expected_stage_profile = XRAY_STUDY_SCREENING_PROFILE_V1
            expected_config_key = cls.STUDY_SCREENING_CONFIG_KEYS.get(species or "")
            expected_prompt_key = cls.STUDY_SCREENING_PROMPT_KEYS.get(species or "")
        elif stage.stage_key == "system_analysis":
            expected_root_profile = XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
            expected_stage_profile = XRAY_SYSTEM_ANALYSIS_PROFILE_V1
            expected_config_key = cls.SYSTEM_ANALYSIS_CONFIG_KEYS.get(species or "")
            expected_prompt_key = cls.SYSTEM_ANALYSIS_PROMPT_KEYS.get(species or "")
        elif stage.stage_key == "targeted_review":
            expected_root_profile = snapshot.get("profile_key")
            if expected_root_profile not in {
                XRAY_TARGETED_REVIEW_PROFILE_V2,
                XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
            }:
                raise AIRequestStateConflict("task_config_snapshot_mismatch")
            expected_stage_profile = XRAY_TARGETED_REVIEW_PROFILE_V2
            expected_config_key = cls.TARGETED_REVIEW_CONFIG_KEYS.get(species or "")
            expected_prompt_key = cls.TARGETED_REVIEW_PROMPT_KEYS.get(species or "")
        elif stage.stage_key == "report_generation":
            expected_root_profile = XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
            expected_stage_profile = XRAY_REPORT_GENERATION_PROFILE_V1
            expected_config_key = cls.REPORT_GENERATION_CONFIG_KEYS.get(species or "")
            expected_prompt_key = cls.REPORT_GENERATION_PROMPT_KEYS.get(species or "")
        else:
            raise AIRequestStateConflict("task_config_snapshot_mismatch")
        expected_binding = {
            "ai_config_id": config.id,
            "config_key": config.config_key,
            "config_version": config.version,
            "profile_key": config.profile_key,
            "prompt_key": config.prompt_key,
            "activation_scope": config.activation_scope,
            "scope_key": config.scope_key,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "prompt_content_sha256": config.prompt_content_sha256,
            "model_snapshot_sha256": config.model_snapshot_sha256,
            "output_schema_sha256": config.output_schema_sha256,
            "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
            "stage_registry_contract_version": (
                config.stage_registry_contract_version
            ),
            "budget_policy_sha256": sha256_json(config.budget_policy_json),
        }
        reserved_budget = task.budget_reserved_json
        if (
            snapshot.get("profile_key") != expected_root_profile
            or snapshot.get("snapshot_contract_version")
            != TASK_REQUEST_SNAPSHOT_V3
            or task.task_type != "diagnose"
            or species not in {"cat", "dog"}
            or config.profile_key != expected_stage_profile
            or config.task_type != "diagnose"
            or expected_config_key is None
            or config.config_key != expected_config_key
            or expected_prompt_key is None
            or config.prompt_key != expected_prompt_key
            or any(binding.get(key) != value for key, value in expected_binding.items())
            or not isinstance(reserved_budget, Mapping)
            or reserved_budget.get("budget_policy_sha256")
            != sha256_json(task.budget_snapshot_json)
            or task.compiled_pipeline_sha256
            != snapshot.get("compiled_pipeline_sha256")
            or task.stage_registry_contract_version
            != snapshot.get("stage_registry_contract_version")
        ):
            raise AIRequestStateConflict("task_config_snapshot_mismatch")

    @staticmethod
    def _call_response(call: Any) -> dict[str, Any]:
        return {
            "call_id": call.id,
            "attempt_id": None,
            "attempt_status": None,
            "status": call.status,
            "result_disposition": call.result_disposition,
            "winner": False,
            "error_code": call.error_code,
            "parsed_result_json": call.parsed_result_json,
            "image_receipt_json": getattr(call, "image_receipt_json", None),
            "rendered_prompt_sha256": call.rendered_prompt_sha256,
            "schema_sha256": call.schema_sha256,
            "network_required": False,
        }

    @staticmethod
    def _sha(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
