import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contexts import CallerContext
from app.core.pipeline import ZERO_MODEL_PROFILE, build_default_registry, compile_profile_contract
from app.crud.ai_config_record import AIConfigRecordDal
from app.crud.outbox import OutboxDal
from app.crud.series import SeriesDal
from app.crud.session import SessionDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.study import StudyDal
from app.crud.task import TaskDal
from app.models.imaging_base import new_opaque_id
from app.schemas.task import TaskCreate, TaskResponse


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

    async def create_task(self, *, payload: TaskCreate, caller: CallerContext) -> TaskResponse:
        if payload.task_type != "replay":
            raise TaskStateConflictError("zero_model_task_type_required")
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
        config = await self.config_dal.get_active(
            f"{self.ZERO_MODEL_CONFIG_KEY}:global:global:{study.modality_type}:replay"
        )
        if config is None:
            raise TaskStateConflictError("zero_model_config_not_active")
        if config.status != "active" or config.capability_manifest_json.get("provider_disabled") is not True:
            raise TaskStateConflictError("zero_model_config_invalid")
        contract, profile_sha = compile_profile_contract(ZERO_MODEL_PROFILE, self.registry)
        if profile_sha != config.compiled_pipeline_sha256:
            raise TaskStateConflictError("config_profile_fingerprint_conflict")
        series = await self.series_dal.list_for_study(study.id)
        snapshot = {
            "study_id": study.id,
            "study_revision_id": study.revision_id,
            "resolved_manifest_sha256": study.resolved_manifest_sha256,
            "series": [
                {"series_id": item.id, "manifest_sha256": item.manifest_sha256, "actual_image_count": item.actual_image_count}
                for item in series
            ],
            "compiled_profile": contract,
        }
        request_sha = self._sha(snapshot)
        business_payload = {
            "requester_id": caller.subject_id,
            "request_id": payload.request_id,
            "study_id": study.id,
            "study_revision_id": study.revision_id,
            "config_id": config.id,
            "request_sha256": request_sha,
        }
        business_key = self._sha(business_payload)
        existing = await self.task_dal.get_by_business_key(business_key)
        if existing is not None:
            return self._response(existing)
        task_id = new_opaque_id()
        stage_id = new_opaque_id()
        stage_input = {"task_id": task_id, "study_revision_id": study.revision_id, "manifest_sha256": study.resolved_manifest_sha256}
        stage_input_sha = self._sha(stage_input)
        task_values = {
            "id": task_id, "study_id": study.id, "requester_id": caller.subject_id,
            "request_id": payload.request_id, "task_type": "replay", "business_key": business_key,
            "contract_version": "task.v1", "ai_config_id": config.id,
            "compiled_pipeline_sha256": profile_sha, "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "routing_policy_version": "control-plane.v1", "assignment_sha256": self._sha({"config_id": config.id, "profile": profile_sha}),
            "study_revision_id": study.revision_id, "report_required": False, "run_mode": "replay", "experiment_arm_id": None,
            "execution_status": "queued", "ai_medical_status": "not_produced", "state_version": 0,
            "request_snapshot_json": snapshot, "request_sha256": request_sha,
            "budget_snapshot_json": config.budget_policy_json, "budget_reserved_json": {}, "budget_consumed_json": {},
            "current_report_id": None, "attempt_no": 1, "trace_id": payload.trace_id,
        }
        task = await self.task_dal.create_idempotent(task_values)
        if task is None:
            existing = await self.task_dal.get_by_business_key(business_key)
            if existing is None or existing.request_sha256 != request_sha:
                raise TaskIdempotencyConflictError("task_idempotency_conflict")
            return self._response(existing)
        stage = await self.stage_dal.create_idempotent({
            "id": stage_id, "task_id": task.id, "task_attempt_no": 1,
            "stage_instance_key": "study_preparation:1", "stage_no": 1,
            "stage_key": "study_preparation", "handler_key": "study_preparation", "handler_version": "v1",
            "status": "queued", "state_version": 0, "lease_generation": 0,
            "input_json": stage_input, "input_sha256": stage_input_sha, "retry_count": 0,
        })
        if stage is None:
            raise TaskStateConflictError("first_stage_create_conflict")
        message = {"task_id": task.id, "stage_checkpoint_id": stage.id, "expected_state_version": stage.state_version, "trace_id": payload.trace_id}
        event = await self.outbox_dal.create_idempotent({
            "id": new_opaque_id(), "aggregate_type": "stage", "aggregate_id": stage.id,
            "aggregate_version": stage.state_version, "event_key": f"stage:{stage.id}:execute:{stage.state_version}",
            "event_type": "execute_stage", "destination_key": OutboxDal.STAGE_DESTINATION_KEY,
            "trace_id": payload.trace_id, "message_version": OutboxDal.STAGE_MESSAGE_VERSION,
            "message_json": message, "message_sha256": OutboxDal.message_sha256(message),
            "publish_status": "pending", "publish_attempt_count": 0,
        })
        if event is None:
            raise TaskStateConflictError("first_stage_event_conflict")
        return self._response(task)

    async def get_task(self, *, task_id: str, caller: CallerContext) -> TaskResponse:
        task = await self.task_dal.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError("task_not_found")
        if task.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        return self._response(task)

    @staticmethod
    def _sha(value: dict) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
