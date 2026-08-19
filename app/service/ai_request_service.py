import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai_call import AICallDal
from app.crud.ai_config_record import AIConfigRecordDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.task import TaskDal
from app.models.imaging_base import new_opaque_id


class AIRequestServiceError(ValueError):
    pass


class AIRequestStateConflict(AIRequestServiceError):
    pass


class AIRequestService:
    def __init__(self, db: AsyncSession):
        self.call_dal = AICallDal(db)
        self.config_dal = AIConfigRecordDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.task_dal = TaskDal(db)

    async def prepare_provider_disabled_call(self, *, task_id: str, stage_checkpoint_id: str, prompt_sha256: str, schema_sha256: str) -> dict[str, Any]:
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if task is None or stage is None or stage.task_id != task.id:
            raise AIRequestStateConflict("ai_call_stage_task_mismatch")
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None or config.status != "active":
            raise AIRequestStateConflict("ai_call_config_not_active")
        if config.capability_manifest_json.get("provider_disabled") is not True or config.provider_plan_json.get("enabled") is not False:
            raise AIRequestStateConflict("provider_disabled_required")
        manifest_sha = (stage.input_json or {}).get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise AIRequestStateConflict("ai_call_manifest_missing")
        request = {"task_id": task.id, "stage_id": stage.id, "config_id": config.id, "prompt_sha256": prompt_sha256, "schema_sha256": schema_sha256, "manifest_sha256": manifest_sha}
        request_sha = self._sha(request)
        logical_key = self._sha({"stage": stage.id, "input": stage.input_sha256, "config": config.compiled_pipeline_sha256, "prompt": prompt_sha256, "schema": schema_sha256})
        existing = await self.call_dal.get_by_logical_key(logical_key)
        if existing is not None:
            return {"call_id": existing.id, "status": existing.status, "error_code": existing.error_code}
        config_sha = self._sha({"id": config.id, "pipeline": config.compiled_pipeline_sha256, "provider": config.provider_plan_json, "budget": config.budget_policy_json})
        prepared = await self.call_dal.create_idempotent({
            "id": new_opaque_id(), "task_id": task.id, "stage_checkpoint_id": stage.id,
            "task_attempt_no": task.attempt_no, "stage_attempt_no": stage.retry_count + 1, "node_call_no": 1,
            "logical_call_key": logical_key, "idempotency_key": logical_key, "ai_config_id": config.id,
            "config_sha256": config_sha, "provider_type": "disabled", "requested_model": "disabled",
            "request_sha256": request_sha, "rendered_prompt_sha256": prompt_sha256, "schema_sha256": schema_sha256,
            "requested_image_manifest_sha256": manifest_sha, "image_count_requested": 0,
            "budget_reservation_json": {}, "status": "prepared", "result_disposition": "pending", "prepared_at": datetime.utcnow(),
        })
        if prepared is None:
            raise AIRequestStateConflict("ai_call_create_conflict")
        failed = await self.call_dal.cas_update(call_id=prepared.id, expected_version=prepared.state_version, values={"status": "failed", "result_disposition": "rejected", "error_code": "provider_disabled", "finished_at": datetime.utcnow()})
        if failed is None:
            raise AIRequestStateConflict("ai_call_disabled_transition_conflict")
        return {"call_id": failed.id, "status": failed.status, "error_code": failed.error_code}

    @staticmethod
    def _sha(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
