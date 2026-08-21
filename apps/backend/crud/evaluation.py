import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.evaluation import (
    EvaluationArtifact,
    EvaluationJob,
    EvaluationOutbox,
    EvaluationRun,
)
from apps.backend.schemas.evaluation import ExecuteEvaluationMessage


class EvaluationJobDal(DalBase):
    TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "dead_letter"})

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationJob)

    async def create_idempotent(self, values: dict[str, Any]) -> EvaluationJob | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if (
                "uq_evaluation_job_business_key" not in detail
                and "business_key" not in detail
            ):
                raise
            return None

    async def get_by_id(self, job_id: str) -> EvaluationJob | None:
        return await self.get_data(data_id=job_id, v_return_none=True)

    async def get_by_business_key(self, key: str) -> EvaluationJob | None:
        return await self.get_data(business_key=key, v_return_none=True)

    async def claim_execution(
        self,
        *,
        job_id: str,
        expected_version: int,
        owner_id: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
        max_attempts: int,
    ) -> EvaluationJob | None:
        normalized_owner_id = owner_id.strip()
        if (
            not normalized_owner_id
            or expected_version < 0
            or max_attempts < 1
            or lease_expires_at <= claimed_at
        ):
            raise ValueError("evaluation_job_claim_contract_invalid")
        row = await self.get_by_id(job_id)
        if row is None or row.state_version != expected_version:
            return None
        changed = await self.conditional_update(
            v_where=[
                self.model.id == job_id,
                self.model.state_version == expected_version,
                self.model.status.in_(("queued", "retry_wait")),
                self.model.retry_count < max_attempts,
                or_(
                    self.model.next_retry_at.is_(None),
                    self.model.next_retry_at <= claimed_at,
                ),
                or_(
                    self.model.lease_owner_id.is_(None),
                    self.model.lease_expires_at <= claimed_at,
                ),
            ],
            data={
                "status": "running",
                "state_version": expected_version + 1,
                "lease_owner_id": normalized_owner_id,
                "lease_generation": row.lease_generation + 1,
                "lease_expires_at": lease_expires_at,
                "heartbeat_at": claimed_at,
                "retry_count": row.retry_count + 1,
                "next_retry_at": None,
                "started_at": row.started_at or claimed_at,
                "finished_at": None,
                "error_code": None,
                "error_message": None,
            },
        )
        return await self.get_by_id(job_id) if changed else None

    async def heartbeat_execution(
        self,
        *,
        job_id: str,
        owner_id: str,
        lease_generation: int,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        normalized_owner_id = owner_id.strip()
        if (
            not normalized_owner_id
            or lease_generation < 1
            or lease_expires_at <= heartbeat_at
        ):
            raise ValueError("evaluation_job_heartbeat_contract_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == job_id,
                self.model.status == "running",
                self.model.lease_owner_id == normalized_owner_id,
                self.model.lease_generation == lease_generation,
                self.model.lease_expires_at > heartbeat_at,
            ],
            data={
                "heartbeat_at": heartbeat_at,
                "lease_expires_at": lease_expires_at,
            },
        )

    async def cancel(
        self,
        *,
        job_id: str,
        expected_version: int,
        cancelled_at: datetime,
        error_code: str,
    ) -> EvaluationJob | None:
        normalized_error_code = error_code.strip()
        if not normalized_error_code or len(normalized_error_code) > 80:
            raise ValueError("evaluation_job_cancel_error_invalid")
        changed = await self.conditional_update(
            v_where=[
                self.model.id == job_id,
                self.model.state_version == expected_version,
                self.model.status.notin_(tuple(self.TERMINAL_STATUSES)),
            ],
            data={
                "status": "cancelled",
                "state_version": expected_version + 1,
                "lease_owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
                "next_retry_at": None,
                "finished_at": cancelled_at,
                "error_code": normalized_error_code,
                "error_message": None,
            },
        )
        return await self.get_by_id(job_id) if changed else None

    async def release_retry(
        self,
        *,
        job_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        released_at: datetime,
        next_retry_at: datetime,
        error_code: str,
        error_message: str,
    ) -> EvaluationJob | None:
        if next_retry_at <= released_at:
            raise ValueError("evaluation_job_retry_time_invalid")
        return await self._finish_execution(
            job_id=job_id,
            expected_version=expected_version,
            owner_id=owner_id,
            lease_generation=lease_generation,
            finished_at=released_at,
            status="retry_wait",
            next_retry_at=next_retry_at,
            result_artifact_id=None,
            error_code=error_code,
            error_message=error_message,
        )

    async def finish_execution(
        self,
        *,
        job_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        finished_at: datetime,
        status: str,
        result_artifact_id: str | None,
        error_code: str | None,
        error_message: str | None,
    ) -> EvaluationJob | None:
        if status not in {"completed", "failed", "dead_letter", "cancelled"}:
            raise ValueError("evaluation_job_terminal_status_invalid")
        if status == "completed" and not result_artifact_id:
            raise ValueError("evaluation_job_result_artifact_required")
        return await self._finish_execution(
            job_id=job_id,
            expected_version=expected_version,
            owner_id=owner_id,
            lease_generation=lease_generation,
            finished_at=finished_at,
            status=status,
            next_retry_at=None,
            result_artifact_id=result_artifact_id,
            error_code=error_code,
            error_message=error_message,
        )

    async def operational_snapshot(self, *, now: datetime) -> dict[str, Any]:
        counts = {
            status: await self.get_count(status=status)
            for status in (
                "queued",
                "running",
                "retry_wait",
                "completed",
                "failed",
                "cancelled",
                "dead_letter",
            )
        }
        expired_running_leases = await self.get_count(
            v_where=[
                self.model.status == "running",
                self.model.lease_expires_at.is_not(None),
                self.model.lease_expires_at <= now,
            ]
        )
        oldest = await self.get_datas(
            page=1,
            limit=1,
            v_where=[self.model.status.in_(("queued", "running", "retry_wait"))],
            v_order_field="created_at",
            v_return_objs=True,
        )
        artifact_drift_failures = await self.get_count(
            error_code="evaluation_artifact_hash_drift"
        )
        return {
            "counts": counts,
            "expired_running_leases": expired_running_leases,
            "artifact_drift_failures": artifact_drift_failures,
            "oldest_active_created_at": oldest[0].created_at if oldest else None,
        }

    async def reconcile_expired_execution_leases(
        self, *, now: datetime, max_attempts: int, limit: int = 100
    ) -> dict[str, Any]:
        if max_attempts < 1 or limit < 1:
            raise ValueError("evaluation_job_reconcile_contract_invalid")
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "running",
                self.model.lease_expires_at <= now,
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )
        result: dict[str, Any] = {
            "retry_wait": 0,
            "dead_lettered": 0,
            "dead_letter_job_ids": [],
        }
        for row in rows:
            exhausted = row.retry_count >= max_attempts
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.status == "running",
                    self.model.state_version == row.state_version,
                    self.model.lease_owner_id == row.lease_owner_id,
                    self.model.lease_generation == row.lease_generation,
                    self.model.lease_expires_at == row.lease_expires_at,
                ],
                data={
                    "status": "dead_letter" if exhausted else "retry_wait",
                    "state_version": row.state_version + 1,
                    "lease_owner_id": None,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                    "next_retry_at": None if exhausted else now,
                    "finished_at": now if exhausted else None,
                    "error_code": "evaluation_worker_lease_expired",
                    "error_message": "evaluation worker lease expired before writeback",
                },
            )
            key = "dead_lettered" if exhausted else "retry_wait"
            result[key] += int(changed)
            if exhausted and changed:
                result["dead_letter_job_ids"].append(row.id)
        return result

    async def cas_update(
        self, *, job_id: str, expected_version: int, values: dict[str, Any]
    ) -> EvaluationJob | None:
        allowed = {
            "status",
            "result_artifact_id",
            "next_retry_at",
            "finished_at",
            "error_code",
            "error_message",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("evaluation_job_update_fields_invalid")
        return await self.cas_put_data(
            data_id=job_id, expected_version=expected_version, data=values
        )

    async def _finish_execution(
        self,
        *,
        job_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        finished_at: datetime,
        status: str,
        next_retry_at: datetime | None,
        result_artifact_id: str | None,
        error_code: str | None,
        error_message: str | None,
    ) -> EvaluationJob | None:
        normalized_owner_id = owner_id.strip()
        if not normalized_owner_id or lease_generation < 1:
            raise ValueError("evaluation_job_finish_identity_invalid")
        safe_error_code = error_code.strip() if error_code else None
        if safe_error_code and len(safe_error_code) > 80:
            raise ValueError("evaluation_job_error_code_invalid")
        changed = await self.conditional_update(
            v_where=[
                self.model.id == job_id,
                self.model.status == "running",
                self.model.state_version == expected_version,
                self.model.lease_owner_id == normalized_owner_id,
                self.model.lease_generation == lease_generation,
                self.model.lease_expires_at > finished_at,
            ],
            data={
                "status": status,
                "state_version": expected_version + 1,
                "lease_owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
                "next_retry_at": next_retry_at,
                "result_artifact_id": result_artifact_id,
                "finished_at": finished_at if status != "retry_wait" else None,
                "error_code": safe_error_code,
                "error_message": (error_message or "").strip()[:500] or None,
            },
        )
        return await self.get_by_id(job_id) if changed else None


class EvaluationOutboxDal(DalBase):
    EVENT_TYPE = "execute_evaluation"
    DESTINATION_KEY = "evaluation.job.execute"
    MESSAGE_VERSION = "evaluation-execution.v1"

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationOutbox)

    @staticmethod
    def event_key(job_id: str, expected_state_version: int) -> str:
        normalized_job_id = job_id.strip()
        if not normalized_job_id or expected_state_version < 0:
            raise ValueError("evaluation_outbox_event_identity_invalid")
        return f"evaluation:{normalized_job_id}:execute:{expected_state_version}"

    @staticmethod
    def message_sha256(message: dict[str, Any]) -> str:
        canonical = json.dumps(
            message, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def create_idempotent(
        self, values: dict[str, Any]
    ) -> EvaluationOutbox | None:
        self._validate_event(values)
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if (
                "uq_evaluation_outbox_event_key" not in detail
                and "event_key" not in detail
            ):
                raise
            return None

    def validate_publish_event(self, event: EvaluationOutbox) -> dict[str, Any]:
        values = {
            "job_id": event.job_id,
            "aggregate_version": event.aggregate_version,
            "event_key": event.event_key,
            "event_type": event.event_type,
            "destination_key": event.destination_key,
            "trace_id": event.trace_id,
            "message_version": event.message_version,
            "message_json": event.message_json,
            "message_sha256": event.message_sha256,
        }
        return self._validate_event(values).model_dump()

    async def get_by_id(self, event_id: str) -> EvaluationOutbox | None:
        return await self.get_data(data_id=event_id, v_return_none=True)

    async def get_by_event_key(self, event_key: str) -> EvaluationOutbox | None:
        return await self.get_data(event_key=event_key, v_return_none=True)

    async def list_publishable_global(
        self, *, now: datetime, limit: int = 100
    ) -> list[EvaluationOutbox]:
        if limit <= 0:
            raise ValueError("evaluation_outbox_publish_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                or_(
                    and_(
                        self.model.publish_status == "pending",
                        self.model.next_retry_at.is_(None),
                    ),
                    and_(
                        self.model.publish_status == "retry_wait",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def claim_publish(
        self,
        *,
        event_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> EvaluationOutbox | None:
        normalized_owner_id = owner_id.strip()
        if not normalized_owner_id or lease_expires_at <= now:
            raise ValueError("evaluation_outbox_publish_lease_invalid")
        row = await self.get_by_id(event_id)
        if row is None:
            return None
        changed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                or_(
                    and_(
                        self.model.publish_status == "pending",
                        self.model.next_retry_at.is_(None),
                    ),
                    and_(
                        self.model.publish_status == "retry_wait",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                self.model.publish_attempt_count == row.publish_attempt_count,
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            data={
                "publish_status": "publishing",
                "relay_owner_id": normalized_owner_id,
                "relay_lease_expires_at": lease_expires_at,
                "publish_attempt_count": row.publish_attempt_count + 1,
                "next_retry_at": None,
                "error_code": None,
                "error_message": None,
            },
        )
        return await self.get_by_id(event_id) if changed else None

    async def mark_published(
        self,
        *,
        event_id: str,
        owner_id: str,
        broker_message_id: str,
        published_at: datetime,
    ) -> bool:
        normalized_owner_id = owner_id.strip()
        normalized_message_id = broker_message_id.strip()
        if not normalized_owner_id or not normalized_message_id:
            raise ValueError("evaluation_outbox_publish_confirmation_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == normalized_owner_id,
                self.model.relay_lease_expires_at > published_at,
            ],
            data={
                "publish_status": "published",
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "broker_message_id": normalized_message_id[:128],
                "published_at": published_at,
            },
        )

    async def mark_retry(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        next_retry_at: datetime,
        error_code: str,
        error_message: str,
    ) -> bool:
        return await self._mark_failure(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            publish_status="retry_wait",
            next_retry_at=next_retry_at,
            error_code=error_code,
            error_message=error_message,
        )

    async def mark_dead_letter(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        error_code: str,
        error_message: str,
    ) -> bool:
        return await self._mark_failure(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            publish_status="dead_letter",
            next_retry_at=None,
            error_code=error_code,
            error_message=error_message,
        )

    async def reconcile_expired_publish_leases(
        self, *, now: datetime, max_attempts: int, limit: int = 100
    ) -> dict[str, int]:
        if max_attempts <= 0 or limit <= 0:
            raise ValueError("evaluation_outbox_reconcile_contract_invalid")
        changed = {"retry_wait": 0, "dead_lettered": 0}
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.publish_status == "publishing",
                self.model.relay_lease_expires_at <= now,
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )
        for row in rows:
            exhausted = row.publish_attempt_count >= max_attempts
            recovered = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.publish_status == "publishing",
                    self.model.relay_owner_id == row.relay_owner_id,
                    self.model.relay_lease_expires_at == row.relay_lease_expires_at,
                ],
                data={
                    "publish_status": ("dead_letter" if exhausted else "retry_wait"),
                    "relay_owner_id": None,
                    "relay_lease_expires_at": None,
                    "next_retry_at": None if exhausted else now,
                    "error_code": "evaluation_relay_lease_expired",
                    "error_message": "evaluation relay lease expired before confirmation",
                },
            )
            key = "dead_lettered" if exhausted else "retry_wait"
            changed[key] += int(recovered)
        return changed

    async def operational_snapshot(self, *, now: datetime) -> dict[str, Any]:
        counts = {
            status: await self.get_count(publish_status=status)
            for status in (
                "pending",
                "publishing",
                "published",
                "retry_wait",
                "dead_letter",
                "cancelled",
            )
        }
        expired_relay_leases = await self.get_count(
            v_where=[
                self.model.publish_status == "publishing",
                self.model.relay_lease_expires_at.is_not(None),
                self.model.relay_lease_expires_at <= now,
            ]
        )
        oldest = await self.get_datas(
            page=1,
            limit=1,
            v_where=[
                self.model.publish_status.in_(("pending", "publishing", "retry_wait"))
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )
        return {
            "counts": counts,
            "expired_relay_leases": expired_relay_leases,
            "oldest_active_created_at": oldest[0].created_at if oldest else None,
        }

    async def _mark_failure(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        publish_status: str,
        next_retry_at: datetime | None,
        error_code: str,
        error_message: str,
    ) -> bool:
        normalized_owner_id = owner_id.strip()
        normalized_error_code = error_code.strip()
        if not normalized_owner_id:
            raise ValueError("evaluation_outbox_publish_owner_invalid")
        if not normalized_error_code or len(normalized_error_code) > 80:
            raise ValueError("evaluation_outbox_error_code_invalid")
        if publish_status == "retry_wait":
            if next_retry_at is None or next_retry_at <= failed_at:
                raise ValueError("evaluation_outbox_retry_time_invalid")
        elif publish_status == "dead_letter":
            if next_retry_at is not None:
                raise ValueError("evaluation_outbox_dead_letter_retry_invalid")
        else:
            raise ValueError("evaluation_outbox_failure_status_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == normalized_owner_id,
                self.model.relay_lease_expires_at > failed_at,
            ],
            data={
                "publish_status": publish_status,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "next_retry_at": next_retry_at,
                "error_code": normalized_error_code,
                "error_message": error_message.strip()[:500],
            },
        )

    def _validate_event(self, values: dict[str, Any]) -> ExecuteEvaluationMessage:
        if values.get("event_type") != self.EVENT_TYPE:
            raise ValueError("evaluation_outbox_event_type_invalid")
        if values.get("destination_key") != self.DESTINATION_KEY:
            raise ValueError("evaluation_outbox_destination_invalid")
        if values.get("message_version") != self.MESSAGE_VERSION:
            raise ValueError("evaluation_outbox_message_version_invalid")
        message = ExecuteEvaluationMessage.model_validate(values.get("message_json"))
        if message.job_id != values.get("job_id"):
            raise ValueError("evaluation_outbox_job_identity_mismatch")
        if message.expected_state_version != values.get("aggregate_version"):
            raise ValueError("evaluation_outbox_job_version_mismatch")
        expected_event_key = self.event_key(
            message.job_id, message.expected_state_version
        )
        if values.get("event_key") != expected_event_key:
            raise ValueError("evaluation_outbox_event_key_mismatch")
        if message.trace_id != values.get("trace_id"):
            raise ValueError("evaluation_outbox_trace_mismatch")
        if self.message_sha256(message.model_dump()) != values.get("message_sha256"):
            raise ValueError("evaluation_outbox_message_sha256_mismatch")
        return message


class EvaluationRunDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationRun)

    async def create_idempotent(self, values: dict[str, Any]) -> EvaluationRun | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_evaluation_run_job_no" not in detail and "job_id" not in detail:
                raise
            return None

    async def get_by_id(self, run_id: str) -> EvaluationRun | None:
        return await self.get_data(data_id=run_id, v_return_none=True)

    async def get_by_job_run_no(
        self, *, job_id: str, run_no: int
    ) -> EvaluationRun | None:
        return await self.get_data(job_id=job_id, run_no=run_no, v_return_none=True)

    async def list_for_job(self, job_id: str) -> list[EvaluationRun]:
        return await self.get_datas(
            limit=0, job_id=job_id, v_order_field="run_no", v_return_objs=True
        )

    async def list_recent(self, *, limit: int = 500) -> list[EvaluationRun]:
        if limit < 1 or limit > 5000:
            raise ValueError("evaluation_run_operational_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_order="desc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def cas_update(
        self, *, run_id: str, expected_version: int, values: dict[str, Any]
    ) -> EvaluationRun | None:
        allowed = {
            "status",
            "summary_json",
            "error_code",
            "error_message",
            "finished_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("evaluation_run_update_fields_invalid")
        return await self.cas_put_data(
            data_id=run_id, expected_version=expected_version, data=values
        )


class EvaluationArtifactDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationArtifact)

    async def create_append_only(self, values: dict[str, Any]):
        return await self.create_data(values, v_return_obj=True)

    async def create_output_idempotent(
        self, values: dict[str, Any]
    ) -> EvaluationArtifact | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if (
                "uq_evaluation_artifact_run_kind" not in detail
                and "artifact_kind" not in detail
            ):
                raise
            return None

    async def get_by_id(self, artifact_id: str) -> EvaluationArtifact | None:
        return await self.get_data(data_id=artifact_id, v_return_none=True)

    async def get_for_run_kind(
        self, *, job_id: str, run_id: str, artifact_kind: str
    ) -> EvaluationArtifact | None:
        return await self.get_data(
            job_id=job_id,
            run_id=run_id,
            artifact_kind=artifact_kind,
            v_return_none=True,
        )

    async def list_for_job(self, job_id: str) -> list[EvaluationArtifact]:
        return await self.get_datas(
            limit=0,
            job_id=job_id,
            v_order_field="created_at",
            v_return_objs=True,
        )


__all__ = [
    "EvaluationArtifactDal",
    "EvaluationJobDal",
    "EvaluationOutboxDal",
    "EvaluationRunDal",
]
