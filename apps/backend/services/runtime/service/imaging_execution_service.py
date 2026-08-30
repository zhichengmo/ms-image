import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.outbox import OutboxDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.crud.task import TaskDal
from apps.backend.core.pipeline import StageResult
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.outbox import ExecuteStageMessage
from apps.backend.services.runtime.medical_status_contract import (
    MedicalStatusContractError,
    project_persisted_medical_status,
)
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.service.report_service import ReportService
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.registry import resolve_stage_handler


class ImagingExecutionError(ValueError):
    pass


class StageExecutionStateConflict(ImagingExecutionError):
    pass


class ImagingExecutionService:
    def __init__(self, db: AsyncSession):
        self.outbox_dal = OutboxDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.task_dal = TaskDal(db)

    @staticmethod
    def _project_medical_status(output: Mapping[str, Any]) -> str:
        return project_persisted_medical_status(output)

    @staticmethod
    def _task_cancel_requested(task: Any) -> bool:
        return (
            task.cancel_requested_at is not None
            or task.execution_status == "cancelled"
        )

    async def _cancel_running_stage(
        self,
        *,
        task: Any,
        stage: Any,
        owner_id: str,
        provider_called: bool,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        cancelled = await self.stage_dal.finish_with_lease(
            checkpoint_id=stage.id,
            expected_version=stage.state_version,
            owner_id=owner_id,
            lease_generation=stage.lease_generation,
            now=now,
            values={
                "status": "cancelled",
                "error_code": "task_cancelled",
                "finished_at": now,
            },
        )
        if cancelled is None:
            raise StageExecutionStateConflict("stage_cancel_conflict")
        if task.execution_status != "cancelled":
            updated = await self.task_dal.cas_update(
                task_id=task.id,
                expected_version=task.state_version,
                values={
                    "execution_status": "cancelled",
                    "ai_medical_status": "not_produced",
                    "finished_at": now,
                },
            )
            if updated is None:
                raise StageExecutionStateConflict("task_cancel_conflict")
        return {"status": "cancelled", "provider_called": provider_called}

    async def claim(
        self,
        *,
        event_id: str,
        message: dict[str, Any],
        message_version: str,
        trace_id: str,
        owner_id: str,
        lease_seconds: int,
    ):
        event = await self.outbox_dal.get_by_id(event_id)
        if event is None:
            raise StageExecutionStateConflict("stage_event_not_found")
        parsed = self.outbox_dal.validate_stage_event(event)
        received = ExecuteStageMessage.model_validate(message)
        if (
            parsed.model_dump() != received.model_dump()
            or event.message_version != message_version
            or event.trace_id != trace_id
        ):
            raise StageExecutionStateConflict("stage_event_contract_conflict")
        stage = await self.stage_dal.get_by_id(parsed.stage_checkpoint_id)
        if stage is None or stage.task_id != parsed.task_id:
            raise StageExecutionStateConflict("stage_checkpoint_not_found")
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        if (
            stage.status == "completed"
            and stage.state_version >= parsed.expected_state_version + 1
        ):
            return None
        task_cancel_requested = self._task_cancel_requested(task)
        if (
            task_cancel_requested
            and stage.status == "cancelled"
            and stage.state_version >= parsed.expected_state_version + 1
        ):
            return None
        if task.execution_status in {"failed", "dead_letter"}:
            raise StageExecutionStateConflict("task_not_executable")
        if task_cancel_requested:
            if (
                stage.status != "queued"
                or stage.state_version != parsed.expected_state_version
            ):
                raise StageExecutionStateConflict("stage_cancel_conflict")
            now = datetime.utcnow()
            cancelled = await self.stage_dal.cas_update(
                checkpoint_id=stage.id,
                expected_version=parsed.expected_state_version,
                values={
                    "status": "cancelled",
                    "error_code": "task_cancelled",
                    "finished_at": now,
                },
            )
            if cancelled is None:
                raise StageExecutionStateConflict("stage_cancel_conflict")
            if task.execution_status != "cancelled":
                updated = await self.task_dal.cas_update(
                    task_id=task.id,
                    expected_version=task.state_version,
                    values={
                        "execution_status": "cancelled",
                        "ai_medical_status": "not_produced",
                        "finished_at": now,
                    },
                )
                if updated is None:
                    raise StageExecutionStateConflict("task_cancel_conflict")
            return None
        # Freeze the Task scalars required by the following transition before
        # claiming the Stage.  CAS/readback is an ORM mutation boundary and the
        # remaining logic must not depend on implicit async attribute refreshes.
        task_id = task.id
        task_state_version = task.state_version
        task_execution_status = task.execution_status
        task_started_at = task.started_at
        claimed = await self.stage_dal.claim(
            checkpoint_id=stage.id,
            expected_version=parsed.expected_state_version,
            owner_id=owner_id,
            now=datetime.utcnow(),
            lease_expires_at=datetime.utcnow() + timedelta(seconds=lease_seconds),
        )
        if claimed is not None and task_execution_status == "queued":
            running = await self.task_dal.cas_update(
                task_id=task_id,
                expected_version=task_state_version,
                values={
                    "execution_status": "running",
                    "started_at": task_started_at or datetime.utcnow(),
                },
            )
            if running is None:
                raise StageExecutionStateConflict("task_start_conflict")
        return claimed

    async def prepare_stage_execution(
        self,
        *,
        stage_checkpoint_id: str,
        owner_id: str,
        trace_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Boundary A: build a Stage plan and durably prepare its Logical Call."""
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if stage is None or stage.status != "running":
            raise StageExecutionStateConflict("stage_not_running")
        if stage.lease_owner_id != owner_id:
            raise StageExecutionStateConflict("stage_lease_owner_conflict")
        task = await self.task_dal.get_by_id(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        try:
            handler = resolve_stage_handler(
                handler_key=stage.handler_key,
                handler_version=stage.handler_version,
            )
            context = StageExecutionContext(task=task, stage=stage)
            plan = await handler.execute(context)
        except StageHandlerContractError as exc:
            raise StageExecutionStateConflict(str(exc)) from exc
        if not isinstance(plan, StageExecutionPlan):
            raise StageExecutionStateConflict("stage_execution_plan_invalid")
        if plan.completed_result is not None:
            output = await self._apply_stage_result(
                task=task,
                stage=stage,
                owner_id=owner_id,
                result=plan.completed_result,
            )
            return {"network_required": False, "output": output}
        if plan.ai_request is None:
            raise StageExecutionStateConflict("stage_execution_plan_invalid")
        call_result = await AIRequestService(self.outbox_dal.db).prepare_call(
            task_id=task.id,
            stage_checkpoint_id=stage.id,
            prompt_command=plan.ai_request.prompt_command,
            trace_id=trace_id,
            request_id=request_id,
        )
        if call_result.get("network_required"):
            return {
                "network_required": True,
                "attempt_id": call_result.get("attempt_id"),
                "call_id": call_result.get("call_id"),
            }
        if (
            call_result.get("status") == "prepared"
            and call_result.get("result_disposition") == "pending"
        ):
            return {
                "network_required": False,
                "pending_reconcile": True,
                "attempt_id": call_result.get("attempt_id"),
                "call_id": call_result.get("call_id"),
            }
        result = self._consume_ai_call(
            handler=handler,
            context=context,
            call_result=call_result,
        )
        output = await self._apply_stage_result(
            task=task,
            stage=stage,
            owner_id=owner_id,
            result=result,
        )
        return {"network_required": False, "output": output}

    async def finalize_ai_stage(
        self,
        *,
        stage_checkpoint_id: str,
        owner_id: str,
        call_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Boundary C: consume a finalized Logical Call and finish the Stage."""
        stage = await self.stage_dal.get_by_id(stage_checkpoint_id)
        if stage is None or stage.status != "running":
            raise StageExecutionStateConflict("stage_not_running")
        if stage.lease_owner_id != owner_id:
            raise StageExecutionStateConflict("stage_lease_owner_conflict")
        task = await self.task_dal.get_by_id_for_update(stage.task_id)
        if task is None:
            raise StageExecutionStateConflict("task_not_found")
        if self._task_cancel_requested(task):
            return await self._cancel_running_stage(
                task=task,
                stage=stage,
                owner_id=owner_id,
                provider_called=True,
            )
        if task.execution_status in {"completed", "failed", "dead_letter"}:
            raise StageExecutionStateConflict("task_not_executable")
        try:
            handler = resolve_stage_handler(
                handler_key=stage.handler_key,
                handler_version=stage.handler_version,
            )
            context = StageExecutionContext(task=task, stage=stage)
            result = self._consume_ai_call(
                handler=handler,
                context=context,
                call_result=call_result,
            )
        except StageHandlerContractError as exc:
            raise StageExecutionStateConflict(str(exc)) from exc
        return await self._apply_stage_result(
            task=task,
            stage=stage,
            owner_id=owner_id,
            result=result,
        )

    @staticmethod
    def _consume_ai_call(
        *, handler: Any, context: StageExecutionContext, call_result: Mapping[str, Any]
    ):
        consume = getattr(handler, "consume_ai_call", None)
        if not callable(consume):
            raise StageHandlerContractError("stage_ai_consumer_missing")
        return consume(context, call_result)

    async def _apply_stage_result(
        self, *, task: Any, stage: Any, owner_id: str, result: Any
    ) -> dict[str, Any]:
        if result.status == "completed":
            if stage.stage_key == "decision_finalization":
                try:
                    medical_status = self._project_medical_status(result.output)
                except MedicalStatusContractError as exc:
                    current_task = await self.task_dal.get_by_id_for_update(task.id)
                    if current_task is None:
                        raise StageExecutionStateConflict("task_not_found") from exc
                    if self._task_cancel_requested(current_task):
                        return await self._cancel_running_stage(
                            task=current_task,
                            stage=stage,
                            owner_id=owner_id,
                            provider_called=False,
                        )
                    if current_task.execution_status in {
                        "completed",
                        "failed",
                        "dead_letter",
                    }:
                        raise StageExecutionStateConflict(
                            "task_not_executable"
                        ) from exc
                    task = current_task
                    result = StageResult(
                        status="failed",
                        output=result.output,
                        error_code=str(exc),
                    )
                else:
                    return await self._complete_decision_finalization(
                        task=task,
                        stage=stage,
                        owner_id=owner_id,
                        output=result.output,
                        medical_status=medical_status,
                    )
            else:
                return await self._complete_stage(
                    task=task,
                    stage=stage,
                    owner_id=owner_id,
                    output=result.output,
                )
        if result.status != "failed":
            raise StageExecutionStateConflict(
                result.error_code or "stage_handler_execution_failed"
            )
        output_sha = hashlib.sha256(
            json.dumps(result.output, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        now = datetime.utcnow()
        failed = await self.stage_dal.finish_with_lease(
            checkpoint_id=stage.id,
            expected_version=stage.state_version,
            owner_id=owner_id,
            lease_generation=stage.lease_generation,
            now=now,
            values={
                "status": "failed",
                "output_json": result.output,
                "output_sha256": output_sha,
                "error_code": (result.error_code or "stage_handler_execution_failed")[
                    :80
                ],
                "finished_at": now,
            },
        )
        if failed is None:
            raise StageExecutionStateConflict("stage_fail_conflict")
        updated = await self.task_dal.cas_update(
            task_id=task.id,
            expected_version=task.state_version,
            values={
                "execution_status": "failed",
                "ai_medical_status": "not_produced",
                "error_code": failed.error_code,
                "finished_at": now,
            },
        )
        if updated is None:
            raise StageExecutionStateConflict("task_fail_conflict")
        return result.output

    async def _complete_decision_finalization(
        self,
        *,
        task,
        stage,
        owner_id: str,
        output: dict[str, Any],
        medical_status: str,
    ) -> dict[str, Any]:
        current_task = await self.task_dal.get_by_id_for_update(task.id)
        if current_task is None:
            raise StageExecutionStateConflict("task_not_found")
        if self._task_cancel_requested(current_task):
            return await self._cancel_running_stage(
                task=current_task,
                stage=stage,
                owner_id=owner_id,
                provider_called=False,
            )
        if current_task.execution_status in {"completed", "failed", "dead_letter"}:
            raise StageExecutionStateConflict("task_not_executable")
        task = current_task
        output_sha = hashlib.sha256(
            json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        now = datetime.utcnow()
        completed = await self.stage_dal.finish_with_lease(
            checkpoint_id=stage.id,
            expected_version=stage.state_version,
            owner_id=owner_id,
            lease_generation=stage.lease_generation,
            now=now,
            values={
                "status": "completed",
                "output_json": output,
                "output_sha256": output_sha,
                "finished_at": now,
            },
        )
        if completed is None:
            raise StageExecutionStateConflict("stage_complete_conflict")
        source_call_id = (stage.input_json.get("previous_output") or {}).get(
            "source_call_id"
        )
        # Keep the Stage-internal ``produced/not_produced`` marker out of the
        # persisted Report/Task content: the persisted facts carry the model's
        # own medical verdict instead.
        persisted = dict(output)
        persisted["medical_status"] = medical_status
        report = await ReportService(self.outbox_dal.db).finalize(
            task_id=task.id,
            finalization_stage_id=completed.id,
            source_call_id=source_call_id,
            medical_status=medical_status,
            content=persisted,
        )
        if report is None:
            updated = await self.task_dal.cas_update(
                task_id=task.id,
                expected_version=task.state_version,
                values={
                    "execution_status": "completed",
                    "ai_medical_status": medical_status,
                    "finished_at": now,
                },
            )
            if updated is None:
                raise StageExecutionStateConflict("task_complete_conflict")
        return output

    async def _complete_stage(
        self, *, task, stage, owner_id: str, output: dict[str, Any]
    ) -> dict[str, Any]:
        output_sha = hashlib.sha256(
            json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        now = datetime.utcnow()
        if self._task_cancel_requested(task):
            return await self._cancel_running_stage(
                task=task,
                stage=stage,
                owner_id=owner_id,
                provider_called=False,
            )
        completed = await self.stage_dal.finish_with_lease(
            checkpoint_id=stage.id,
            expected_version=stage.state_version,
            owner_id=owner_id,
            lease_generation=stage.lease_generation,
            now=now,
            values={
                "status": "completed",
                "output_json": output,
                "output_sha256": output_sha,
                "finished_at": now,
            },
        )
        if completed is None:
            raise StageExecutionStateConflict("stage_complete_conflict")
        await self._schedule_next_or_complete(
            task=task, stage=completed, output=output, output_sha=output_sha, now=now
        )
        return output

    async def _schedule_next_or_complete(
        self, *, task, stage, output: dict[str, Any], output_sha: str, now: datetime
    ) -> None:
        snapshot = task.request_snapshot_json or {}
        contract = snapshot.get("compiled_profile") or {}
        stages = contract.get("stages") or []
        if (
            stage.stage_key == "family_routing"
            and output.get("route_signal") == "targeted_review"
        ):
            dynamic = contract.get("dynamic_stage_definitions") or []
            if len(dynamic) != 1 or dynamic[0].get("stage_key") != "targeted_review":
                raise StageExecutionStateConflict("targeted_review_contract_missing")
            definition = dynamic[0]
            next_stage_no = stage.stage_no + 1
        elif stage.stage_key == "targeted_review":
            definition = next(
                (
                    item
                    for item in stages
                    if item.get("stage_key") == "decision_finalization"
                ),
                None,
            )
            if definition is None:
                raise StageExecutionStateConflict(
                    "decision_finalization_contract_missing"
                )
            next_stage_no = stage.stage_no + 1
        else:
            try:
                current_index = next(
                    index
                    for index, item in enumerate(stages)
                    if item.get("stage_key") == stage.stage_key
                )
            except StopIteration as exc:
                raise StageExecutionStateConflict(
                    "compiled_profile_stage_missing"
                ) from exc
            if current_index + 1 >= len(stages):
                updated = await self.task_dal.cas_update(
                    task_id=task.id,
                    expected_version=task.state_version,
                    values={
                        "execution_status": "completed",
                        "ai_medical_status": "not_produced",
                        "finished_at": now,
                    },
                )
                if updated is None:
                    raise StageExecutionStateConflict("task_complete_conflict")
                return
            definition = stages[current_index + 1]
            next_stage_no = stage.stage_no + 1
        if definition is None:
            updated = await self.task_dal.cas_update(
                task_id=task.id,
                expected_version=task.state_version,
                values={
                    "execution_status": "completed",
                    "ai_medical_status": "not_produced",
                    "finished_at": now,
                },
            )
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
        if (
            stage.stage_key == "family_routing"
            and output.get("route_signal") == "targeted_review"
        ):
            route_fields = {
                key: output.get(key)
                for key in (
                    "selected_family_key",
                    "selected_focus_key",
                    "selected_strategy_key",
                    "source_finding_ids",
                    "coverage_proof",
                    "route_reason_codes",
                )
            }
            if (
                not isinstance(route_fields["selected_family_key"], str)
                or not isinstance(route_fields["selected_focus_key"], str)
                or not isinstance(route_fields["source_finding_ids"], list)
                or not isinstance(route_fields["coverage_proof"], dict)
                or not isinstance(route_fields["route_reason_codes"], list)
            ):
                raise StageExecutionStateConflict(
                    "targeted_review_route_evidence_missing"
                )
            next_input.update(route_fields)
        input_sha = hashlib.sha256(
            json.dumps(next_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        next_stage = await self.stage_dal.create_idempotent(
            {
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
            }
        )
        if next_stage is None:
            raise StageExecutionStateConflict("next_stage_create_conflict")
        message = {
            "task_id": task.id,
            "stage_checkpoint_id": next_stage.id,
            "expected_state_version": next_stage.state_version,
            "trace_id": task.trace_id,
        }
        event = await self.outbox_dal.create_idempotent(
            {
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
            }
        )
        if event is None:
            raise StageExecutionStateConflict("next_stage_event_conflict")
        updated = await self.task_dal.cas_update(
            task_id=task.id,
            expected_version=task.state_version,
            values={"execution_status": "queued", "ai_medical_status": "not_produced"},
        )
        if updated is None:
            raise StageExecutionStateConflict("task_schedule_conflict")

    async def reconcile_expired_stages(
        self, *, now: datetime, limit: int, max_attempts: int
    ) -> dict[str, int]:
        rows = await self.stage_dal.list_expired_running(now=now, limit=limit)
        result = {"requeued": 0, "dead_letter": 0, "conflicted": 0}
        for row in rows:
            recovered = await self.stage_dal.recover_expired(
                checkpoint_id=row.id,
                expected_version=row.state_version,
                lease_generation=row.lease_generation,
                now=now,
                max_attempts=max_attempts,
            )
            if recovered is None:
                result["conflicted"] += 1
                continue
            task = await self.task_dal.get_by_id(recovered.task_id)
            if task is None:
                await self.stage_dal.cas_update(
                    checkpoint_id=recovered.id,
                    expected_version=recovered.state_version,
                    values={
                        "status": "dead_letter",
                        "error_code": "task_not_found",
                        "finished_at": now,
                    },
                )
                result["dead_letter"] += 1
                continue
            if task.cancel_requested_at is not None or task.execution_status in {
                "cancelled",
                "failed",
                "completed",
                "dead_letter",
            }:
                await self.stage_dal.cas_update(
                    checkpoint_id=recovered.id,
                    expected_version=recovered.state_version,
                    values={
                        "status": "cancelled",
                        "error_code": "task_not_executable",
                        "finished_at": now,
                    },
                )
                result["dead_letter"] += 1
                continue
            if recovered.status == "dead_letter":
                await self.task_dal.cas_update(
                    task_id=task.id,
                    expected_version=task.state_version,
                    values={
                        "execution_status": "dead_letter",
                        "ai_medical_status": "not_produced",
                        "error_code": "stage_attempts_exhausted",
                        "finished_at": now,
                    },
                )
                result["dead_letter"] += 1
                continue
            message = {
                "task_id": recovered.task_id,
                "stage_checkpoint_id": recovered.id,
                "expected_state_version": recovered.state_version,
                "trace_id": task.trace_id,
            }
            event = await self.outbox_dal.create_idempotent(
                {
                    "id": new_opaque_id(),
                    "aggregate_type": "stage",
                    "aggregate_id": recovered.id,
                    "aggregate_version": recovered.state_version,
                    "event_key": f"stage:{recovered.id}:execute:{recovered.state_version}",
                    "event_type": "execute_stage",
                    "destination_key": OutboxDal.STAGE_DESTINATION_KEY,
                    "trace_id": message["trace_id"],
                    "message_version": OutboxDal.STAGE_MESSAGE_VERSION,
                    "message_json": message,
                    "message_sha256": OutboxDal.message_sha256(message),
                    "publish_status": "pending",
                    "publish_attempt_count": 0,
                }
            )
            result["requeued" if event is not None else "conflicted"] += 1
        return result
