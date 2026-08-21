"""Reliable Evaluation Job execution state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.evaluation import (
    EvaluationArtifactDal,
    EvaluationJobDal,
    EvaluationOutboxDal,
    EvaluationRunDal,
)
from app.models.imaging_base import new_opaque_id
from app.schemas.evaluation import ExecuteEvaluationMessage
from app.service.evaluation_fake_scorer import FakeEvaluationScorer


class EvaluationExecutionError(ValueError):
    pass


class EvaluationExecutionNotFound(EvaluationExecutionError):
    pass


class EvaluationExecutionConflict(EvaluationExecutionError):
    pass


@dataclass(frozen=True)
class EvaluationExecutionClaim:
    event_id: str
    job_id: str
    job_state_version: int
    lease_generation: int
    attempt_count: int
    run_id: str
    run_state_version: int
    requester_id: str
    dataset_fingerprint: str
    gold_fingerprint: str
    scorer_fingerprint: str
    experiment_fingerprint: str
    case_split: dict[str, Any]
    denominator_contract: dict[str, Any]
    input_manifest_artifact_id: str
    input_manifest_object_ref: dict[str, Any]
    input_manifest_sha256: str
    input_manifest_provenance: dict[str, Any]
    sanitization_artifact_id: str
    sanitization_object_ref: dict[str, Any]
    sanitization_sha256: str
    sanitization_provenance: dict[str, Any]
    trace_id: str


@dataclass(frozen=True)
class StoredEvaluationArtifact:
    artifact_kind: str
    object_ref: dict[str, Any]
    content_sha256: str
    provenance: dict[str, Any]


class EvaluationExecutionService:
    def __init__(self, db: AsyncSession):
        self.job_dal = EvaluationJobDal(db)
        self.outbox_dal = EvaluationOutboxDal(db)
        self.run_dal = EvaluationRunDal(db)
        self.artifact_dal = EvaluationArtifactDal(db)

    async def claim(
        self,
        *,
        event_id: str,
        message: dict[str, Any],
        message_version: str,
        header_trace_id: str,
        owner_id: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
        max_attempts: int,
    ) -> EvaluationExecutionClaim | None:
        event = await self.outbox_dal.get_by_id(event_id)
        if event is None:
            raise EvaluationExecutionNotFound("evaluation_outbox_not_found")
        try:
            validated = self.outbox_dal.validate_publish_event(event)
            provided = ExecuteEvaluationMessage.model_validate(message).model_dump()
        except ValueError as exc:
            raise EvaluationExecutionConflict(
                "evaluation_message_contract_invalid"
            ) from exc
        if validated != provided:
            raise EvaluationExecutionConflict("evaluation_message_payload_mismatch")
        if message_version != event.message_version:
            raise EvaluationExecutionConflict("evaluation_message_version_mismatch")
        if header_trace_id != event.trace_id:
            raise EvaluationExecutionConflict("evaluation_trace_header_mismatch")
        if event.publish_status not in {"publishing", "published"}:
            raise EvaluationExecutionConflict("evaluation_outbox_not_deliverable")

        job = await self.job_dal.get_by_id(provided["job_id"])
        if job is None:
            raise EvaluationExecutionNotFound("evaluation_job_not_found")
        if job.status in self.job_dal.TERMINAL_STATUSES:
            return None
        if job.status == "running":
            return None
        if (
            job.status == "queued"
            and job.state_version != provided["expected_state_version"]
        ):
            raise EvaluationExecutionConflict("evaluation_job_initial_version_mismatch")
        if job.status not in {"queued", "retry_wait"}:
            raise EvaluationExecutionConflict("evaluation_job_not_claimable")

        claimed = await self.job_dal.claim_execution(
            job_id=job.id,
            expected_version=job.state_version,
            owner_id=owner_id,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            max_attempts=max_attempts,
        )
        if claimed is None:
            return None

        input_artifact = await self._load_job_artifact(
            artifact_id=claimed.input_manifest_artifact_id,
            job_id=claimed.id,
            expected_kind="input_manifest",
        )
        sanitization_artifact = await self._load_job_artifact(
            artifact_id=claimed.sanitization_artifact_id,
            job_id=claimed.id,
            expected_kind="sanitization",
        )
        case_split_sha256 = FakeEvaluationScorer.sha256_json(claimed.case_split_json)
        denominator_sha256 = FakeEvaluationScorer.sha256_json(
            claimed.denominator_contract_json
        )
        run_values = {
            "id": new_opaque_id(),
            "job_id": claimed.id,
            "run_no": 1,
            "dataset_fingerprint": claimed.dataset_fingerprint,
            "gold_fingerprint": claimed.gold_fingerprint,
            "scorer_fingerprint": claimed.scorer_fingerprint,
            "experiment_fingerprint": claimed.experiment_fingerprint,
            "case_split_sha256": case_split_sha256,
            "denominator_contract_sha256": denominator_sha256,
            "input_manifest_artifact_sha256": input_artifact.content_sha256,
            "sanitization_artifact_sha256": sanitization_artifact.content_sha256,
            "status": "started",
            "state_version": 0,
            "summary_json": None,
            "error_code": None,
            "error_message": None,
            "started_at": claimed_at,
            "finished_at": None,
        }
        run = await self.run_dal.create_idempotent(run_values)
        if run is None:
            run = await self.run_dal.get_by_job_run_no(job_id=claimed.id, run_no=1)
            if run is None:
                raise EvaluationExecutionConflict("evaluation_run_create_conflict")
            self._validate_frozen_run(run, run_values)
            if run.status != "started":
                raise EvaluationExecutionConflict("evaluation_run_not_reusable")

        return EvaluationExecutionClaim(
            event_id=event.id,
            job_id=claimed.id,
            job_state_version=claimed.state_version,
            lease_generation=claimed.lease_generation,
            attempt_count=claimed.retry_count,
            run_id=run.id,
            run_state_version=run.state_version,
            requester_id=claimed.requester_id,
            dataset_fingerprint=claimed.dataset_fingerprint,
            gold_fingerprint=claimed.gold_fingerprint,
            scorer_fingerprint=claimed.scorer_fingerprint,
            experiment_fingerprint=claimed.experiment_fingerprint,
            case_split=dict(claimed.case_split_json),
            denominator_contract=dict(claimed.denominator_contract_json),
            input_manifest_artifact_id=input_artifact.id,
            input_manifest_object_ref=dict(input_artifact.object_ref_json),
            input_manifest_sha256=input_artifact.content_sha256,
            input_manifest_provenance=dict(input_artifact.provenance_json),
            sanitization_artifact_id=sanitization_artifact.id,
            sanitization_object_ref=dict(sanitization_artifact.object_ref_json),
            sanitization_sha256=sanitization_artifact.content_sha256,
            sanitization_provenance=dict(sanitization_artifact.provenance_json),
            trace_id=event.trace_id,
        )

    async def heartbeat(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        return await self.job_dal.heartbeat_execution(
            job_id=claim.job_id,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )

    async def complete(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        artifacts: list[StoredEvaluationArtifact],
        summary: dict[str, Any],
        finished_at: datetime,
    ) -> dict[str, Any]:
        required_kinds = {"case_result", "failure_summary", "metric_summary"}
        actual_kinds = {item.artifact_kind for item in artifacts}
        if (
            not required_kinds.issubset(actual_kinds)
            or not actual_kinds.issubset(required_kinds | {"paired_ab_summary"})
            or len(actual_kinds) != len(artifacts)
        ):
            raise EvaluationExecutionConflict("evaluation_output_artifacts_incomplete")
        artifact_ids: dict[str, str] = {}
        for item in artifacts:
            values = {
                "id": new_opaque_id(),
                "job_id": claim.job_id,
                "run_id": claim.run_id,
                "artifact_kind": item.artifact_kind,
                "object_ref_json": item.object_ref,
                "content_sha256": item.content_sha256,
                "provenance_json": item.provenance,
                "visibility": "evaluation_internal",
                "status": "ready",
                "error_code": None,
            }
            artifact = await self.artifact_dal.create_output_idempotent(values)
            if artifact is None:
                artifact = await self.artifact_dal.get_for_run_kind(
                    job_id=claim.job_id,
                    run_id=claim.run_id,
                    artifact_kind=item.artifact_kind,
                )
                if artifact is None:
                    raise EvaluationExecutionConflict(
                        "evaluation_artifact_create_conflict"
                    )
                if (
                    artifact.content_sha256 != item.content_sha256
                    or artifact.object_ref_json != item.object_ref
                ):
                    raise EvaluationExecutionConflict("evaluation_artifact_hash_drift")
            artifact_ids[item.artifact_kind] = artifact.id

        run_summary = {
            **summary,
            "artifact_ids": dict(sorted(artifact_ids.items())),
        }
        run = await self.run_dal.cas_update(
            run_id=claim.run_id,
            expected_version=claim.run_state_version,
            values={
                "status": "succeeded",
                "summary_json": run_summary,
                "error_code": None,
                "error_message": None,
                "finished_at": finished_at,
            },
        )
        if run is None:
            raise EvaluationExecutionConflict("evaluation_run_writeback_conflict")
        job = await self.job_dal.finish_execution(
            job_id=claim.job_id,
            expected_version=claim.job_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            finished_at=finished_at,
            status="completed",
            result_artifact_id=artifact_ids["metric_summary"],
            error_code=None,
            error_message=None,
        )
        if job is None:
            raise EvaluationExecutionConflict("evaluation_job_writeback_conflict")
        return {
            "job_id": job.id,
            "job_state_version": job.state_version,
            "run_id": run.id,
            "run_state_version": run.state_version,
            "artifact_ids": artifact_ids,
        }

    async def release_retry(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        released_at: datetime,
        next_retry_at: datetime,
        error_code: str,
    ) -> bool:
        job = await self.job_dal.release_retry(
            job_id=claim.job_id,
            expected_version=claim.job_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            released_at=released_at,
            next_retry_at=next_retry_at,
            error_code=error_code,
            error_message=error_code,
        )
        return job is not None

    async def fail(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        failed_at: datetime,
        status: str,
        error_code: str,
    ) -> bool:
        if status not in {"failed", "dead_letter"}:
            raise ValueError("evaluation_failure_status_invalid")
        run = await self.run_dal.cas_update(
            run_id=claim.run_id,
            expected_version=claim.run_state_version,
            values={
                "status": "failed",
                "error_code": error_code,
                "error_message": error_code,
                "finished_at": failed_at,
            },
        )
        if run is None:
            return False
        job = await self.job_dal.finish_execution(
            job_id=claim.job_id,
            expected_version=claim.job_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            finished_at=failed_at,
            status=status,
            result_artifact_id=None,
            error_code=error_code,
            error_message=error_code,
        )
        if job is None:
            raise EvaluationExecutionConflict("evaluation_job_writeback_conflict")
        return True

    async def reconcile_expired(
        self, *, now: datetime, max_attempts: int, limit: int = 100
    ) -> dict[str, int]:
        result = await self.job_dal.reconcile_expired_execution_leases(
            now=now, max_attempts=max_attempts, limit=limit
        )
        dead_letter_job_ids = list(result.pop("dead_letter_job_ids"))
        for job_id in dead_letter_job_ids:
            run = await self.run_dal.get_by_job_run_no(job_id=job_id, run_no=1)
            if run is None or run.status != "started":
                continue
            updated = await self.run_dal.cas_update(
                run_id=run.id,
                expected_version=run.state_version,
                values={
                    "status": "failed",
                    "error_code": "evaluation_worker_lease_expired",
                    "error_message": "evaluation worker lease expired before writeback",
                    "finished_at": now,
                },
            )
            if updated is None:
                raise EvaluationExecutionConflict("evaluation_run_reconcile_conflict")
        return result

    async def _load_job_artifact(
        self, *, artifact_id: str, job_id: str, expected_kind: str
    ):
        artifact = await self.artifact_dal.get_by_id(artifact_id)
        if (
            artifact is None
            or artifact.job_id != job_id
            or artifact.run_id is not None
            or artifact.artifact_kind != expected_kind
            or artifact.status != "ready"
        ):
            raise EvaluationExecutionConflict("evaluation_input_artifact_invalid")
        return artifact

    @staticmethod
    def _validate_frozen_run(run: Any, expected: dict[str, Any]) -> None:
        frozen_fields = (
            "dataset_fingerprint",
            "gold_fingerprint",
            "scorer_fingerprint",
            "experiment_fingerprint",
            "case_split_sha256",
            "denominator_contract_sha256",
            "input_manifest_artifact_sha256",
            "sanitization_artifact_sha256",
        )
        if any(getattr(run, field) != expected[field] for field in frozen_fields):
            raise EvaluationExecutionConflict("evaluation_run_fingerprint_drift")


__all__ = [
    "EvaluationExecutionClaim",
    "EvaluationExecutionConflict",
    "EvaluationExecutionError",
    "EvaluationExecutionNotFound",
    "EvaluationExecutionService",
    "StoredEvaluationArtifact",
]
