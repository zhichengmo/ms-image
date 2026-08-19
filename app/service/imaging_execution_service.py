import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.outbox import OutboxDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.task import TaskDal
from app.schemas.outbox import ExecuteStageMessage


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
        if task.execution_status in {"cancelled", "failed", "dead_letter"}:
            raise StageExecutionStateConflict("task_not_executable")
        claimed = await self.stage_dal.claim(checkpoint_id=stage.id, expected_version=parsed.expected_state_version, owner_id=owner_id, now=datetime.utcnow(), lease_expires_at=datetime.utcnow() + timedelta(seconds=lease_seconds))
        return claimed

    async def complete_study_preparation(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "study_preparation" or stage.status != "running":
            raise StageExecutionStateConflict("study_preparation_stage_invalid")
        output = {"study_revision_id": stage.input_json["study_revision_id"], "manifest_sha256": stage.input_json["manifest_sha256"], "status": "prepared", "provider_called": False}
        output_sha = hashlib.sha256(json.dumps(output, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        now = datetime.utcnow()
        completed = await self.stage_dal.cas_update(checkpoint_id=stage.id, expected_version=stage.state_version, values={"status": "completed", "lease_owner_id": None, "lease_expires_at": None, "heartbeat_at": None, "output_json": output, "output_sha256": output_sha, "finished_at": now})
        if completed is None:
            raise StageExecutionStateConflict("stage_complete_conflict")
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "completed", "ai_medical_status": "not_produced", "finished_at": now})
        if updated is None:
            raise StageExecutionStateConflict("task_complete_conflict")
        return output
