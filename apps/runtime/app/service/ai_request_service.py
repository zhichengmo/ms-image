import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.prompting import PromptCatalog, PromptCompiler, PromptContractError
from app.core.ai.prompting.contracts import sha256_json
from app.crud.ai_call import AICallDal
from app.crud.ai_config_record import AIConfigRecordDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.task import TaskDal
from app.models.imaging_base import new_opaque_id
from app.service.stages.xray.prompt_commands import XRayPromptCommand


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
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None or config.status != "active":
            raise AIRequestStateConflict("ai_call_config_not_active")
        if (
            config.capability_manifest_json.get("provider_disabled") is not True
            or config.provider_plan_json.get("enabled") is not False
        ):
            raise AIRequestStateConflict("provider_disabled_required")
        self._validate_task_config_snapshot(task=task, config=config)
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
        manifest_sha = (stage.input_json or {}).get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise AIRequestStateConflict("ai_call_manifest_missing")
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
            return {
                "call_id": existing.id,
                "status": existing.status,
                "error_code": existing.error_code,
                "rendered_prompt_sha256": existing.rendered_prompt_sha256,
                "schema_sha256": existing.schema_sha256,
            }
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
        return {
            "call_id": failed.id,
            "status": failed.status,
            "error_code": failed.error_code,
            "rendered_prompt_sha256": compiled_prompt.rendered_sha256,
            "schema_sha256": schema_sha256,
        }

    @staticmethod
    def _validate_task_config_snapshot(*, task: Any, config: Any) -> None:
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
    def _sha(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
