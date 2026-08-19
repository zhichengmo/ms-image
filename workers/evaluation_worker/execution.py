"""Reliable Evaluation consumer orchestration with external Artifact I/O."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.evaluation import JsonArtifactStore
from app.core.imaging.object_store import (
    OSSObjectStore,
    ObjectStorageGateway,
    ObjectStoreError,
)
from app.schemas.evaluation_execution import EvaluationInputManifest
from app.service.evaluation_execution_service import (
    EvaluationExecutionClaim,
    EvaluationExecutionConflict,
    EvaluationExecutionService,
    StoredEvaluationArtifact,
)
from app.service.evaluation_fake_scorer import (
    EvaluationScoringError,
    FakeEvaluationScorer,
    ScoredArtifact,
)


class EvaluationExecutionWorker:
    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession],
        gateway_factory: Callable[[], ObjectStorageGateway] = OSSObjectStore,
        scorer_factory: Callable[[], FakeEvaluationScorer] = FakeEvaluationScorer,
    ):
        self.session_factory = session_factory_
        self.gateway_factory = gateway_factory
        self.scorer_factory = scorer_factory

    async def execute(
        self,
        *,
        event_id: str,
        message: dict[str, Any],
        message_version: str,
        trace_id: str,
        owner_id: str,
        lease_seconds: int,
        max_attempts: int,
    ) -> dict[str, Any]:
        if lease_seconds < 10 or max_attempts < 1:
            raise ValueError("evaluation_worker_runtime_invalid")
        claimed_at = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                claim = await EvaluationExecutionService(session).claim(
                    event_id=event_id,
                    message=message,
                    message_version=message_version,
                    header_trace_id=trace_id,
                    owner_id=owner_id,
                    claimed_at=claimed_at,
                    lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                    max_attempts=max_attempts,
                )
        if claim is None:
            return {"outcome": "already_applied", "event_id": event_id}

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat_loop(
                claim=claim,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
                stop=stop_heartbeat,
                lease_lost=lease_lost,
            )
        )
        try:
            artifact_store = JsonArtifactStore(self.gateway_factory())
            manifest_data = await artifact_store.load_verified_json(
                object_ref=claim.input_manifest_object_ref,
                expected_sha256=claim.input_manifest_sha256,
            )
            sanitization_data = await artifact_store.load_verified_json(
                object_ref=claim.sanitization_object_ref,
                expected_sha256=claim.sanitization_sha256,
            )
            if (
                claim.sanitization_provenance.get("sanitized") is not True
                or not isinstance(sanitization_data, dict)
                or sanitization_data.get("sanitized") is not True
            ):
                raise EvaluationScoringError("sanitization_proof_invalid")
            manifest = EvaluationInputManifest.model_validate(manifest_data)
            bundle = self.scorer_factory().score(
                manifest=manifest,
                dataset_fingerprint=claim.dataset_fingerprint,
                gold_fingerprint=claim.gold_fingerprint,
                scorer_fingerprint=claim.scorer_fingerprint,
                experiment_fingerprint=claim.experiment_fingerprint,
                case_split=claim.case_split,
                denominator_contract=claim.denominator_contract,
            )
            stored = [
                await self._store_artifact(
                    artifact_store=artifact_store,
                    claim=claim,
                    artifact=artifact,
                )
                for artifact in bundle.artifacts
            ]
        except (EvaluationScoringError, ValidationError) as exc:
            return await self._finish_failure(
                claim=claim,
                owner_id=owner_id,
                error_code=self._safe_contract_error(exc),
                status="failed",
            )
        except ObjectStoreError as exc:
            error_code = self._safe_object_error(exc)
            if error_code in {
                "evaluation_artifact_ref_invalid",
                "evaluation_artifact_content_empty",
                "evaluation_artifact_serialization_failed",
                "evaluation_artifact_json_invalid",
                "object_storage_profile_mismatch",
                "evaluation_artifact_profile_drift",
                "evaluation_artifact_version_drift",
                "evaluation_artifact_size_drift",
                "evaluation_artifact_content_type_invalid",
                "evaluation_artifact_content_type_drift",
                "evaluation_artifact_hash_drift",
                "evaluation_output_artifact_profile_drift",
                "evaluation_output_artifact_content_type_drift",
                "evaluation_output_artifact_size_drift",
                "evaluation_output_artifact_hash_drift",
            }:
                return await self._finish_failure(
                    claim=claim,
                    owner_id=owner_id,
                    error_code=error_code,
                    status="failed",
                )
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code=error_code,
                max_attempts=max_attempts,
            )
        except Exception:
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code="evaluation_worker_execution_error",
                max_attempts=max_attempts,
            )
        finally:
            stop_heartbeat.set()
            await heartbeat

        if lease_lost.is_set():
            return {
                "outcome": "lease_lost",
                "event_id": event_id,
                "job_id": claim.job_id,
            }
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    result = await EvaluationExecutionService(session).complete(
                        claim=claim,
                        owner_id=owner_id,
                        artifacts=stored,
                        summary=bundle.metrics.model_dump(mode="json"),
                        finished_at=datetime.utcnow(),
                    )
        except EvaluationExecutionConflict as exc:
            return {
                "outcome": "lease_lost",
                "event_id": event_id,
                "job_id": claim.job_id,
                "error_code": str(exc),
            }
        except Exception:
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code="evaluation_worker_commit_error",
                max_attempts=max_attempts,
            )
        return {"outcome": "completed", "event_id": event_id, **result}

    async def _heartbeat_loop(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        lease_seconds: int,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = max(1.0, min(30.0, lease_seconds / 3))
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            heartbeat_at = datetime.utcnow()
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        renewed = await EvaluationExecutionService(session).heartbeat(
                            claim=claim,
                            owner_id=owner_id,
                            heartbeat_at=heartbeat_at,
                            lease_expires_at=heartbeat_at
                            + timedelta(seconds=lease_seconds),
                        )
            except Exception:
                renewed = False
            if not renewed:
                lease_lost.set()
                return

    async def _schedule_retry(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        error_code: str,
        max_attempts: int,
    ) -> dict[str, Any]:
        if claim.attempt_count >= max_attempts:
            return await self._finish_failure(
                claim=claim,
                owner_id=owner_id,
                error_code="evaluation_attempts_exhausted",
                status="dead_letter",
            )
        delay_seconds = min(300, 2 ** max(0, claim.attempt_count - 1))
        released_at = datetime.utcnow()
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    released = await EvaluationExecutionService(session).release_retry(
                        claim=claim,
                        owner_id=owner_id,
                        released_at=released_at,
                        next_retry_at=released_at + timedelta(seconds=delay_seconds),
                        error_code=error_code,
                    )
        except Exception:
            released = False
        return {
            "outcome": "retry" if released else "lease_lost",
            "event_id": claim.event_id,
            "job_id": claim.job_id,
            "error_code": error_code,
            "retry_after_seconds": delay_seconds,
        }

    async def _finish_failure(
        self,
        *,
        claim: EvaluationExecutionClaim,
        owner_id: str,
        error_code: str,
        status: str,
    ) -> dict[str, Any]:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    finished = await EvaluationExecutionService(session).fail(
                        claim=claim,
                        owner_id=owner_id,
                        failed_at=datetime.utcnow(),
                        status=status,
                        error_code=error_code,
                    )
        except Exception:
            finished = False
        return {
            "outcome": status if finished else "lease_lost",
            "event_id": claim.event_id,
            "job_id": claim.job_id,
            "error_code": error_code,
        }

    async def _store_artifact(
        self,
        *,
        artifact_store: JsonArtifactStore,
        claim: EvaluationExecutionClaim,
        artifact: ScoredArtifact,
    ) -> StoredEvaluationArtifact:
        stored = await artifact_store.store_bytes(
            object_key=(
                f"evaluation/{claim.job_id}/{claim.run_id}/"
                f"{artifact.artifact_kind}-{artifact.content_sha256}.json"
            ),
            content=artifact.content,
        )
        if stored.content_sha256 != artifact.content_sha256:
            raise ObjectStoreError("evaluation_output_artifact_hash_drift")
        provenance = {
            "producer": "fake_evaluation_scorer",
            "schema_version": artifact.schema_version,
            "job_id": claim.job_id,
            "run_id": claim.run_id,
            "dataset_fingerprint": claim.dataset_fingerprint,
            "gold_fingerprint": claim.gold_fingerprint,
            "scorer_fingerprint": claim.scorer_fingerprint,
            "experiment_fingerprint": claim.experiment_fingerprint,
            "sanitized": True,
        }
        return StoredEvaluationArtifact(
            artifact_kind=artifact.artifact_kind,
            object_ref=stored.object_ref,
            content_sha256=stored.content_sha256,
            provenance=provenance,
        )

    @staticmethod
    def _safe_contract_error(exc: BaseException) -> str:
        value = str(exc).strip()
        if value.startswith("evaluation_") or value.startswith("sanitization_"):
            return value[:80]
        return "evaluation_input_contract_invalid"

    @staticmethod
    def _safe_object_error(exc: BaseException) -> str:
        value = str(exc).strip()
        if (
            value
            and len(value) <= 80
            and all(char.isalnum() or char == "_" for char in value)
        ):
            return value
        return "evaluation_object_store_error"


__all__ = ["EvaluationExecutionWorker"]
