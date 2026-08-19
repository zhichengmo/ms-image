import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contexts import ControlPlaneContext
from app.crud.evaluation import (
    EvaluationArtifactDal,
    EvaluationJobDal,
    EvaluationOutboxDal,
    EvaluationRunDal,
)
from app.models.imaging_base import new_opaque_id
from app.schemas.evaluation import (
    EvaluationArtifactResponse,
    EvaluationJobCreate,
    EvaluationJobResponse,
    EvaluationRunResponse,
)


class EvaluationServiceError(ValueError):
    pass


class EvaluationNotFoundError(EvaluationServiceError):
    pass


class EvaluationStateConflictError(EvaluationServiceError):
    pass


class EvaluationValidationError(EvaluationServiceError):
    pass


class EvaluationService:
    def __init__(self, db: AsyncSession):
        self.job_dal = EvaluationJobDal(db)
        self.outbox_dal = EvaluationOutboxDal(db)
        self.run_dal = EvaluationRunDal(db)
        self.artifact_dal = EvaluationArtifactDal(db)

    async def create_job(
        self, *, payload: EvaluationJobCreate, context: ControlPlaneContext
    ) -> EvaluationJobResponse:
        self._validate_case_split(payload.case_split)
        self._validate_denominators(payload.denominator_contract)
        self._validate_artifact(
            payload.input_manifest.object_ref, payload.input_manifest.content_sha256
        )
        self._validate_artifact(
            payload.sanitization.object_ref, payload.sanitization.content_sha256
        )
        if payload.sanitization.provenance.get("sanitized") is not True:
            raise EvaluationValidationError("sanitization_proof_required")

        request_payload_sha256 = self._sha(
            self._normalized_request_payload(payload=payload, context=context)
        )
        business_key = self._sha(
            {
                "requester_id": context.subject_id,
                "request_id": payload.request_id,
            }
        )
        existing = await self.job_dal.get_by_business_key(business_key)
        if existing is not None:
            self._ensure_idempotent_payload(existing, request_payload_sha256)
            return EvaluationJobResponse.model_validate(existing)

        job_id = new_opaque_id()
        input_id = new_opaque_id()
        sanitization_id = new_opaque_id()
        job = await self.job_dal.create_idempotent(
            {
                "id": job_id,
                "requester_id": context.subject_id,
                "business_key": business_key,
                "request_payload_sha256": request_payload_sha256,
                "dataset_fingerprint": payload.dataset_fingerprint,
                "gold_fingerprint": payload.gold_fingerprint,
                "scorer_fingerprint": payload.scorer_fingerprint,
                "experiment_fingerprint": payload.experiment_fingerprint,
                "case_split_json": payload.case_split,
                "denominator_contract_json": payload.denominator_contract,
                "input_manifest_artifact_id": input_id,
                "sanitization_artifact_id": sanitization_id,
                "status": "queued",
                "state_version": 0,
            }
        )
        if job is None:
            existing = await self.job_dal.get_by_business_key(business_key)
            if existing is None:
                raise EvaluationStateConflictError("evaluation_job_create_conflict")
            self._ensure_idempotent_payload(existing, request_payload_sha256)
            return EvaluationJobResponse.model_validate(existing)

        artifact_values = (
            (input_id, "input_manifest", payload.input_manifest),
            (sanitization_id, "sanitization", payload.sanitization),
        )
        for artifact_id, kind, item in artifact_values:
            await self.artifact_dal.create_append_only(
                {
                    "id": artifact_id,
                    "job_id": job_id,
                    "run_id": None,
                    "artifact_kind": kind,
                    "object_ref_json": item.object_ref,
                    "content_sha256": item.content_sha256,
                    "provenance_json": item.provenance,
                    "visibility": "evaluation_internal",
                    "status": "ready",
                }
            )
        trace_id = f"evaluation:{job.id}:{job.state_version}"
        message = {
            "job_id": job.id,
            "expected_state_version": job.state_version,
            "trace_id": trace_id,
        }
        outbox = await self.outbox_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "job_id": job.id,
                "aggregate_version": job.state_version,
                "event_key": self.outbox_dal.event_key(job.id, job.state_version),
                "event_type": self.outbox_dal.EVENT_TYPE,
                "destination_key": self.outbox_dal.DESTINATION_KEY,
                "trace_id": trace_id,
                "message_version": self.outbox_dal.MESSAGE_VERSION,
                "message_json": message,
                "message_sha256": self.outbox_dal.message_sha256(message),
                "publish_status": "pending",
                "publish_attempt_count": 0,
            }
        )
        if outbox is None:
            raise EvaluationStateConflictError("evaluation_outbox_create_conflict")
        return EvaluationJobResponse.model_validate(job)

    async def get_job(self, job_id: str) -> EvaluationJobResponse:
        job = await self.job_dal.get_by_id(job_id)
        if job is None:
            raise EvaluationNotFoundError("evaluation_job_not_found")
        return EvaluationJobResponse.model_validate(job)

    async def cancel_job(
        self, job_id: str, expected_version: int
    ) -> EvaluationJobResponse:
        job = await self.job_dal.get_by_id(job_id)
        if job is None:
            raise EvaluationNotFoundError("evaluation_job_not_found")
        if job.status in {"completed", "failed", "cancelled"}:
            return EvaluationJobResponse.model_validate(job)
        updated = await self.job_dal.cas_update(
            job_id=job.id,
            expected_version=expected_version,
            values={"status": "cancelled", "error_code": "cancelled_by_control_plane"},
        )
        if updated is None:
            raise EvaluationStateConflictError("evaluation_job_cancel_conflict")
        return EvaluationJobResponse.model_validate(updated)

    async def create_run(self, job_id: str) -> EvaluationRunResponse:
        job = await self.job_dal.get_by_id(job_id)
        if job is None or job.status == "cancelled":
            raise EvaluationStateConflictError("evaluation_job_not_runnable")
        rows = await self.run_dal.list_for_job(job.id)
        run = await self.run_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "job_id": job.id,
                "run_no": len(rows) + 1,
                "dataset_fingerprint": job.dataset_fingerprint,
                "gold_fingerprint": job.gold_fingerprint,
                "scorer_fingerprint": job.scorer_fingerprint,
                "status": "pending",
                "state_version": 0,
            }
        )
        if run is None:
            raise EvaluationStateConflictError("evaluation_run_create_conflict")
        return EvaluationRunResponse.model_validate(run)

    async def list_runs(self, job_id: str) -> list[EvaluationRunResponse]:
        return [
            EvaluationRunResponse.model_validate(item)
            for item in await self.run_dal.list_for_job(job_id)
        ]

    async def get_run(self, run_id: str) -> EvaluationRunResponse:
        run = await self.run_dal.get_by_id(run_id)
        if run is None:
            raise EvaluationNotFoundError("evaluation_run_not_found")
        return EvaluationRunResponse.model_validate(run)

    async def list_artifacts(self, job_id: str) -> list[EvaluationArtifactResponse]:
        return [
            EvaluationArtifactResponse.model_validate(item)
            for item in await self.artifact_dal.list_for_job(job_id)
        ]

    async def get_artifact(self, artifact_id: str) -> EvaluationArtifactResponse:
        artifact = await self.artifact_dal.get_by_id(artifact_id)
        if artifact is None:
            raise EvaluationNotFoundError("evaluation_artifact_not_found")
        return EvaluationArtifactResponse.model_validate(artifact)

    @staticmethod
    def _normalized_request_payload(
        *, payload: EvaluationJobCreate, context: ControlPlaneContext
    ) -> dict[str, Any]:
        return {
            "requester_id": context.subject_id,
            "request_id": payload.request_id,
            "dataset_fingerprint": payload.dataset_fingerprint,
            "gold_fingerprint": payload.gold_fingerprint,
            "scorer_fingerprint": payload.scorer_fingerprint,
            "experiment_fingerprint": payload.experiment_fingerprint,
            "case_split": payload.case_split,
            "denominator_contract": payload.denominator_contract,
            "input_manifest_artifact_sha256": payload.input_manifest.content_sha256,
            "sanitization_artifact_sha256": payload.sanitization.content_sha256,
            "input_manifest_object_ref": payload.input_manifest.object_ref,
            "input_manifest_provenance": payload.input_manifest.provenance,
            "sanitization_object_ref": payload.sanitization.object_ref,
            "sanitization_provenance": payload.sanitization.provenance,
        }

    @staticmethod
    def _ensure_idempotent_payload(job: Any, expected_sha256: str) -> None:
        if job.request_payload_sha256 != expected_sha256:
            raise EvaluationStateConflictError("evaluation_idempotency_conflict")

    @staticmethod
    def _validate_artifact(ref: dict[str, Any], sha: str) -> None:
        required = (
            "storage_profile",
            "object_key",
            "sha256",
            "size_bytes",
            "content_type",
        )
        if any(not ref.get(key) for key in required) or ref.get("sha256") != sha:
            raise EvaluationValidationError("evaluation_artifact_invalid")

    @staticmethod
    def _validate_case_split(value: dict[str, Any]) -> None:
        if (
            value.get("role") not in {"development", "failure_bank", "holdout"}
            or not isinstance(value.get("case_count"), int)
            or value["case_count"] < 1
        ):
            raise EvaluationValidationError("evaluation_case_split_invalid")

    @staticmethod
    def _validate_denominators(value: dict[str, Any]) -> None:
        if value.get("medical") is None or value.get("population") is None:
            raise EvaluationValidationError("evaluation_denominator_contract_invalid")

    @staticmethod
    def _sha(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
