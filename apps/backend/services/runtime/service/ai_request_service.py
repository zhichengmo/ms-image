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
from apps.backend.core.pipeline import build_default_registry
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

    async def prepare_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
        trace_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Prepare one durable Logical Call and state whether network I/O is required."""
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None:
            raise AIRequestStateConflict("ai_call_config_not_found")
        if not is_v2_config(config):
            result = await self._prepare_v1_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
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
            )
        if not self._runtime_gate_allows():
            return await self._prepare_v2_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
                terminal_error_code="ai_gateway_runtime_gate_denied",
                provider_disabled_required=False,
            )
        return await self.prepare_structured_call(
            task_id=task_id,
            stage_checkpoint_id=stage_checkpoint_id,
            prompt_command=prompt_command,
            trace_id=trace_id,
            request_id=request_id,
        )

    async def prepare_provider_disabled_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
    ) -> dict[str, Any]:
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        # Runtime is intentionally bound to the Task's immutable Config reference,
        # never to the currently active Config or mutable Prompt/Pool/Connection rows.
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None:
            raise AIRequestStateConflict("ai_call_config_not_found")
        if is_v2_config(config):
            return await self._prepare_v2_provider_disabled_call(
                task=task,
                stage=stage,
                config=config,
                prompt_command=prompt_command,
            )
        return await self._prepare_v1_provider_disabled_call(
            task=task,
            stage=stage,
            config=config,
            prompt_command=prompt_command,
        )

    async def _prepare_v1_provider_disabled_call(
        self,
        *,
        task: Any,
        stage: Any,
        config: Any,
        prompt_command: XRayPromptCommand,
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
        self._validate_v2_task_config_snapshot(task=task, config=config)

        model_snapshot = config.model_snapshot_json
        if not isinstance(model_snapshot, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lanes = model_snapshot.get("lanes")
        if not isinstance(lanes, list) or len(lanes) != 1:
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        lane = lanes[0]
        if not isinstance(lane, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")
        requested_model = lane.get("requested_model")
        if not isinstance(requested_model, str) or not requested_model:
            raise AIRequestStateConflict("ai_call_requested_model_invalid")

        budget_policy = config.budget_policy_json
        (
            max_prompt_chars,
            max_input_images,
            max_total_calls,
            max_total_attempts,
            task_deadline_ms,
        ) = self._validate_v2_budget_policy(budget_policy=budget_policy)

        manifest_sha = self._stage_manifest_sha256(stage=stage)
        image_count = self._v2_image_count(task=task)
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
        )
        budget_policy_sha256 = sha256_json(budget_policy)
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
            "strategy": "race",
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
                "execution_mode": "single",
                "prompt_kind": prompt_command.prompt_kind,
            }
        )
        return request, request_sha, logical_key

    async def prepare_structured_call(
        self,
        *,
        task_id: str,
        stage_checkpoint_id: str,
        prompt_command: XRayPromptCommand,
        trace_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Boundary A: persist a Logical Call plus its first prepared Attempt.

        The caller owns the surrounding transaction and must commit before any
        network I/O starts.  This path is reachable only when the frozen
        ai-gateway-profile is provider-enabled/qualified and the runtime gate
        allows it; otherwise callers must keep the provider-disabled path.
        """
        if not self._runtime_gate_allows():
            raise AIRequestStateConflict("ai_gateway_runtime_gate_denied")
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None:
            raise AIRequestStateConflict("ai_call_config_not_found")
        if not is_v2_config(config) or config.status not in {"active", "retired"}:
            raise AIRequestStateConflict("ai_call_config_state_invalid")
        try:
            gateway_profile = normalize_gateway_profile(config.gateway_profile_json)
        except GatewayContractError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        if (
            not gateway_profile["provider_enabled"]
            or gateway_profile["qualification_status"] != "qualified"
        ):
            raise AIRequestStateConflict("provider_enabled_required")
        try:
            self.config_compiler.verify_frozen_integrity(config)
        except AIControlValidationError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        self._validate_v2_task_config_snapshot(task=task, config=config)

        lane = self._frozen_lane(config=config)
        requested_model = lane.get("requested_model")
        connection_id = lane.get("connection_id")
        connection_sha256 = lane.get("connection_sha256")
        provider_type = lane.get("provider_type")
        api_format = lane.get("api_format")
        generation_params = lane.get("generation_params")
        if any(
            not isinstance(value, str) or not value
            for value in (
                requested_model,
                connection_id,
                connection_sha256,
                provider_type,
                api_format,
            )
        ) or not isinstance(generation_params, Mapping):
            raise AIRequestStateConflict("ai_call_model_snapshot_invalid")

        budget_policy = config.budget_policy_json
        (
            max_prompt_chars,
            max_input_images,
            max_total_calls,
            max_total_attempts,
            task_deadline_ms,
        ) = self._validate_v2_budget_policy(budget_policy=budget_policy)

        manifest_sha = self._stage_manifest_sha256(stage=stage)
        image_count = self._v2_image_count(task=task)
        if image_count > max_input_images:
            raise AIRequestStateConflict("ai_call_image_budget_exceeded")

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
        )
        budget_policy_sha256 = sha256_json(budget_policy)
        now = datetime.utcnow()
        task_created_at = task.created_at
        if not isinstance(task_created_at, datetime):
            raise AIRequestStateConflict("task_created_at_invalid")
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
        call_values = {
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
            "provider_type": provider_type,
            "requested_model": requested_model,
            "request_sha256": request_sha,
            "rendered_prompt_sha256": rendered.rendered_prompt_sha256,
            "rendered_messages_json": rendered_messages.messages_json,
            "schema_sha256": config.output_schema_sha256,
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
                call=prepared,
                attempt=None,
                winner=False,
            )
        existing_attempt = await self.attempt_dal.get_by_call_attempt_no(
            ai_call_id=prepared.id,
            attempt_no=1,
        )
        if existing_attempt is not None:
            return self._structured_call_response(
                call=prepared,
                attempt=existing_attempt,
                winner=False,
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
            call=prepared,
            attempt=attempt,
            winner=False,
        )

    async def prepare_retry_attempt(
        self, *, call_id: str, trace_id: str, request_id: str
    ) -> dict[str, Any]:
        """Boundary A: create a genuinely new Attempt with a new idempotency key."""
        call = await self.call_dal.get_by_id_for_update(call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        self._ensure_task_accepts_new_attempt(task)
        if call.winner_attempt_id is not None:
            raise AIRequestStateConflict("ai_call_winner_already_selected")
        if call.status not in {"prepared", "running"}:
            raise AIRequestStateConflict("ai_call_retry_state_invalid")
        config = await self.config_dal.get_by_id(call.ai_config_id)
        if config is None or config.config_sha256 != call.config_sha256:
            raise AIRequestStateConflict("ai_call_config_snapshot_mismatch")
        lane = self._frozen_lane(config=config)
        reservation = call.budget_reservation_json
        if not isinstance(reservation, Mapping):
            raise AIRequestStateConflict("ai_call_budget_reservation_invalid")
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
                "connection_id": lane["connection_id"],
                "connection_sha256": lane["connection_sha256"],
                "provider_type": lane["provider_type"],
                "api_format": lane["api_format"],
                "requested_model": lane["requested_model"],
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
            call=updated_call,
            attempt=attempt,
            winner=False,
        )

    async def load_attempt_for_network(self, *, attempt_id: str) -> dict[str, Any]:
        """Freeze every fact needed by Boundary B before the DB transaction closes."""
        attempt = await self.attempt_dal.get_by_id(attempt_id)
        if attempt is None:
            raise AIRequestStateConflict("ai_call_attempt_not_found")
        call = await self.call_dal.get_by_id(attempt.ai_call_id)
        if call is None:
            raise AIRequestStateConflict("ai_call_not_found")
        config = await self.config_dal.get_by_id(call.ai_config_id)
        if config is None or config.config_sha256 != call.config_sha256:
            raise AIRequestStateConflict("ai_call_config_snapshot_mismatch")
        try:
            gateway_profile = normalize_gateway_profile(config.gateway_profile_json)
        except GatewayContractError as exc:
            raise AIRequestStateConflict(str(exc)) from exc
        if (
            not gateway_profile["provider_enabled"]
            or gateway_profile["qualification_status"] != "qualified"
        ):
            raise AIRequestStateConflict("provider_enabled_required")
        lane = self._frozen_lane(config=config)
        if (
            lane.get("connection_id") != attempt.connection_id
            or lane.get("connection_sha256") != attempt.connection_sha256
        ):
            raise AIRequestStateConflict("ai_call_attempt_connection_mismatch")
        if attempt.status != "prepared":
            raise AIRequestStateConflict("ai_call_attempt_network_state_invalid")
        if (
            call.status not in {"prepared", "running"}
            or call.result_disposition != "pending"
        ):
            raise AIRequestStateConflict("ai_call_network_state_invalid")
        messages = call.rendered_messages_json
        if not isinstance(messages, list) or not messages:
            raise AIRequestStateConflict("ai_call_rendered_messages_missing")
        task = await self.task_dal.get_by_id_for_update(call.task_id)
        self._ensure_task_accepts_new_attempt(task)
        if call.winner_attempt_id is not None:
            raise AIRequestStateConflict("ai_call_winner_already_selected")
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
            "allowed_actual_models": tuple(gateway_profile["allowed_actual_models"]),
            "generation_params": dict(lane["generation_params"]),
            "response_schema": dict(config.output_schema_json),
            "messages": tuple(dict(item) for item in messages),
            "streaming_mode": gateway_profile["streaming_mode"],
            "timeout_ms": lane["timeout_ms"],
            "provider_idempotency_key": attempt.provider_idempotency_key,
            "image_manifest_sha256": call.requested_image_manifest_sha256,
            "image_count_requested": call.image_count_requested,
            "image_inputs": image_inputs,
            "snapshot_contract_version": (task.request_snapshot_json or {}).get(
                "snapshot_contract_version"
            ),
            "image_url_ttl_seconds": gateway_profile["image_url_ttl_seconds"],
        }

    @staticmethod
    async def execute_gateway_attempt_network(
        *,
        network_plan: Mapping[str, Any],
        gateway_client: GatewayClient | None = None,
        image_signer: AttemptImageSigner | None = None,
    ) -> dict[str, Any]:
        """Boundary B: call ms-ai-platform from frozen facts with no DB access."""
        signer = image_signer or build_oss_attempt_image_signer()
        images = await signer.sign(
            attempt_plan=network_plan,
            ttl_seconds=int(network_plan["image_url_ttl_seconds"]),
        )
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
            content = AIRequestService._provider_message_content(body)
            actual_model = body.get("model") or gateway_request.requested_model
            if not isinstance(actual_model, str) or not actual_model.strip():
                raise GatewayContractError("provider_actual_model_missing")
            actual_model = actual_model.strip()
            allowed_models = set(gateway_request.allowed_actual_models) or {
                gateway_request.requested_model
            }
            if actual_model not in allowed_models:
                raise GatewayContractError("provider_actual_model_mismatch")
            usage = body.get("usage")
            if usage is not None and not isinstance(usage, Mapping):
                raise GatewayContractError("provider_usage_invalid")
            parsed_result = schema_validate_result(
                value=content,
                schema=gateway_request.response_schema,
            )
            try:
                parsed_result = validate_xray_result_contract(
                    result=parsed_result,
                    schema_contract_version=gateway_request.response_schema.get(
                        "x-ms-image-contract-version"
                    ),
                    image_receipt=image_receipt,
                )
            except XRayResultContractError as exc:
                raise GatewayContractError(str(exc)) from exc
            execution = GatewayExecutionResult(
                provider_request_id=provider_request_id.strip(),
                actual_model=actual_model,
                usage_json=dict(usage) if isinstance(usage, Mapping) else None,
                parsed_result_json=parsed_result,
                response_sha256=response_sha256(body),
                duration_ms=max(0, round((monotonic() - started) * 1000)),
                transport_mode="json",
            )
        except GatewayContractError as exc:
            raise GatewayDefiniteResponseError(
                str(exc),
                image_receipt=image_receipt,
                image_manifest_sha256=image_manifest_sha256,
                image_count_sent=image_count_sent,
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
    def _v2_image_count(*, task: Any) -> int:
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
        allowed = required | optional
        return {name: candidates[name] for name in allowed if name in candidates}

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

    @staticmethod
    def _validate_v2_task_config_snapshot(*, task: Any, config: Any) -> None:
        snapshot = task.request_snapshot_json or {}
        if snapshot.get("snapshot_contract_version") not in {
            TASK_REQUEST_SNAPSHOT_V2,
            TASK_REQUEST_SNAPSHOT_V3,
        }:
            raise AIRequestStateConflict("task_config_snapshot_mismatch")
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
            "stage_registry_contract_version": config.stage_registry_contract_version,
        }
        if (
            any(snapshot.get(key) != value for key, value in expected.items())
            or task.ai_config_id != config.id
            or task.compiled_pipeline_sha256 != config.compiled_pipeline_sha256
            or task.stage_registry_contract_version
            != config.stage_registry_contract_version
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
            "rendered_prompt_sha256": call.rendered_prompt_sha256,
            "schema_sha256": call.schema_sha256,
            "network_required": False,
        }

    @staticmethod
    def _sha(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
