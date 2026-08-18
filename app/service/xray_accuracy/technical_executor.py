"""Database-backed technical stage executor for the validation-only chain."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.imaging import (
    FailClosedImageResolver,
    ImageResolver,
    ImageResolverError,
    FailClosedSourceImageFetcher,
    OSSObjectStore,
    ObjectStoreError,
    SourceImageFetcher,
    XRayImageIngestService,
)
from app.crud.xray_accuracy import (
    XRayRunDal,
    XRayStageCheckpointDal,
    XRayTraceEventDal,
    XRayRequestSnapshotDal,
    XRayImageAssetDal,
    XRayStudySnapshotDal,
)
from app.service.xray_accuracy.ai_request_service import (
    ProviderNotQualifiedError,
    ProviderRequestError,
    XRayAIRequestService,
)
from .message_contract import InvalidWorkerMessage, validate_message


def _canonical_manifest_sha256(assets: list[Any]) -> str:
    """Hash only the ordered opaque asset IDs used by the Study contract."""
    manifest = [
        {"source_index": int(asset.source_index), "source_image_ref": str(asset.id)}
        for asset in assets
    ]
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class TechnicalExecutor:
    """Execute only the request_gate technical node with stub/replay AI."""

    def __init__(
        self,
        db: AsyncSession,
        image_resolver: ImageResolver | None = None,
        object_store: OSSObjectStore | None = None,
        source_image_fetcher: SourceImageFetcher | None = None,
        ai_service: XRayAIRequestService | None = None,
    ):
        self.db = db
        self.run_dal = XRayRunDal(db)
        self.checkpoint_dal = XRayStageCheckpointDal(db)
        self.trace_dal = XRayTraceEventDal(db)
        self.snapshot_dal = XRayRequestSnapshotDal(db)
        self.study_dal = XRayStudySnapshotDal(db)
        self.asset_dal = XRayImageAssetDal(db)
        self.image_resolver = image_resolver or FailClosedImageResolver()
        self.object_store = object_store
        self.source_image_fetcher = source_image_fetcher or FailClosedSourceImageFetcher()
        self.ai_service = ai_service or XRayAIRequestService(db)

    async def _execute_study_preparation(
        self,
        *,
        db: AsyncSession,
        run: Any,
        checkpoint: Any,
        event: dict[str, Any],
        tenant_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        """Prepare every declared asset and freeze the Study atomically.

        This is an engineering-only stage.  It never creates a medical
        verdict and fails closed when the source fetcher or object store is
        not configured.
        """
        request_snapshot = await self.snapshot_dal.get_by_run(
            run_id=run.id, tenant_id=tenant_id
        )
        if request_snapshot is None:
            raise ValueError("technical_snapshot_not_found")
        run_id = run.id
        run_trace_namespace = run.trace_namespace
        run_release_fingerprint = run.release_fingerprint
        checkpoint_id = checkpoint.id
        study_revision_id = request_snapshot.study_revision
        study_snapshot = await self.study_dal.get_by_revision(
            tenant_id=tenant_id,
            study_revision_id=study_revision_id,
        )
        if study_snapshot is None:
            raise ValueError("technical_study_snapshot_not_found")
        assets = await self.asset_dal.list_originals_for_study(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
        if len(assets) != study_snapshot.expected_image_count:
            raise ValueError("study_asset_count_mismatch")
        if [asset.source_index for asset in assets] != list(range(len(assets))):
            raise ValueError("study_asset_source_index_mismatch")
        if [asset.id for asset in assets] != list(
            request_snapshot.manifest_json[i]["source_image_ref"]
            for i in range(len(request_snapshot.manifest_json))
        ):
            raise ValueError("study_manifest_asset_mismatch")
        if any(asset.asset_status != "uploaded" for asset in assets):
            await self._renew_checkpoint(
                checkpoint_id=checkpoint.id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
            object_store = self.object_store
            if object_store is None:
                try:
                    object_store = OSSObjectStore()
                except ObjectStoreError as exc:
                    raise ValueError(str(exc)) from exc
            ingest = XRayImageIngestService(
                session_factory=None,  # in-session form is used below
                object_store=object_store,
                fetcher=self.source_image_fetcher,
            )
            for asset in assets:
                if asset.asset_status != "uploaded":
                    await ingest.ingest_asset_in_db(
                        db, tenant_id=tenant_id, asset_id=asset.id
                    )
                    await self._renew_checkpoint(
                        checkpoint_id=checkpoint.id,
                        tenant_id=tenant_id,
                        owner_id=owner_id,
                        lease_seconds=lease_seconds,
                    )
            assets = await self.asset_dal.list_originals_for_study(
                tenant_id=tenant_id, study_revision_id=study_revision_id
            )
        if any(asset.asset_status != "uploaded" for asset in assets):
            raise ValueError("study_asset_not_uploaded")
        ordered_ids = [str(asset.id) for asset in assets]
        manifest_sha256 = _canonical_manifest_sha256(assets)
        if study_snapshot.expected_manifest_sha256 != manifest_sha256:
            raise ValueError("study_manifest_hash_mismatch")
        if list(study_snapshot.ordered_source_image_ids_json or []) != ordered_ids:
            raise ValueError("study_ordered_asset_ids_mismatch")
        if any(
            not asset.content_sha256
            or not asset.object_key
            or not asset.object_key.startswith(
                OSSObjectStore.expected_object_prefix(
                    tenant_id=tenant_id,
                    study_revision_id=study_revision_id,
                    source_index=asset.source_index,
                )
            )
            for asset in assets
        ):
            raise ValueError("study_asset_storage_binding_invalid")
        frozen = await self.study_dal.freeze(
            tenant_id=tenant_id,
            study_revision_id=study_revision_id,
            status="ready_full_study",
            coverage_status="ready_for_request",
            identity_confidence="confirmed",
            projection_groups=[
                {
                    "source_index": asset.source_index,
                    "projection": asset.projection,
                    "body_part": asset.body_part,
                }
                for asset in assets
            ],
            expected_manifest_sha256=manifest_sha256,
            ordered_source_image_ids=ordered_ids,
            frozen_at=datetime.utcnow(),
        )
        if frozen is None:
            frozen = await self.study_dal.get_by_revision(
                tenant_id=tenant_id,
                study_revision_id=study_revision_id,
            )
        if frozen is None or frozen.study_status != "ready_full_study":
            raise ValueError("study_freeze_conflict")
        if (
            frozen.expected_manifest_sha256 != manifest_sha256
            or list(frozen.ordered_source_image_ids_json or []) != ordered_ids
        ):
            raise ValueError("study_freeze_manifest_conflict")
        coverage_status = frozen.coverage_status
        if not await self.checkpoint_dal.complete_checkpoint(
            checkpoint_id=checkpoint_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            finished_at=datetime.utcnow(),
        ):
            raise ValueError("technical_checkpoint_completion_conflict")
        updated = await self.run_dal.cas_update(
            run_id=run_id,
            tenant_id=tenant_id,
            expected_version=event["expected_version"],
            values={
                "execution_status": "completed",
                "engineering_eligibility": "clean",
                "completed_at": datetime.utcnow(),
            },
        )
        if updated is None:
            raise ValueError("technical_run_completion_conflict")
        await self.trace_dal.create_event_once(
            {
                "id": f"trace-study-preparation-{event['task_id']}",
                "run_id": run_id,
                "tenant_id": tenant_id,
                "trace_namespace": run_trace_namespace,
                "stage_key": event["stage_key"],
                "event_type": "technical_study_preparation_completed",
                "event_payload_json": {
                    "study_revision_id": study_revision_id,
                    "image_count": len(assets),
                    "coverage_status": coverage_status,
                    "medical_verdict_produced": False,
                },
                "fingerprint": run_release_fingerprint,
                "state_version": updated.state_version,
            }
        )
        return {
            "run_id": run_id,
            "task_id": event["task_id"],
            "execution_status": updated.execution_status,
            "engineering_eligibility": updated.engineering_eligibility,
            "ai_medical_status": updated.ai_medical_status,
            "study_revision_id": study_revision_id,
            "image_count": len(assets),
            "medical_verdict_produced": False,
        }

    async def execute(
        self,
        message: dict[str, Any],
        *,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int = 120,
    ) -> dict[str, Any]:
        try:
            event = validate_message(message)
        except InvalidWorkerMessage as exc:
            raise ValueError("technical_message_invalid") from exc
        if event["stage_key"] != "request_gate":
            raise ValueError("technical_stage_not_enabled")
        if not owner_id.strip() or lease_seconds <= 0:
            raise ValueError("technical_lease_invalid")

        run = await self.run_dal.get_by_id(event["run_id"], tenant_id)
        if run is None:
            raise ValueError("technical_run_not_found")
        # DalBase CAS reads use expire_all=True. Capture immutable bindings
        # before later checkpoint/run updates can expire this ORM instance;
        # async attribute refresh outside greenlet is a hard worker failure.
        run_id = run.id
        run_trace_namespace = run.trace_namespace
        run_release_fingerprint = run.release_fingerprint
        requested_operation = run.requested_operation
        if run.release_fingerprint != event["release_fingerprint"] or run.trace_namespace != event["trace_namespace"]:
            raise ValueError("technical_run_binding_or_cas_conflict")
        if run.execution_mode != "validation_only" or run.ai_medical_status != "not_produced":
            raise ValueError("technical_run_not_validation_only")
        checkpoint = await self.checkpoint_dal.get_by_attempt_id(
            run_id=run_id,
            tenant_id=tenant_id,
            attempt_id=event["task_id"],
        )
        if checkpoint is not None and checkpoint.stage_key != "request_gate":
            raise ValueError("technical_checkpoint_not_found")
        checkpoint_id = checkpoint.id if checkpoint is not None else None
        if run.execution_status in {"completed", "failed", "cancel_requested", "cancelled"}:
            if checkpoint is not None:
                await self.checkpoint_dal.mark_late(
                    checkpoint_id=checkpoint_id,
                    tenant_id=tenant_id,
                    finished_at=datetime.utcnow(),
                )
            await self.trace_dal.create_event_once(
                {
                    "id": f"trace-late-{event['task_id']}",
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "trace_namespace": run_trace_namespace,
                    "stage_key": event["stage_key"],
                    "event_type": "technical_late_result",
                    "event_payload_json": {
                        "late_reason": "cancelled_or_terminal",
                        "medical_verdict_produced": False,
                    },
                    "fingerprint": run_release_fingerprint,
                    "state_version": run.state_version,
                }
            )
            return {
                "run_id": run_id,
                "task_id": event["task_id"],
                "execution_status": run.execution_status,
                "engineering_eligibility": run.engineering_eligibility,
                "ai_medical_status": run.ai_medical_status,
                "medical_verdict_produced": False,
            }
        if run.state_version != event["expected_version"]:
            raise ValueError("technical_run_binding_or_cas_conflict")
        if checkpoint is None:
            raise ValueError("technical_checkpoint_not_found")
        now = datetime.utcnow()
        claimed = await self.checkpoint_dal.claim_checkpoint(
            checkpoint_id=checkpoint_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            expected_version=event["expected_version"],
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            started_at=now,
        )
        if claimed is None:
            raise ValueError("technical_checkpoint_claim_conflict")

        try:
            if requested_operation == "prepare_study":
                return await self._execute_study_preparation(
                    db=self.db,
                    run=run,
                    checkpoint=checkpoint,
                    event=event,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    lease_seconds=lease_seconds,
                )
            images = ()
            expected_source_image_refs: tuple[str, ...] = ()
            expected_source_image_hashes: tuple[str, ...] = ()
            if self.ai_service.provider.provider_key != "stub/replay":
                snapshot = await self.snapshot_dal.get_by_run(
                    run_id=run_id,
                    tenant_id=tenant_id,
                )
                if snapshot is None:
                    raise ValueError("technical_snapshot_not_found")
                study = await self.study_dal.get_by_revision(
                    tenant_id=tenant_id,
                    study_revision_id=snapshot.study_revision,
                )
                if (
                    study is None
                    or study.study_id != run.study_id
                    or study.study_status != "ready_full_study"
                    or study.frozen_at is None
                ):
                    raise ValueError("technical_study_not_ready")
                expected_source_image_refs = tuple(
                    str(item["source_image_ref"])
                    for item in snapshot.manifest_json
                )
                assets = await self.asset_dal.list_originals_for_study(
                    tenant_id=tenant_id,
                    study_revision_id=snapshot.study_revision,
                )
                if (
                    len(assets) != study.expected_image_count
                    or [asset.id for asset in assets] != list(expected_source_image_refs)
                    or _canonical_manifest_sha256(assets) != study.expected_manifest_sha256
                    or any(not asset.content_sha256 for asset in assets)
                ):
                    raise ValueError("technical_study_manifest_mismatch")
                expected_source_image_hashes = tuple(
                    str(asset.content_sha256) for asset in assets
                )
                try:
                    images = await self.image_resolver.resolve(
                        tenant_id=tenant_id,
                        run_id=run_id,
                        manifest=snapshot.manifest_json,
                    )
                except ImageResolverError as exc:
                    raise ValueError(exc.error_class) from exc
            # Extend the lease immediately before a potentially slow Provider
            # call.  The extension covers the configured hard timeout plus a
            # bounded grace period; the post-call heartbeat below prevents a
            # late response from being committed after lease loss.
            await self._renew_checkpoint(
                checkpoint_id=checkpoint_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                lease_seconds=max(
                    lease_seconds,
                    int(self.ai_service.pool.policy.hard_timeout_seconds) + 30,
                ),
            )
            response = await self.ai_service.execute_validation_request(
                tenant_id=tenant_id,
                run_id=run_id,
                attempt_id=event["task_id"],
                release_fingerprint=run_release_fingerprint,
                trace_namespace=run_trace_namespace,
                node_key=event["stage_key"],
                images=images,
                expected_source_image_refs=expected_source_image_refs,
                expected_source_image_hashes=expected_source_image_hashes,
                resolved_source_image_refs=tuple(
                    image.source_image_ref for image in images
                ),
            )
            await self._renew_checkpoint(
                checkpoint_id=checkpoint_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
            if response.output_json.get("medical_verdict") is not None:
                raise ValueError("technical_stub_returned_medical_verdict")
            if not await self.checkpoint_dal.complete_checkpoint(
                checkpoint_id=checkpoint_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                finished_at=datetime.utcnow(),
            ):
                raise ValueError("technical_checkpoint_completion_conflict")
            updated = await self.run_dal.cas_update(
                run_id=run_id,
                tenant_id=tenant_id,
                expected_version=event["expected_version"],
                values={
                    "execution_status": "completed",
                    "engineering_eligibility": "clean",
                    "completed_at": datetime.utcnow(),
                },
            )
            if updated is None:
                raise ValueError("technical_run_completion_conflict")
            await self.trace_dal.create_event_once(
                {
                    "id": f"trace-{event['task_id']}",
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "trace_namespace": run_trace_namespace,
                    "stage_key": event["stage_key"],
                    "event_type": "technical_ai_request_completed",
                    "event_payload_json": {
                        "provider_key": response.receipt_json.get(
                            "provider_key", self.ai_service.provider.provider_key
                        ),
                        "actual_model": response.actual_model,
                        "image_count": response.receipt_json.get(
                            "image_count_received"
                        )
                        or response.receipt_json.get(
                            "adapter_egress_proof", {}
                        ).get("image_count", 0),
                        "image_ordered_sha256": response.receipt_json.get("image_ordered_sha256"),
                        "coverage_status": response.receipt_json.get(
                            "coverage_status", "unknown"
                        ),
                        "model_call_recorded": True,
                        "medical_verdict_produced": False,
                    },
                    "fingerprint": run_release_fingerprint,
                    "state_version": updated.state_version,
                }
            )
            return {
                "run_id": run_id,
                "task_id": event["task_id"],
                "execution_status": updated.execution_status,
                "engineering_eligibility": updated.engineering_eligibility,
                "ai_medical_status": updated.ai_medical_status,
                "provider_request_id_sha256": response.receipt_json.get(
                    "provider_request_id_sha256"
                ),
                "prompt_key": "xray.request_gate.v1",
            }
        except Exception as exc:
            if isinstance(exc, ProviderRequestError):
                error_class = exc.error_class
                retryable = exc.retryable
            elif isinstance(exc, ProviderNotQualifiedError):
                reason = str(exc).strip()
                error_class = {
                    "real_provider_not_enabled": "provider_disabled",
                    "real_provider_not_qualified": "provider_not_qualified",
                    "image_manifest_not_resolved": "image_manifest_not_resolved",
                    "provider_output_contract": "provider_output_contract",
                }.get(reason, "provider_output_contract")
                retryable = False
            elif isinstance(exc, ValueError) and str(exc).startswith(("prompt_", "response_schema_")):
                error_class = str(exc)[:64]
                retryable = False
            elif isinstance(exc, ValueError) and str(exc) in {
                "technical_snapshot_not_found",
                "technical_study_snapshot_not_found",
                "technical_study_not_ready",
                "technical_study_manifest_mismatch",
                "study_asset_count_mismatch",
                "study_manifest_asset_mismatch",
                "study_asset_not_uploaded",
                "study_freeze_conflict",
                "study_freeze_manifest_invalid",
                "study_freeze_manifest_conflict",
                "study_manifest_hash_mismatch",
                "study_ordered_asset_ids_mismatch",
                "study_asset_source_index_mismatch",
                "study_asset_storage_binding_invalid",
                "object_store_not_configured",
                "object_store_upload_failed",
                "image_resolver_not_configured",
                "image_source_fetcher_not_configured",
                "image_source_manifest_not_configured",
                "image_source_manifest_invalid",
                "image_source_unavailable",
                "image_fetch_timeout",
                "image_source_forbidden",
                "image_manifest_invalid",
                "image_content_invalid",
                "image_content_too_large",
                "image_hash_mismatch",
                "technical_checkpoint_lease_lost",
            }:
                error_class = str(exc)
                retryable = error_class in {
                    "object_store_upload_failed",
                    "image_source_fetcher_not_configured",
                    "image_source_unavailable",
                    "image_fetch_timeout",
                    "technical_checkpoint_lease_lost",
                }
            elif "cas" in str(exc).casefold() or "conflict" in str(exc).casefold():
                error_class = "cas_conflict"
                retryable = True
            else:
                error_class = "technical_ai_request_failed"
                retryable = False
            failed = await self.checkpoint_dal.fail_checkpoint(
                checkpoint_id=checkpoint_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                finished_at=datetime.utcnow(),
                error_class=error_class,
                retryable=retryable,
            )
            if not failed:
                # Losing the lease/CAS means this worker no longer owns the
                # right to publish a failure.  Roll back the transaction and
                # let the caller reconcile instead of overwriting newer state.
                raise
            result_run = run
            if not retryable:
                result_run = await self.run_dal.cas_update(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    expected_version=event["expected_version"],
                    values={
                        "execution_status": "failed",
                        "engineering_eligibility": "failed",
                        "completed_at": datetime.utcnow(),
                    },
                )
                if result_run is None:
                    raise ValueError("technical_run_failure_conflict") from exc
            await self.trace_dal.create_event_once(
                {
                    "id": f"trace-failure-{event['task_id']}",
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "trace_namespace": run_trace_namespace,
                    "stage_key": event["stage_key"],
                    "event_type": "technical_ai_request_retry" if retryable else "technical_ai_request_failed",
                    "event_payload_json": {
                        "error_class": error_class,
                        "retryable": retryable,
                        "medical_verdict_produced": False,
                    },
                    "fingerprint": run_release_fingerprint,
                    "state_version": result_run.state_version,
                }
            )
            return {
                "run_id": run_id,
                "task_id": event["task_id"],
                "execution_status": result_run.execution_status,
                "engineering_eligibility": result_run.engineering_eligibility,
                "ai_medical_status": result_run.ai_medical_status,
                "error_class": error_class,
                "retryable": retryable,
                "medical_verdict_produced": False,
            }

    async def _renew_checkpoint(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> None:
        now = datetime.utcnow()
        if not await self.checkpoint_dal.heartbeat_checkpoint(
            checkpoint_id=checkpoint_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
        ):
            raise ValueError("technical_checkpoint_lease_lost")
