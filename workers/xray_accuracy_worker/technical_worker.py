"""Database-backed validation-only worker entrypoint.

This is the executable boundary between a committed Outbox row and the
technical executor. It deliberately does not open RabbitMQ or call a real
Provider; a future broker consumer can invoke the same method after relay
qualification. The transaction owns Outbox lease, Executor state changes,
and final Outbox acknowledgement together.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.async_db import session_factory
from app.core.ai.contracts import ProviderNotQualifiedError
from app.core.config import settings
from app.core.imaging import (
    ImageResolver,
    OSSObjectStore,
    ObjectStoreError,
    ApprovedManifestSourceImageFetcher,
    SourceImageFetcher,
    XRayOSSImageResolver,
)
from app.crud.xray_accuracy import (
    XRayOutboxDal,
    XRayRunDal,
    XRayStageCheckpointDal,
    XRayTraceEventDal,
)
from app.service.xray_accuracy.message_contract import InvalidWorkerMessage, validate_message
from app.service.xray_accuracy.technical_executor import TechnicalExecutor


class XRayTechnicalWorker:
    """Execute one tenant-scoped Outbox event with lease/CAS protection."""

    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession] = session_factory,
        executor_factory: Callable[[AsyncSession], TechnicalExecutor] | None = None,
        image_resolver: ImageResolver | None = None,
        object_store: OSSObjectStore | None = None,
        source_image_fetcher: SourceImageFetcher | None = None,
        outbox_factory: Callable[[AsyncSession], XRayOutboxDal] = XRayOutboxDal,
        run_factory: Callable[[AsyncSession], XRayRunDal] = XRayRunDal,
        trace_factory: Callable[[AsyncSession], XRayTraceEventDal] = XRayTraceEventDal,
        retry_delay_seconds: int = 5,
        max_attempts: int = settings.XRAY_WORKER_MAX_ATTEMPTS,
    ):
        if retry_delay_seconds <= 0 or max_attempts <= 0:
            raise ValueError("worker_retry_delay_invalid")
        self.session_factory = session_factory_
        if executor_factory is not None:
            self.executor_factory = executor_factory
        else:
            def _build_executor(db: AsyncSession) -> TechnicalExecutor:
                store = object_store
                resolver = image_resolver
                fetcher = source_image_fetcher
                # The default worker must be able to resolve a frozen Study
                # when real Provider mode is explicitly enabled.  Missing OSS
                # credentials remain fail-closed; they must never silently
                # fall back to caller URLs or an empty image set.
                if resolver is None and store is None and settings.AI_CONFIG_VERSION:
                    try:
                        store = OSSObjectStore()
                    except ObjectStoreError:
                        store = None
                if resolver is None and store is not None:
                    resolver = XRayOSSImageResolver(
                        session_factory=self.session_factory,
                        object_store=store,
                    )
                if fetcher is None and settings.AI_SOURCE_IMAGE_MANIFEST_PATH and settings.AI_SOURCE_IMAGE_ROOT:
                    try:
                        fetcher = ApprovedManifestSourceImageFetcher(
                            manifest_path=settings.AI_SOURCE_IMAGE_MANIFEST_PATH,
                            root_dir=settings.AI_SOURCE_IMAGE_ROOT,
                        )
                    except ObjectStoreError:
                        # Preparation remains fail-closed and reports a
                        # stable technical error through the Worker.
                        fetcher = None
                return TechnicalExecutor(
                    db,
                    image_resolver=resolver,
                    object_store=store,
                    source_image_fetcher=fetcher,
                )

            self.executor_factory = _build_executor
        self.outbox_factory = outbox_factory
        self.run_factory = run_factory
        self.trace_factory = trace_factory
        self.retry_delay_seconds = retry_delay_seconds
        self.max_attempts = max_attempts

    async def _execute_message_with_db(
        self,
        db: AsyncSession,
        message_payload: dict[str, Any],
        *,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        message = validate_message(message_payload)
        if message["stage_key"] == "cancel":
            run_dal = self.run_factory(db)
            checkpoint_dal = XRayStageCheckpointDal(db)
            outbox_dal = self.outbox_factory(db)
            trace_dal = self.trace_factory(db)
            run = await run_dal.get_by_id(message["run_id"], tenant_id)
            if run is None:
                raise ValueError("worker_cancel_run_not_found")
            if (
                run.release_fingerprint != message["release_fingerprint"]
                or run.trace_namespace != message["trace_namespace"]
            ):
                raise ValueError("worker_cancel_binding_conflict")
            # A repeated delivery after the terminal transition is idempotent:
            # it must not advance state_version or append a second terminal
            # trace.  The initial cancel request is a separate transition;
            # this worker message is the acknowledgement that closes it.
            if run.execution_status == "cancelled":
                result = {
                    "run_id": run.id,
                    "task_id": message["task_id"],
                    "execution_status": run.execution_status,
                    "state_version": run.state_version,
                    "ai_medical_status": run.ai_medical_status,
                    "cancel_acknowledged": True,
                    "medical_verdict_produced": False,
                }
            else:
                if run.execution_status != "cancel_requested":
                    raise ValueError("worker_cancel_state_conflict")
                if run.state_version != message["expected_version"]:
                    raise ValueError("worker_cancel_cas_conflict")
                updated = await run_dal.cas_update(
                    run_id=run.id,
                    tenant_id=tenant_id,
                    expected_version=message["expected_version"],
                    values={
                        "execution_status": "cancelled",
                        "completed_at": datetime.utcnow(),
                    },
                )
                if updated is None:
                    raise ValueError("worker_cancel_cas_conflict")
                await checkpoint_dal.cancel_for_run(
                    tenant_id=tenant_id,
                    run_id=updated.id,
                    finished_at=datetime.utcnow(),
                )
                await outbox_dal.cancel_pending_for_run(
                    tenant_id=tenant_id,
                    run_id=updated.id,
                    cancelled_at=datetime.utcnow(),
                )
                await trace_dal.create_event_once(
                    {
                        "id": f"trace-cancel-{message['task_id']}",
                        "run_id": updated.id,
                        "tenant_id": tenant_id,
                        "trace_namespace": updated.trace_namespace,
                        "stage_key": "cancel",
                        "event_type": "run_cancelled",
                        "event_payload_json": {
                            "cancel_acknowledged": True,
                            "medical_verdict_produced": False,
                        },
                        "fingerprint": updated.release_fingerprint,
                        "state_version": updated.state_version,
                    }
                )
                result = {
                    "run_id": updated.id,
                    "task_id": message["task_id"],
                    "execution_status": updated.execution_status,
                    "state_version": updated.state_version,
                    "ai_medical_status": updated.ai_medical_status,
                    "cancel_acknowledged": True,
                    "medical_verdict_produced": False,
                }
        else:
            result = await self.executor_factory(db).execute(
                message,
                tenant_id=tenant_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
        return message, result

    async def execute_message(
        self,
        message: dict[str, Any],
        *,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int = 120,
    ) -> dict[str, Any]:
        """Consume a broker whitelist message after Outbox relay publication.

        The relay has already acknowledged the Outbox row in this mode, so
        this method only owns Executor/Checkpoint/Run/Trace transitions.
        """
        if not tenant_id.strip() or not owner_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_identity_or_lease_invalid")
        async with self.session_factory() as db:
            async with db.begin():
                _, result = await self._execute_message_with_db(
                    db,
                    message,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    lease_seconds=lease_seconds,
                )
                return result

    async def execute_outbox_event(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int = 120,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        if not event_id.strip() or not tenant_id.strip() or not owner_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_identity_or_lease_invalid")
        if db is not None:
            return await self._execute_outbox_event_in_db(
                db,
                event_id=event_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
            )
        async with self.session_factory() as owned_db:
            async with owned_db.begin():
                return await self._execute_outbox_event_in_db(
                    owned_db,
                    event_id=event_id,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    lease_seconds=lease_seconds,
                )

    async def _execute_outbox_event_in_db(
        self,
        db: AsyncSession,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        # The lease must outlive the bounded Provider timeout and its grace
        # period.  A heartbeat below renews it at each transaction boundary;
        # this minimum prevents a normal 30s Provider call from being
        # classified as a worker crash when a deployment used a shorter
        # default lease.
        effective_lease_seconds = max(
            lease_seconds,
            int(settings.XRAY_WORKER_LEASE_SECONDS),
        )
        outbox = self.outbox_factory(db)
        row = await outbox.get_by_event_id(event_id=event_id, tenant_id=tenant_id)
        if row is None:
            raise ValueError("worker_outbox_not_found")
        if row.consumer_status == "completed":
            return {
                "event_id": event_id,
                "outcome": "duplicate",
                "publish_status": row.publish_status,
                "consumer_status": row.consumer_status,
            }
        if row.consumer_status == "dead_letter" or row.publish_status == "dead_letter":
            return {
                "event_id": event_id,
                "outcome": "dead_letter",
                "publish_status": row.publish_status,
                "consumer_status": row.consumer_status,
            }
        now = datetime.utcnow()
        claimed = await outbox.claim_for_consumer(
            event_id=event_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            now=now,
            lease_expires_at=now + timedelta(seconds=effective_lease_seconds),
        )
        if claimed is None:
            return {"event_id": event_id, "outcome": "not_claimed"}
        claimed_run_id = claimed.run_id
        claimed_task_id = claimed.task_id
        claimed_message = dict(claimed.message_json)
        if not await outbox.heartbeat_consumer(
            event_id=event_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            heartbeat_at=datetime.utcnow(),
            lease_expires_at=datetime.utcnow() + timedelta(seconds=effective_lease_seconds),
        ):
            return {"event_id": event_id, "outcome": "not_claimed", "error_class": "consumer_lease_lost"}
        try:
            async with db.begin_nested():
                message, result = await self._execute_message_with_db(
                    db,
                    claimed_message,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    lease_seconds=effective_lease_seconds,
                )
                if message["run_id"] != claimed_run_id or message["task_id"] != claimed_task_id:
                    raise ValueError("worker_outbox_message_identity_conflict")
        except (InvalidWorkerMessage, ProviderNotQualifiedError, ValueError) as exc:
            error_class = _safe_error_class(exc)
            retryable = _technical_conflict_retryable(error_class)
            result = {
                "execution_status": "technical_error" if retryable else "failed",
                "error_class": error_class,
                "retryable": retryable,
                "medical_verdict_produced": False,
            }

        if result.get("retryable") is True:
            error_class = _safe_error_class(result.get("error_class"))
            failed_at = datetime.utcnow()
            if claimed.consumer_attempt_count >= self.max_attempts:
                marked = await outbox.mark_consumer_dead_letter(
                    event_id=event_id,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    failed_at=failed_at,
                    error_class=error_class,
                )
                if not marked:
                    raise ValueError("worker_outbox_dead_letter_conflict")
                return {
                    **result,
                    "event_id": event_id,
                    "outcome": "dead_letter",
                    "error_class": error_class,
                }
            marked = await outbox.mark_consumer_retry(
                event_id=event_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                failed_at=failed_at,
                next_retry_at=failed_at + timedelta(seconds=self.retry_delay_seconds),
                error_class=error_class,
            )
            if not marked:
                raise ValueError("worker_outbox_retry_conflict")
            return {**result, "event_id": event_id, "outcome": "retry_scheduled", "error_class": error_class}

        if result.get("execution_status") == "failed":
            error_class = _safe_error_class(result.get("error_class"))
            marked = await outbox.mark_consumer_dead_letter(
                event_id=event_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                failed_at=datetime.utcnow(),
                error_class=error_class,
            )
            if not marked:
                raise ValueError("worker_outbox_dead_letter_conflict")
            return {**result, "event_id": event_id, "outcome": "dead_letter", "error_class": error_class}

        heartbeat_at = datetime.utcnow()
        if not await outbox.heartbeat_consumer(
            event_id=event_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            heartbeat_at=heartbeat_at,
            lease_expires_at=heartbeat_at + timedelta(seconds=effective_lease_seconds),
        ):
            raise ValueError("worker_consumer_lease_lost")
        marked = await outbox.mark_consumer_completed(
            event_id=event_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            finished_at=datetime.utcnow(),
        )
        if not marked:
            raise ValueError("worker_outbox_publish_conflict")
        return {
            **result,
            "event_id": event_id,
            "outcome": "completed",
            "publish_status": "published",
            "consumer_status": "completed",
        }


def _safe_error_class(value: Any) -> str:
    text = value.strip() if isinstance(value, str) else ""
    stable = {
        "provider_auth", "endpoint_timeout", "network_unreachable", "tls_failure",
        "model_invalid", "model_mismatch", "schema_invalid", "rate_limited",
        "provider_unavailable", "provider_receipt_missing", "provider_receipt_unsupported",
        "provider_output_contract",
        "provider_configuration_incomplete", "provider_disabled", "provider_not_qualified",
        "image_manifest_not_resolved", "technical_ai_request_failed", "technical_message_invalid",
        "technical_run_not_found", "technical_stage_not_enabled", "technical_run_not_validation_only",
        "technical_checkpoint_not_found", "technical_lease_invalid", "worker_error",
        "technical_snapshot_not_found", "image_resolver_not_configured",
        "technical_study_snapshot_not_found", "technical_study_not_ready",
        "technical_study_manifest_mismatch",
        "image_source_unavailable", "image_fetch_timeout", "image_source_forbidden",
        "image_source_fetcher_not_configured", "image_manifest_invalid",
        "image_content_invalid", "image_hash_mismatch", "image_asset_count_mismatch",
        "study_manifest_asset_mismatch", "study_asset_not_uploaded", "study_freeze_conflict",
        "study_freeze_manifest_invalid", "study_freeze_manifest_conflict",
        "study_manifest_hash_mismatch", "study_ordered_asset_ids_mismatch",
        "study_asset_source_index_mismatch", "study_asset_storage_binding_invalid",
        "object_store_not_configured", "object_store_upload_failed", "object_store_download_failed",
        "consumer_lease_lost", "worker_consumer_lease_lost",
    }
    if text in stable:
        return text
    if any(marker in text for marker in ("cas", "claim", "completion", "binding", "conflict")):
        return "cas_conflict"
    return "worker_error"


def _technical_conflict_retryable(error_class: str) -> bool:
    if error_class in {"image_source_unavailable", "image_fetch_timeout"}:
        return True
    return any(
        marker in error_class
        for marker in (
            "cas_conflict",
            "claim_conflict",
            "completion_conflict",
            "failure_conflict",
            "binding_or_cas_conflict",
        )
    )


__all__ = ["XRayTechnicalWorker"]
