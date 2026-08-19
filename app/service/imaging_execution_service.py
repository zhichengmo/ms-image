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
from app.service.ai_request_service import AIRequestService


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
        if claimed is not None and task.execution_status == "queued":
            running = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "running", "started_at": task.started_at or datetime.utcnow()})
            if running is None:
                raise StageExecutionStateConflict("task_start_conflict")
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
        await self._schedule_next_or_complete(task=task, stage=completed, output=output, output_sha=output_sha, now=now)
        return output

    async def complete_joint_primary_reader(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "joint_primary_reader" or stage.status != "running":
            raise StageExecutionStateConflict("joint_primary_stage_invalid")
        call = await AIRequestService(self.outbox_dal.db).prepare_provider_disabled_call(
            task_id=stage.task_id,
            stage_checkpoint_id=stage.id,
            prompt_sha256=hashlib.sha256(b"joint-primary-disabled.v1").hexdigest(),
            schema_sha256=hashlib.sha256(b"primary-candidate.v1").hexdigest(),
        )
        return await self._complete_provider_disabled_stage(
            stage=stage,
            owner_id=owner_id,
            output={"candidate_kind": "primary", "medical_status": "not_produced", "source_call_id": call["call_id"], "error_code": call["error_code"], "manifest_sha256": stage.input_json["manifest_sha256"]},
        )

    async def complete_family_routing(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "family_routing" or stage.status != "running":
            raise StageExecutionStateConflict("family_routing_stage_invalid")
        return await self._complete_provider_disabled_stage(
            stage=stage,
            owner_id=owner_id,
            output={"route_signal": "primary_final", "source_primary_output_sha256": stage.input_json.get("previous_output_sha256"), "source_primary_call_id": (stage.input_json.get("previous_output") or {}).get("source_call_id")},
        )

    async def complete_targeted_review(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "targeted_review" or stage.status != "running":
            raise StageExecutionStateConflict("targeted_review_stage_invalid")
        call = await AIRequestService(self.outbox_dal.db).prepare_provider_disabled_call(
            task_id=stage.task_id,
            stage_checkpoint_id=stage.id,
            prompt_sha256=hashlib.sha256(b"targeted-review-disabled.v1").hexdigest(),
            schema_sha256=hashlib.sha256(b"targeted-candidate.v1").hexdigest(),
        )
        output = {
            "candidate_kind": "targeted",
            "medical_status": "not_produced",
            "source_call_id": call["call_id"],
            "error_code": call["error_code"],
            "source_route_sha256": stage.input_json.get("previous_output_sha256"),
        }
        if output["error_code"]:
            raise StageExecutionStateConflict("targeted_review_provider_disabled")
        return await self._complete_provider_disabled_stage(stage=stage, owner_id=owner_id, output=output)

    async def complete_decision_finalization(self, *, stage, owner_id: str) -> dict[str, Any]:
        if stage.stage_key != "decision_finalization" or stage.status != "running":
            raise StageExecutionStateConflict("decision_finalization_stage_invalid")
        return await self._complete_provider_disabled_stage(
            stage=stage,
            owner_id=owner_id,
            output={"medical_status": "not_produced", "selected_owner": "primary", "source_stage_id": stage.input_json.get("previous_stage_id"), "provider_called": False},
        )

    async def _complete_provider_disabled_stage(self, *, stage, owner_id: str, output: dict[str, Any]) -> dict[str, Any]:
        output_sha = hashlib.sha256(json.dumps(output, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        now = datetime.utcnow()
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        if task.cancel_requested_at is not None:
            cancelled = await self.stage_dal.finish_with_lease(checkpoint_id=stage.id, expected_version=stage.state_version, owner_id=owner_id, lease_generation=stage.lease_generation, now=now, values={"status": "cancelled", "error_code": "task_cancelled", "finished_at": now})
            if cancelled is None:
                raise StageExecutionStateConflict("stage_cancel_conflict")
            updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "cancelled", "ai_medical_status": "not_produced", "finished_at": now})
            if updated is None:
                raise StageExecutionStateConflict("task_cancel_conflict")
            return {"status": "cancelled", "provider_called": False}
        completed = await self.stage_dal.finish_with_lease(checkpoint_id=stage.id, expected_version=stage.state_version, owner_id=owner_id, lease_generation=stage.lease_generation, now=now, values={"status": "completed", "output_json": output, "output_sha256": output_sha, "finished_at": now})
        if completed is None:
            raise StageExecutionStateConflict("stage_complete_conflict")
        await self._schedule_next_or_complete(task=task, stage=completed, output=output, output_sha=output_sha, now=now)
        return output

    async def _schedule_next_or_complete(self, *, task, stage, output: dict[str, Any], output_sha: str, now: datetime) -> None:
        snapshot = task.request_snapshot_json or {}
        contract = snapshot.get("compiled_profile") or {}
        stages = contract.get("stages") or []
        if stage.stage_key == "family_routing" and output.get("route_signal") == "targeted_review":
            dynamic = contract.get("dynamic_stage_definitions") or []
            if len(dynamic) != 1 or dynamic[0].get("stage_key") != "targeted_review":
                raise StageExecutionStateConflict("targeted_review_contract_missing")
            definition = dynamic[0]
            next_stage_no = stage.stage_no + 1
        elif stage.stage_key == "targeted_review":
            definition = next((item for item in stages if item.get("stage_key") == "decision_finalization"), None)
            if definition is None:
                raise StageExecutionStateConflict("decision_finalization_contract_missing")
            next_stage_no = stage.stage_no + 1
        else:
            try:
                current_index = next(index for index, item in enumerate(stages) if item.get("stage_key") == stage.stage_key)
            except StopIteration as exc:
                raise StageExecutionStateConflict("compiled_profile_stage_missing") from exc
            if current_index + 1 >= len(stages):
                updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "completed", "ai_medical_status": "not_produced", "finished_at": now})
                if updated is None:
                    raise StageExecutionStateConflict("task_complete_conflict")
                return
            definition = stages[current_index + 1]
            next_stage_no = stage.stage_no + 1
        if definition is None:
            updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "completed", "ai_medical_status": "not_produced", "finished_at": now})
            if updated is None:
                raise StageExecutionStateConflict("task_complete_conflict")
            return
        next_stage_id = new_opaque_id()
        next_input = {
            "task_id": task.id,
            "study_revision_id": task.study_revision_id,
            "manifest_sha256": snapshot.get("resolved_manifest_sha256"),
            "previous_stage_id": stage.id,
            "previous_output_sha256": output_sha,
            "previous_output": output,
            "compiled_pipeline_sha256": task.compiled_pipeline_sha256,
        }
        input_sha = hashlib.sha256(json.dumps(next_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        next_stage = await self.stage_dal.create_idempotent({
            "id": next_stage_id,
            "task_id": task.id,
            "task_attempt_no": task.attempt_no,
            "stage_instance_key": f"{definition['stage_key']}:1",
            "stage_no": next_stage_no,
            "stage_key": definition["stage_key"],
            "handler_key": definition["handler_key"],
            "handler_version": definition["handler_version"],
            "status": "queued",
            "state_version": 0,
            "lease_generation": 0,
            "input_json": next_input,
            "input_sha256": input_sha,
            "retry_count": 0,
        })
        if next_stage is None:
            raise StageExecutionStateConflict("next_stage_create_conflict")
        message = {"task_id": task.id, "stage_checkpoint_id": next_stage.id, "expected_state_version": next_stage.state_version, "trace_id": task.trace_id}
        event = await self.outbox_dal.create_idempotent({
            "id": new_opaque_id(),
            "aggregate_type": "stage",
            "aggregate_id": next_stage.id,
            "aggregate_version": next_stage.state_version,
            "event_key": f"stage:{next_stage.id}:execute:{next_stage.state_version}",
            "event_type": "execute_stage",
            "destination_key": OutboxDal.STAGE_DESTINATION_KEY,
            "trace_id": task.trace_id,
            "message_version": OutboxDal.STAGE_MESSAGE_VERSION,
            "message_json": message,
            "message_sha256": OutboxDal.message_sha256(message),
            "publish_status": "pending",
            "publish_attempt_count": 0,
        })
        if event is None:
            raise StageExecutionStateConflict("next_stage_event_conflict")
        updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"execution_status": "queued", "ai_medical_status": "not_produced"})
        if updated is None:
            raise StageExecutionStateConflict("task_schedule_conflict")

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
