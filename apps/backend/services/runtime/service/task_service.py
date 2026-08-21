import hashlib
import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import CallerContext
from apps.backend.core.pipeline import (
    ZERO_MODEL_PROFILE,
    build_default_registry,
    compile_profile_contract,
)
from apps.backend.crud.ai_config_record import AIConfigRecordDal
from apps.backend.crud.outbox import OutboxDal
from apps.backend.crud.series import SeriesDal
from apps.backend.crud.session import SessionDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.crud.study import StudyDal
from apps.backend.crud.task import TaskDal
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.task import TaskCreate, TaskResponse


class TaskServiceError(ValueError):
    pass


class TaskNotFoundError(TaskServiceError):
    pass


class TaskAccessDeniedError(TaskServiceError):
    pass


class TaskStateConflictError(TaskServiceError):
    pass


class TaskIdempotencyConflictError(TaskServiceError):
    pass


class TaskService:
    ZERO_MODEL_CONFIG_KEY = "zero_model_replay"
    DIAGNOSE_CONFIG_KEY = "xray_diagnose"
    TASK_CONFIG_KEYS = {
        "replay": ZERO_MODEL_CONFIG_KEY,
        "diagnose": DIAGNOSE_CONFIG_KEY,
    }
    TASK_PROFILES = {
        "replay": frozenset({ZERO_MODEL_PROFILE}),
        "diagnose": frozenset({"xray_primary_v1", "xray_targeted_review_v1"}),
    }

    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)
        self.study_dal = StudyDal(db)
        self.series_dal = SeriesDal(db)
        self.config_dal = AIConfigRecordDal(db)
        self.task_dal = TaskDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.outbox_dal = OutboxDal(db)
        self.registry = build_default_registry()

    @staticmethod
    def _response(task) -> TaskResponse:
        return TaskResponse.model_validate(task)

    async def create_task(
        self, *, payload: TaskCreate, caller: CallerContext
    ) -> TaskResponse:
        config_key = self.TASK_CONFIG_KEYS.get(payload.task_type)
        allowed_profiles = self.TASK_PROFILES.get(payload.task_type)
        if config_key is None or allowed_profiles is None:
            raise TaskStateConflictError("task_type_not_supported")
        study = await self.study_dal.get_by_id(payload.study_id)
        if study is None:
            raise TaskNotFoundError("study_not_found")
        session = await self.session_dal.get_by_id(study.session_id)
        if session is None:
            raise TaskNotFoundError("session_not_found")
        if session.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        if (
            study.status != "ready"
            or study.revision_id != payload.study_revision_id
            or not study.resolved_manifest_sha256
        ):
            raise TaskStateConflictError("study_revision_not_ready")
        activation_slot = (
            f"{config_key}:global:global:{study.modality_type}:{payload.task_type}"
        )
        config = await self.config_dal.get_active(activation_slot)
        if config is None:
            raise TaskStateConflictError("task_config_not_active")
        if (
            config.status != "active"
            or config.capability_manifest_json.get("provider_disabled") is not True
            or config.provider_plan_json.get("enabled") is not False
        ):
            raise TaskStateConflictError("task_config_invalid")
        profile_key = config.compiled_pipeline_json.get("profile_key")
        if profile_key not in allowed_profiles:
            raise TaskStateConflictError("task_profile_not_allowed")
        contract, profile_sha = compile_profile_contract(profile_key, self.registry)
        if (
            profile_sha != config.compiled_pipeline_sha256
            or config.stage_registry_contract_version != self.registry.CONTRACT_VERSION
        ):
            raise TaskStateConflictError("config_profile_fingerprint_conflict")
        if not contract.get("stages"):
            raise TaskStateConflictError("compiled_profile_empty")
        first_definition = contract["stages"][0]
        if first_definition.get("stage_key") != "study_preparation":
            raise TaskStateConflictError("compiled_profile_entry_invalid")

        series = await self.series_dal.list_for_study(study.id)
        run_mode = "replay" if payload.task_type == "replay" else "validation_only"
        report_required = payload.task_type == "diagnose"
        snapshot = {
            "study_id": study.id,
            "study_revision_id": study.revision_id,
            "resolved_manifest_sha256": study.resolved_manifest_sha256,
            "series": [
                {
                    "series_id": item.id,
                    "manifest_sha256": item.manifest_sha256,
                    "actual_image_count": item.actual_image_count,
                }
                for item in series
            ],
            "ai_config_id": config.id,
            "config_key": config.config_key,
            "config_version": config.version,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "prompt_bundle_sha256": config.prompt_bundle_json["bundle_sha256"],
            "schema_bundle_sha256": config.schema_bundle_json["bundle_sha256"],
            "profile_key": profile_key,
            "compiled_profile": contract,
        }
        request_sha = self._sha(snapshot)
        business_key = self._sha(
            {
                "requester_id": caller.subject_id,
                "request_id": payload.request_id,
                "task_type": payload.task_type,
            }
        )
        existing = await self.task_dal.get_by_business_key(business_key)
        if existing is not None:
            self._ensure_idempotent_task(
                task=existing,
                study_id=study.id,
                study_revision_id=study.revision_id,
                config_id=config.id,
                request_sha=request_sha,
            )
            return self._response(existing)

        task_id = new_opaque_id()
        stage_id = new_opaque_id()
        stage_input = {
            "task_id": task_id,
            "study_revision_id": study.revision_id,
            "manifest_sha256": study.resolved_manifest_sha256,
        }
        stage_input_sha = self._sha(stage_input)
        assignment_sha = self._sha(
            {
                "config_id": config.id,
                "config_sha256": config.config_sha256,
                "release_fingerprint": config.release_fingerprint,
                "profile": profile_sha,
                "task_type": payload.task_type,
                "run_mode": run_mode,
            }
        )
        task_values = {
            "id": task_id,
            "study_id": study.id,
            "requester_id": caller.subject_id,
            "request_id": payload.request_id,
            "task_type": payload.task_type,
            "business_key": business_key,
            "contract_version": "task.v1",
            "ai_config_id": config.id,
            "compiled_pipeline_sha256": profile_sha,
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "routing_policy_version": "control-plane.v1",
            "assignment_sha256": assignment_sha,
            "study_revision_id": study.revision_id,
            "report_required": report_required,
            "run_mode": run_mode,
            "experiment_arm_id": None,
            "execution_status": "queued",
            "ai_medical_status": "not_produced",
            "state_version": 0,
            "request_snapshot_json": snapshot,
            "request_sha256": request_sha,
            "budget_snapshot_json": config.budget_policy_json,
            "budget_reserved_json": {},
            "budget_consumed_json": {},
            "current_report_id": None,
            "attempt_no": 1,
            "trace_id": payload.trace_id,
        }
        task = await self.task_dal.create_idempotent(task_values)
        if task is None:
            existing = await self.task_dal.get_by_business_key(business_key)
            if existing is None:
                raise TaskIdempotencyConflictError("task_create_conflict")
            self._ensure_idempotent_task(
                task=existing,
                study_id=study.id,
                study_revision_id=study.revision_id,
                config_id=config.id,
                request_sha=request_sha,
            )
            return self._response(existing)
        stage = await self.stage_dal.create_idempotent(
            {
                "id": stage_id,
                "task_id": task.id,
                "task_attempt_no": 1,
                "stage_instance_key": f"{first_definition['stage_key']}:1",
                "stage_no": 1,
                "stage_key": first_definition["stage_key"],
                "handler_key": first_definition["handler_key"],
                "handler_version": first_definition["handler_version"],
                "status": "queued",
                "state_version": 0,
                "lease_generation": 0,
                "input_json": stage_input,
                "input_sha256": stage_input_sha,
                "retry_count": 0,
            }
        )
        if stage is None:
            raise TaskStateConflictError("first_stage_create_conflict")
        message = {
            "task_id": task.id,
            "stage_checkpoint_id": stage.id,
            "expected_state_version": stage.state_version,
            "trace_id": payload.trace_id,
        }
        event = await self.outbox_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "aggregate_type": "stage",
                "aggregate_id": stage.id,
                "aggregate_version": stage.state_version,
                "event_key": f"stage:{stage.id}:execute:{stage.state_version}",
                "event_type": "execute_stage",
                "destination_key": OutboxDal.STAGE_DESTINATION_KEY,
                "trace_id": payload.trace_id,
                "message_version": OutboxDal.STAGE_MESSAGE_VERSION,
                "message_json": message,
                "message_sha256": OutboxDal.message_sha256(message),
                "publish_status": "pending",
                "publish_attempt_count": 0,
            }
        )
        if event is None:
            raise TaskStateConflictError("first_stage_event_conflict")
        return self._response(task)

    @staticmethod
    def _ensure_idempotent_task(
        *, task, study_id: str, study_revision_id: str, config_id: str, request_sha: str
    ) -> None:
        if (
            task.study_id != study_id
            or task.study_revision_id != study_revision_id
            or task.ai_config_id != config_id
            or task.request_sha256 != request_sha
        ):
            raise TaskIdempotencyConflictError("task_idempotency_conflict")

    async def get_task(self, *, task_id: str, caller: CallerContext) -> TaskResponse:
        task = await self.task_dal.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError("task_not_found")
        if task.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        return self._response(task)

    async def cancel_task(
        self,
        *,
        task_id: str,
        expected_version: int,
        reason: str | None,
        caller: CallerContext,
    ) -> TaskResponse:
        task = await self.task_dal.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError("task_not_found")
        if task.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        if task.cancel_requested_at is not None:
            return self._response(task)
        if (
            task.execution_status in {"completed", "failed", "cancelled", "dead_letter"}
            or task.state_version != expected_version
        ):
            raise TaskStateConflictError("task_cancel_conflict")
        updated = await self.task_dal.cas_update(
            task_id=task.id,
            expected_version=expected_version,
            values={
                "cancel_requested_by_id": caller.subject_id,
                "cancel_reason": (reason or "caller_cancelled")[:200],
                "cancel_requested_at": datetime.utcnow(),
            },
        )
        if updated is None:
            raise TaskStateConflictError("task_cancel_conflict")
        return self._response(updated)

    @staticmethod
    def _sha(value: dict) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
