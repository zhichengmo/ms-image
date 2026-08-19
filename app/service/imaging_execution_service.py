import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.outbox import OutboxDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.task import TaskDal
from app.schemas.outbox import ExecuteStageMessage
from app.models.imaging_base import new_opaque_id


class ImagingExecutionError(ValueError):
    pass


class StageExecutionStateConflict(ImagingExecutionError):
    pass


class ImagingExecutionService:
    def __init__(self, db: AsyncSession):
        self.outbox_dal = OutboxDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.task_dal = TaskDal(db)

    async def claim(self, *, event_id: str, message: dict[str, Any], message_version: str, trace_id: str, owner_id: str, lease_seconds: int):
        event = await self.outbox_dal.get_by_id(event_id)
        if event is None:
            raise StageExecutionStateConflict("stage_event_not_found")
        parsed = self.outbox_dal.validate_stage_event(event)
        received = ExecuteStageMessage.model_validate(message)
        if parsed.model_dump() != received.model_dump() or event.message_version != message_version or event.trace_id != trace_id:
            raise StageExecutionStateConflict("stage_event_contract_conflict")
        stage = await self.stage_dal.get_by_id(parsed.stage_checkpoint_id)
        if stage is None or stage.task_id != parsed.task_id:
            raise StageExecutionStateConflict("stage_checkpoint_not_found")
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        if stage.status == "completed" and stage.state_version >= parsed.expected_state_version + 1:
            return None
        if task.execution_status in {"cancelled", "failed", "dead_letter"} or task.cancel_requested_at is not None:
            raise StageExecutionStateConflict("task_not_executable")
        claimed = await self.stage_dal.claim(checkpoint_id=stage.id, expected_version=parsed.expected_state_version, owner_id=owner_id, now=datetime.utcnow(), lease_expires_at=datetime.utcnow() + timedelta(seconds=lease_seconds))
        return claimed

    async def complete_study_preparation(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "study_preparation" or stage.status != "running":
            raise StageExecutionStateConflict("study_preparation_stage_invalid")
        output = {"study_revision_id": stage.input_json["study_revision_id"], "manifest_sha256": stage.input_json["manifest_sha256"], "status": "prepared", "provider_called": False}
        output_sha = hashlib.sha256(json.dumps(output, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        now = datetime.utcnow()
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        if task.cancel_requested_at is not None:
            cancelled = await self.stage_dal.finish_with_lease(checkpoint_id=stage.id, expected_version=stage.state_version, owner_id=owner_id, lease_generation=stage.lease_generation, now=now, values={"status": "cancelled", "error_code": "task_cancelled", "finished_at": now})
            if cancelled is None:
                raise StageExecutionStateConflict("stage_cancel_conflict")
            updated_task = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "cancelled", "ai_medical_status": "not_produced", "finished_at": now})
            if updated_task is None:
                raise StageExecutionStateConflict("task_cancel_conflict")
            return {"status": "cancelled", "provider_called": False}
        completed = await self.stage_dal.finish_with_lease(checkpoint_id=stage.id, expected_version=stage.state_version, owner_id=owner_id, lease_generation=stage.lease_generation, now=now, values={"status": "completed", "output_json": output, "output_sha256": output_sha, "finished_at": now})
        if completed is None:
            raise StageExecutionStateConflict("stage_complete_conflict")
        updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "completed", "ai_medical_status": "not_produced", "finished_at": now})
        if updated is None:
            raise StageExecutionStateConflict("task_complete_conflict")
        return output

    async def reconcile_expired_stages(self, *, now: datetime, limit: int, max_attempts: int) -> dict[str, int]:
        rows = await self.stage_dal.list_expired_running(now=now, limit=limit)
        result = {"requeued": 0, "dead_letter": 0, "conflicted": 0}
        for row in rows:
            recovered = await self.stage_dal.recover_expired(checkpoint_id=row.id, expected_version=row.state_version, lease_generation=row.lease_generation, now=now, max_attempts=max_attempts)
            if recovered is None:
                result["conflicted"] += 1
                continue
            task = await self.task_dal.get_by_id(recovered.task_id)
            if task is None:
                await self.stage_dal.cas_update(checkpoint_id=recovered.id, expected_version=recovered.state_version, values={"status": "dead_letter", "error_code": "task_not_found", "finished_at": now})
                result["dead_letter"] += 1
                continue
            if task.cancel_requested_at is not None or task.execution_status in {"cancelled", "failed", "completed", "dead_letter"}:
                await self.stage_dal.cas_update(checkpoint_id=recovered.id, expected_version=recovered.state_version, values={"status": "cancelled", "error_code": "task_not_executable", "finished_at": now})
                result["dead_letter"] += 1
                continue
            if recovered.status == "dead_letter":
                await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "dead_letter", "ai_medical_status": "not_produced", "error_code": "stage_attempts_exhausted", "finished_at": now})
                result["dead_letter"] += 1
                continue
            message = {"task_id": recovered.task_id, "stage_checkpoint_id": recovered.id, "expected_state_version": recovered.state_version, "trace_id": task.trace_id}
            event = await self.outbox_dal.create_idempotent({"id": new_opaque_id(), "aggregate_type": "stage", "aggregate_id": recovered.id, "aggregate_version": recovered.state_version, "event_key": f"stage:{recovered.id}:execute:{recovered.state_version}", "event_type": "execute_stage", "destination_key": OutboxDal.STAGE_DESTINATION_KEY, "trace_id": message["trace_id"], "message_version": OutboxDal.STAGE_MESSAGE_VERSION, "message_json": message, "message_sha256": OutboxDal.message_sha256(message), "publish_status": "pending", "publish_attempt_count": 0})
            result["requeued" if event is not None else "conflicted"] += 1
        return result
