"""Controlled end-to-end real Provider qualification.

The qualification command is deliberately not an HTTP endpoint.  It creates
an isolated Session/Study, lets the normal preparation Worker fetch and upload
the approved fixtures, then creates a diagnosis Run and invokes the same
DB-backed Worker/Provider boundary.  The first request is allowed to bypass
the *already-qualified* artifact gate only for the exact in-memory Run ID
created by this command; ordinary diagnosis requests never receive that
capability.

The resulting artifact is built from committed ModelCall/Checkpoint/Outbox
facts, not from a response retained by this process.  It never writes a
medical verdict and it refuses to run against the default ``ms_image`` DB.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from app.core.ai.connection_pool import AIConnectionPool
from app.core.ai.contracts import (
    AIRequestPolicy,
    ProviderNotQualifiedError,
    ProviderRequestError,
    sha256_bytes,
)
from app.core.ai.qualification import (
    openai_compatible_endpoint_fingerprint,
    secret_fingerprint,
    write_qualification_artifact,
)
from app.core.async_db import session_factory
from app.core.config import settings
from app.core.imaging import (
    ApprovedManifestSourceImageFetcher,
    OSSObjectStore,
    ObjectStoreError,
    XRayOSSImageResolver,
    inspect_image_bytes,
)
from app.schemas.xray_accuracy import (
    XRayRunCreate,
    XRaySessionCreate,
    XRayStudyPreparationCreate,
    XRayStudyImageCreate,
)
from app.service.xray_accuracy.ai_request_service import XRayAIRequestService
from app.service.xray_accuracy.execution_service import XRayExecutionService
from app.service.xray_accuracy.lifecycle_service import XRayLifecycleService
from app.service.xray_accuracy.technical_executor import TechnicalExecutor
from app.service.ai_governance_service import AIGovernanceService, GovernedConnection
from app.service.xray_accuracy.providers import governed_provider_pool
from workers.xray_accuracy_worker.technical_worker import XRayTechnicalWorker


@dataclass(frozen=True)
class _ApprovedSource:
    source_index: int
    source_image_ref: str
    mime_type: str
    pixel_width: int
    pixel_height: int
    content_sha256: str


def _artifact_base(
    *, status: str, reason: str, retryable: bool,
    connection: GovernedConnection | None = None,
) -> dict[str, Any]:
    return {
        "schema": "ai-provider-transport-qualification.v1",
        "status": status,
        "reason": reason,
        "retryable": retryable,
        "medical_verdict_produced": False,
        "provider": {
            "kind": "openai_compatible",
            "endpoint_sha256": (
                openai_compatible_endpoint_fingerprint(connection.base_url)
                if connection else None
            ),
            "model": connection.model if connection else None,
            "key_fingerprint": secret_fingerprint(connection.api_key) if connection else None,
        },
    }


def _write_result(result: dict[str, Any]) -> dict[str, Any]:
    write_qualification_artifact(
        settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
        result,
        signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
    )
    return result


def _blocked(reason: str, *, retryable: bool = False) -> dict[str, Any]:
    return _write_result(_artifact_base(status="blocked", reason=reason, retryable=retryable))


def _image_reason(error: BaseException) -> str:
    reason = str(error).strip()
    allowed = {
        "image_source_manifest_not_configured",
        "image_source_manifest_invalid",
        "image_source_forbidden",
        "image_source_unavailable",
        "image_hash_mismatch",
        "image_content_invalid",
        "image_content_too_large",
        "image_dimensions_invalid",
    }
    return reason if reason in allowed else "qualification_image_invalid"


async def _transaction(
    operation: Callable[[Any], Awaitable[Any]],
) -> Any:
    async with session_factory() as db:
        async with db.begin():
            return await operation(db)


async def _load_approved_images(
    *,
    fetcher: ApprovedManifestSourceImageFetcher,
    tenant_id: str,
) -> tuple[_ApprovedSource, ...]:
    refs = fetcher.approved_refs(tenant_id=tenant_id)
    images: list[_ApprovedSource] = []
    for source_index, source_ref in enumerate(refs):
        content = await fetcher.fetch(
            tenant_id=tenant_id,
            source_image_ref=source_ref,
        )
        inspection = inspect_image_bytes(content)
        images.append(
            _ApprovedSource(
                source_index=source_index,
                source_image_ref=source_ref,
                mime_type=inspection.mime_type,
                pixel_width=inspection.pixel_width,
                pixel_height=inspection.pixel_height,
                content_sha256=sha256_bytes(content),
            )
        )
    return tuple(images)


async def _execute_pending_until_terminal(
    *,
    worker: XRayTechnicalWorker,
    run_id: str,
    tenant_id: str,
    owner_id: str,
) -> dict[str, Any]:
    """Drive the same DB worker without pretending this is live RabbitMQ."""
    # The worker owns retry/DLQ state.  This loop merely waits for its due
    # retry time; it does not create a second task or mutate a status directly.
    max_polls = max(4, settings.XRAY_WORKER_MAX_ATTEMPTS * 3)
    last: dict[str, Any] = {"outcome": "not_pending"}
    for _ in range(max_polls):
        async with session_factory() as db:
            async with db.begin():
                last = await XRayExecutionService(
                    db, worker=worker
                ).execute_pending(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    owner_id=owner_id,
                )
        if last.get("outcome") in {"completed", "dead_letter"}:
            return last
        if last.get("outcome") == "not_pending":
            # ``not_pending`` may mean retry_wait; inspect the committed run
            # before deciding whether to sleep or finish.
            async with session_factory() as db:
                async with db.begin():
                    run = await XRayLifecycleService(db).run_service.run_dal.get_by_id(
                        run_id, tenant_id
                    )
                    execution_status = run.execution_status if run is not None else None
            if execution_status in {"completed", "failed", "cancelled"}:
                return last
        await asyncio.sleep(1.1)
    return last


async def _qualify_unlocked() -> dict[str, object]:
    """Run the controlled Session→Study→OSS→Run→Worker→Provider gate."""
    if not settings.AI_CONFIG_VERSION.strip():
        return _blocked("ai_config_version_missing")
    if not settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY:
        return _blocked("qualification_artifact_signing_key_missing")
    if not settings.AI_EGRESS_PROOF_SIGNING_KEY:
        return _blocked("egress_proof_signing_key_missing")
    database_name = settings.MYSQL_DB.casefold().strip()
    if database_name in {"ms_image", "ms-image"} or not any(
        marker in database_name for marker in ("test", "qual", "sandbox")
    ):
        return _blocked("qualification_database_not_isolated")
    if not settings.AI_SOURCE_IMAGE_MANIFEST_PATH or not settings.AI_SOURCE_IMAGE_ROOT:
        return _blocked("image_source_manifest_not_configured")

    try:
        fetcher = ApprovedManifestSourceImageFetcher(
            manifest_path=settings.AI_SOURCE_IMAGE_MANIFEST_PATH,
            root_dir=settings.AI_SOURCE_IMAGE_ROOT,
        )
        tenant_id = settings.AI_QUALIFICATION_TENANT_ID.strip()
        subject_id = settings.AI_QUALIFICATION_SUBJECT_ID.strip()
        images = await _load_approved_images(fetcher=fetcher, tenant_id=tenant_id)
        if len(images) < 2:
            return _blocked("qualification_requires_multiple_images")
        object_store = OSSObjectStore()
        async with session_factory() as governance_db:
            async with governance_db.begin():
                bundle = await AIGovernanceService(governance_db).resolve(
                    version=settings.AI_CONFIG_VERSION,
                    language="en",
                )
        connections, providers, key_fingerprints = governed_provider_pool(
            bundle.connection_entries
        )
        first_provider = providers[connections[0].connection_id]
        first_connection = bundle.connection_entries[0]
    except (ObjectStoreError, ValueError) as exc:
        return _blocked(_image_reason(exc) if "image" in str(exc) else "provider_configuration_incomplete")

    invocation = uuid4().hex
    session_id: str | None = None
    study_revision_id: str | None = None
    preparation_run_id: str | None = None
    diagnosis_run_id: str | None = None
    phase = "session_create"
    try:
        context = {"tenant_id": tenant_id, "subject": subject_id}
        session_result = await _transaction(
            lambda db: XRayLifecycleService(db).create_session(
                context=context,
                payload=XRaySessionCreate(
                    request_id=f"qualification-session:{invocation}",
                    case_request_id=None,
                    module_key="xray-provider-qualification",
                    metadata={"qualification": True},
                ),
            )
        )
        session_id = session_result["session_id"]
        phase = "study_preparation_create"
        preparation_result = await _transaction(
            lambda db: XRayLifecycleService(db).create_study_preparation(
                context=context,
                payload=XRayStudyPreparationCreate(
                    request_id=f"qualification-study:{invocation}",
                    session_id=session_id,
                    study_id=f"qualification-study:{invocation}",
                    images=[
                        XRayStudyImageCreate(
                            source_index=image.source_index,
                            source_image_ref=image.source_image_ref,
                            mime_type=image.mime_type,
                        )
                        for image in images
                    ],
                    species=None,
                    body_scope="qualification",
                ),
            )
        )
        study = preparation_result["study"]
        study_revision_id = study["study_revision_id"]
        preparation_run_id = preparation_result["run"].run_id

        phase = "study_preparation_execute"
        preparation_worker = XRayTechnicalWorker(
            session_factory_=session_factory,
            object_store=object_store,
            source_image_fetcher=fetcher,
            retry_delay_seconds=1,
            max_attempts=settings.XRAY_WORKER_MAX_ATTEMPTS,
        )
        preparation_result = await _execute_pending_until_terminal(
            worker=preparation_worker,
            run_id=preparation_run_id,
            tenant_id=tenant_id,
            owner_id=f"qualification-preparation:{invocation}",
        )
        if preparation_result.get("execution_status") != "completed":
            return _blocked(
                str(preparation_result.get("error_class") or "study_preparation_failed"),
                retryable=bool(preparation_result.get("retryable")),
            )

        # The assets returned by the preparation response are stable opaque
        # IDs; no source path or signed URL crosses this boundary.
        phase = "study_readback"
        async with session_factory() as db:
            async with db.begin():
                prepared = await XRayLifecycleService(db).get_study(
                    tenant_id=tenant_id,
                    subject_id=subject_id,
                    study_revision_id=study_revision_id,
                )
        expected_manifest = [
            {
                "source_index": asset["source_index"],
                "source_image_ref": asset["asset_id"],
            }
            for asset in prepared["assets"]
        ]
        phase = "diagnosis_run_create"
        diagnosis_result = await _transaction(
            lambda db: XRayLifecycleService(db).run_service.create_run(
                context=context,
                payload=XRayRunCreate(
                    request_id=f"qualification-diagnose:{invocation}",
                    session_id=session_id,
                    study_id=prepared["study"]["study_id"],
                    requested_operation="diagnose",
                    contract_version="xray-provider-qualification.v1",
                    study_revision=study_revision_id,
                    expected_manifest=expected_manifest,
                    validation_only=True,
                ),
            )
        )
        diagnosis_run_id = diagnosis_result.run_id
        phase = "provider_worker_build"
        pool = AIConnectionPool(
            connections=connections,
            provider_factory=lambda config: providers[config.connection_id],
            policy=AIRequestPolicy(
                # Qualification must be able to exhaust the explicitly
                # configured lane set.  A low global default otherwise makes
                # a healthy later lane unreachable when earlier credentials
                # have expired.  Ordinary runtime requests keep their own
                # separately bounded policy.
                max_attempts=max(
                    1,
                    min(
                        len(connections),
                        settings.AI_QUALIFICATION_MAX_ATTEMPTS,
                    ),
                ),
                hard_timeout_seconds=bundle.connection_entries[0].timeout_seconds,
                grace_timeout_seconds=2.0,
                backoff_base_seconds=0.25,
                max_backoff_seconds=4.0,
                concurrency=1,
            ),
            allow_network=True,
        )

        def diagnosis_executor(db: Any) -> TechnicalExecutor:
            ai_service = XRayAIRequestService(
                db,
                provider=first_provider,
                pool=pool,
                config_version=settings.AI_CONFIG_VERSION,
                # This capability is held only by this in-process command and
                # is bound to this exact committed Run ID.
                qualification_run_id=diagnosis_run_id,
            )
            resolver = XRayOSSImageResolver(
                session_factory=session_factory,
                object_store=object_store,
            )
            return TechnicalExecutor(
                db,
                image_resolver=resolver,
                object_store=object_store,
                ai_service=ai_service,
            )

        diagnosis_worker = XRayTechnicalWorker(
            session_factory_=session_factory,
            executor_factory=diagnosis_executor,
            retry_delay_seconds=1,
            max_attempts=settings.XRAY_WORKER_MAX_ATTEMPTS,
        )
        phase = "provider_worker_execute"
        diagnosis_result = await _execute_pending_until_terminal(
            worker=diagnosis_worker,
            run_id=diagnosis_run_id,
            tenant_id=tenant_id,
            owner_id=f"qualification-diagnosis:{invocation}",
        )
        if diagnosis_result.get("execution_status") != "completed":
            return _blocked(
                str(diagnosis_result.get("error_class") or "provider_request_failed"),
                retryable=bool(diagnosis_result.get("retryable")),
            )

        phase = "qualification_evidence_readback"
        async with session_factory() as db:
            async with db.begin():
                evidence = await XRayExecutionService(
                    db
                ).get_transport_qualification_evidence(
                    tenant_id=tenant_id,
                    run_id=diagnosis_run_id,
                )
        if evidence["expected_image_sha256"] != [
            image.content_sha256 for image in images
        ]:
            return _blocked("qualification_source_hash_mismatch")
        sent_hashes = evidence["sent_image_sha256"]
        image_manifest = evidence["image_manifest"]
        connection_id = evidence.get("connection_id")
        key_fingerprint = key_fingerprints.get(connection_id)
        if not key_fingerprint:
            return _blocked("qualification_connection_not_in_pool")
        phase = "artifact_build"
        selected_connection = next(
            (entry for entry in bundle.connection_entries if entry.connection_id == connection_id),
            first_connection,
        )
        result = _artifact_base(
            status="qualified", reason="qualified", retryable=False,
            connection=selected_connection,
        )
        result.update(
            {
                "transport_status": "qualified",
                "receipt_status": (
                    "qualified"
                    if evidence["receipt_status"] == "confirmed"
                    else "unsupported"
                ),
                "coverage_status": "egress_proven",
                "run_id": diagnosis_run_id,
                "trace_namespace": evidence["trace_namespace"],
                "provider": {
                    **result["provider"],
                    "key_fingerprint": key_fingerprint,
                    "provider_key": evidence["provider_key"],
                    "actual_model": evidence["actual_model"],
                    "provider_request_id_sha256": evidence[
                        "adapter_egress_proof"
                    ].get("provider_request_id_sha256"),
                },
                "prompt": {
                    "prompt_key": evidence["prompt_key"],
                    "prompt_version": evidence["prompt_version"],
                    "prompt_checksum": evidence["prompt_checksum"],
                    "rendered_sha256": evidence["rendered_sha256"],
                    "schema_key": evidence["schema_key"],
                    "schema_sha256": evidence["schema_sha256"],
                },
                "images": {
                    "count": evidence["image_count"],
                    "ordered_sha256": evidence["image_ordered_sha256"],
                    "manifest": image_manifest,
                },
                "adapter_egress_proof": evidence["adapter_egress_proof"],
                "model_call": {
                    "raw_output_sha256": evidence["raw_output_sha256"],
                    "parsed_output_sha256": evidence["parsed_output_sha256"],
                    "finish_reason": evidence["finish_reason"],
                    "latency_ms": evidence["latency_ms"],
                    "input_tokens": evidence["input_tokens"],
                    "output_tokens": evidence["output_tokens"],
                    "medical_verdict_produced": False,
                },
                "chain": {
                    "session_id": session_id,
                    "study_id": evidence["study_id"],
                    "study_revision_id": study_revision_id,
                    "preparation_run_id": preparation_run_id,
                    "diagnosis_run_id": diagnosis_run_id,
                    "object_store": "isolated_oss_object_key",
                    "worker_mode": "db_worker_manual",
                    "broker_status": "live_required_before_phase_gate"
                    if not settings.BROKER_ENABLED
                    else "enabled",
                    "medical_verdict_produced": False,
                },
                "coverage": {
                    "expected_image_sha256": evidence["expected_image_sha256"],
                    "egress_sent_image_sha256": evidence["sent_image_sha256"],
                },
                "qualification_fingerprint": hashlib.sha256(
                    json.dumps(
                        {
                            "provider": result["provider"],
                            "prompt_checksum": evidence["prompt_checksum"],
                            "schema_sha256": evidence["schema_sha256"],
                            "image_ordered_sha256": evidence[
                                "image_ordered_sha256"
                            ],
                            "proof_signature": evidence[
                                "adapter_egress_proof"
                            ]["proof_signature"]["value"],
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "qualified_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        # G1-T never upgrades the strict Provider receipt gate. Persist an
        # explicit blocked G1-R artifact when the Provider declares no receipt
        # capability, so operators cannot mistake a transport success for
        # full_sent confirmation.
        if evidence["receipt_status"] != "confirmed":
            write_qualification_artifact(
                settings.AI_QUALIFICATION_ARTIFACT_PATH,
                {
                    "schema": "ai-provider-qualification.v1",
                    "status": "blocked",
                    "reason": "provider_receipt_unsupported",
                    "retryable": False,
                    "transport_status": "qualified",
                    "receipt_status": "unsupported",
                    "coverage_status": "egress_proven",
                    "medical_verdict_produced": False,
                    "transport_artifact_ref": settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
                },
                signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
            )
        return _write_result(result)
    except ProviderRequestError as exc:
        return _blocked(exc.error_class, retryable=exc.retryable)
    except ProviderNotQualifiedError as exc:
        return _blocked(str(exc) or "provider_not_qualified")
    except Exception as exc:  # noqa: BLE001 - stable, secret-free artifact
        reason = str(exc).strip()
        stable = {
            "qualification_database_not_isolated",
            "qualification_run_not_completed",
            "qualification_medical_status_invalid",
            "qualification_checkpoint_not_completed",
            "qualification_outbox_not_completed",
            "qualification_model_call_not_recorded",
            "qualification_coverage_not_full_sent",
            "qualification_image_hash_missing",
            "qualification_image_ordered_hash_mismatch",
            "qualification_receipt_invalid",
            "qualification_source_hash_mismatch",
            "study_preparation_failed",
            "provider_request_failed",
        }
        result = _artifact_base(
            status="blocked",
            reason=reason if reason in stable else "qualification_chain_failed",
            retryable=False,
        )
        result["phase"] = phase
        return _write_result(result)


async def qualify() -> dict[str, object]:
    """Serialize API/CLI qualification attempts within the shared runtime."""
    lock_path = f"{settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH}.lock"
    lock_target = Path(lock_path)
    lock_target.parent.mkdir(parents=True, exist_ok=True)
    with lock_target.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _blocked("provider_qualification_already_running", retryable=True)
        try:
            return await _qualify_unlocked()
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = asyncio.run(qualify())
    # Keep command output safe for CI/operator logs.  The full bounded
    # artifact is written to the configured artifact path; stdout must not
    # become a second channel for source refs, image hashes or provider
    # metadata that callers may treat as sensitive.
    print(
        json.dumps(
            {
                "schema": result.get("schema"),
                "status": result.get("status"),
                "reason": result.get("reason"),
                "retryable": result.get("retryable"),
                "medical_verdict_produced": result.get("medical_verdict_produced"),
                "phase": result.get("phase"),
                "artifact_path": settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    if result.get("status") != "qualified":
        raise SystemExit(2)


__all__ = ["qualify"]
