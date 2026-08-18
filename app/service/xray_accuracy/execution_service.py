"""Validation-only execution trigger and safe technical result view.

The trigger is intentionally explicit and admin-scoped until a real Outbox
relay/Broker consumer is deployed.  It reuses the DB-backed worker entrypoint;
it does not contain a second execution implementation or any medical logic.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.xray_accuracy import (
    XRayModelCallDal,
    XRayOutboxDal,
    XRayRunDal,
    XRayStageCheckpointDal,
    XRayTraceEventDal,
)
from app.schemas.xray_accuracy import (
    XRayCheckpointResponse,
    XRayExecutionResponse,
    XRayCoverageEvidenceResponse,
    XRayModelCallResponse,
    XRayOutboxResponse,
    XRayRunResponse,
    XRayTraceResponse,
)
from workers.xray_accuracy_worker.technical_worker import XRayTechnicalWorker
from app.core.ai.qualification import safe_provider_receipt
from app.core.ai.qualification import (
    openai_compatible_endpoint_fingerprint,
    secret_fingerprint,
)
from app.service.ai_governance_service import AIGovernanceService
from app.core.ai.egress_proof import adapter_egress_proof_is_valid
from app.core.ai.contracts import ordered_image_identity_sha256
from app.core.config import settings

from .errors import RunNotFoundError


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _coverage_lineage_is_complete(
    coverage: dict[str, Any],
    *,
    expected_refs: list[str],
    resolved_refs: list[str],
    requested_refs: list[str],
    sent_refs: list[str],
) -> tuple[list[str], str]:
    """Validate the four-set lineage before a qualification artifact is built.

    Expected/resolved hashes may differ when a DICOM source is normalized to a
    provider-safe PNG.  They must nevertheless have one valid hash per source
    image, in the same ordered lineage as their corresponding reference set.
    """

    if not expected_refs or not (
        expected_refs == resolved_refs == requested_refs == sent_refs
    ):
        raise ValueError("qualification_coverage_not_full_sent")
    image_count = len(expected_refs)
    if (
        any(not isinstance(ref, str) or not ref.strip() for ref in expected_refs)
        or len(set(expected_refs)) != image_count
    ):
        raise ValueError("qualification_coverage_not_full_sent")
    hash_sets = (
        list(coverage.get("expected_image_sha256") or []),
        list(coverage.get("resolved_image_sha256") or []),
        list(coverage.get("requested_image_sha256") or []),
        list(coverage.get("sent_image_sha256") or []),
    )
    if any(
        len(values) != image_count or any(not _valid_sha256(value) for value in values)
        for values in hash_sets
    ):
        raise ValueError("qualification_image_hash_missing")
    ordered_sha = coverage.get("image_ordered_sha256")
    if not _valid_sha256(ordered_sha):
        raise ValueError("qualification_image_ordered_hash_mismatch")
    sent_hashes = hash_sets[-1]
    if ordered_image_identity_sha256(
        (index, digest) for index, digest in enumerate(sent_hashes)
    ) != ordered_sha:
        raise ValueError("qualification_image_ordered_hash_mismatch")
    return sent_hashes, ordered_sha


class XRayExecutionService:
    """Expose one controlled worker trigger and a tenant-scoped result view."""

    def __init__(
        self,
        db: AsyncSession,
        worker: XRayTechnicalWorker | None = None,
    ):
        self.run_dal = XRayRunDal(db)
        self.checkpoint_dal = XRayStageCheckpointDal(db)
        self.model_call_dal = XRayModelCallDal(db)
        self.trace_dal = XRayTraceEventDal(db)
        self.outbox_dal = XRayOutboxDal(db)
        self.worker = worker or XRayTechnicalWorker()

    @staticmethod
    def _run_response(run: Any) -> XRayRunResponse:
        return XRayRunResponse(
            run_id=run.id,
            session_id=run.session_id,
            study_id=run.study_id,
            requested_operation=run.requested_operation,
            request_id=run.request_id,
            contract_version=run.contract_version,
            release_fingerprint=run.release_fingerprint,
            execution_status=run.execution_status,
            ai_medical_status=run.ai_medical_status,
            delivery_status=run.delivery_status,
            engineering_eligibility=run.engineering_eligibility,
            state_version=run.state_version,
            validation_only=run.execution_mode == "validation_only",
            trace_ref=f"trace:{run.trace_namespace}",
        )

    async def execute_pending(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
    ) -> dict[str, Any]:
        """Execute the oldest pending validation-only Outbox event once.

        This is a qualification/control-plane entrypoint.  The future Broker
        consumer can call the same worker method without changing the state
        machine.
        """
        run = await self.run_dal.get_by_id(run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        rows = await self.outbox_dal.list_for_tenant_run(
            tenant_id=tenant_id,
            run_id=run_id,
            limit=100,
        )
        pending = next(
            (
                row
                for row in rows
                if (
                    row.publish_status == "pending"
                    or (
                        row.publish_status == "retry"
                        and (row.next_retry_at is None or row.next_retry_at <= datetime.utcnow())
                    )
                    or (
                        row.publish_status == "published"
                        and row.consumer_status in {"pending", "retry_wait"}
                    )
                )
                and row.event_type == "execute"
            ),
            None,
        )
        if pending is None:
            return {
                "run_id": run_id,
                "outcome": "not_pending",
                "execution_status": run.execution_status,
                "state_version": run.state_version,
                "medical_verdict_produced": False,
            }
        if run.execution_status in {"cancel_requested", "cancelled", "completed", "failed"}:
            return {
                "run_id": run_id,
                "outcome": "not_pending",
                "execution_status": run.execution_status,
                "state_version": run.state_version,
                "medical_verdict_produced": False,
            }
        marked = True
        if pending.publish_status in {"pending", "retry"}:
            marked = await self.outbox_dal.mark_manual_broker_published(
                event_id=pending.event_id,
                tenant_id=tenant_id,
                published_at=datetime.utcnow(),
            )
        if not marked:
            return {
                "run_id": run_id,
                "outcome": "not_claimed",
                "execution_status": run.execution_status,
                "state_version": run.state_version,
                "medical_verdict_produced": False,
            }
        safe_owner = f"api:{owner_id.strip()}"[:128]
        return await self.worker.execute_outbox_event(
            event_id=pending.event_id,
            tenant_id=tenant_id,
            owner_id=safe_owner,
            db=self.outbox_dal.db,
        )

    async def get_execution(
        self,
        *,
        tenant_id: str,
        run_id: str,
    ) -> XRayExecutionResponse:
        """Return only safe technical metadata for one tenant-scoped Run."""
        run = await self.run_dal.get_by_id(run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        checkpoints = await self.checkpoint_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        model_calls = await self.model_call_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        traces, _ = await self.trace_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id, page=1, limit=100
        )
        outbox = await self.outbox_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        input_tokens = sum(int(row.input_tokens or 0) for row in model_calls)
        output_tokens = sum(int(row.output_tokens or 0) for row in model_calls)
        return XRayExecutionResponse(
            run=self._run_response(run),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            checkpoints=[
                XRayCheckpointResponse(
                    checkpoint_id=row.id,
                    run_id=row.run_id,
                    stage_key=row.stage_key,
                    attempt_id=row.attempt_id,
                    status=row.status,
                    expected_version=row.expected_version,
                    input_hash=row.input_hash,
                    output_hash=row.output_hash,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    error_class=row.error_class,
                    late_flag="yes" if row.status == "late" else "no",
                )
                for row in checkpoints
            ],
            model_calls=[
                XRayModelCallResponse(
                    model_call_id=row.id,
                    run_id=row.run_id,
                    node_key=row.node_key,
                    attempt_id=row.attempt_id,
                    module_key=row.module_key,
                    provider_key=row.provider_key,
                    requested_model=row.requested_model,
                    actual_model=row.actual_model,
                    prompt_key=row.prompt_key,
                    prompt_version=row.prompt_version,
                    prompt_sha256=row.prompt_sha256,
                    rendered_sha256=row.rendered_sha256,
                    schema_key=row.schema_key,
                    schema_sha256=row.schema_sha256,
                    requested_language=row.requested_language,
                    actual_language=row.actual_language,
                    image_ordered_sha256=row.image_ordered_sha256,
                    coverage_evidence=(
                        XRayCoverageEvidenceResponse(
                            expected_source_image_refs=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("expected_source_image_refs", [])
                            ),
                            resolved_source_image_refs=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("resolved_source_image_refs", [])
                            ),
                            requested_source_image_refs=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("requested_source_image_refs", [])
                            ),
                            sent_source_image_refs=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("sent_source_image_refs", [])
                            ),
                            expected_image_sha256=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("expected_image_sha256", [])
                            ),
                            resolved_image_sha256=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("resolved_image_sha256", [])
                            ),
                            requested_image_sha256=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("requested_image_sha256", [])
                            ),
                            sent_image_sha256=list(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("sent_image_sha256", [])
                            ),
                            coverage_status=(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("coverage_status", "unknown")
                            ),
                            image_ordered_sha256=(
                                (row.receipt_json or {})
                                .get("coverage_evidence", {})
                                .get("image_ordered_sha256")
                            ),
                        )
                        if isinstance(
                            (row.receipt_json or {}).get("coverage_evidence"), dict
                        )
                        else None
                    ),
                    raw_output_sha256=row.raw_output_sha256,
                    parsed_output_sha256=row.parsed_output_sha256,
                    finish_reason=row.finish_reason,
                    input_tokens=row.input_tokens,
                    output_tokens=row.output_tokens,
                    latency_ms=row.latency_ms,
                    retry_index=row.retry_index,
                    fallback_used=row.fallback_used,
                    error_class=row.error_class,
                    created_at=row.created_at,
                )
                for row in model_calls
            ],
            traces=[
                XRayTraceResponse(
                    trace_id=row.id,
                    run_id=row.run_id,
                    stage_key=row.stage_key,
                    event_type=row.event_type,
                    state_version=row.state_version,
                    late_flag="yes" if "late" in row.event_type.casefold() else "no",
                    fingerprint=row.fingerprint,
                )
                for row in traces
            ],
            outbox=[
                XRayOutboxResponse(
                    event_id=row.event_id,
                    run_id=row.run_id,
                    task_id=row.task_id,
                    stage_key=row.stage_key,
                    event_type=row.event_type,
                    publish_status=row.publish_status,
                    consumer_status=row.consumer_status,
                    consumer_attempt_count=row.consumer_attempt_count,
                    consumer_next_retry_at=row.consumer_next_retry_at,
                    consumer_finished_at=row.consumer_finished_at,
                    consumer_last_error=row.consumer_last_error,
                    attempt_count=row.attempt_count,
                    next_retry_at=row.next_retry_at,
                    published_at=row.published_at,
                    last_error=row.last_error,
                )
                for row in outbox
            ],
        )

    async def get_qualification_evidence(
        self,
        *,
        tenant_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Return a secret-free, fail-closed evidence projection.

        Qualification artifacts are built from committed facts, never from a
        Provider response held by the command process.  This keeps the
        Session/Study/OSS/Run/Worker chain auditable and makes replay verify
        the same rows that a tenant-scoped execution query sees.
        """
        run = await self.run_dal.get_by_id(run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        checkpoints = await self.checkpoint_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        model_calls = await self.model_call_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        outbox_rows = await self.outbox_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        if run.execution_status != "completed" or run.engineering_eligibility != "clean":
            raise ValueError("qualification_run_not_completed")
        if run.ai_medical_status != "not_produced":
            raise ValueError("qualification_medical_status_invalid")
        if not any(
            row.status == "completed" and row.stage_key == "request_gate"
            for row in checkpoints
        ):
            raise ValueError("qualification_checkpoint_not_completed")
        if not any(
            row.publish_status == "published" and row.consumer_status == "completed"
            for row in outbox_rows
        ):
            raise ValueError("qualification_outbox_not_completed")
        successful_calls = [row for row in model_calls if row.error_class is None]
        if not successful_calls:
            raise ValueError("qualification_model_call_not_recorded")
        call = successful_calls[-1]
        receipt = call.receipt_json or {}
        coverage = receipt.get("coverage_evidence") or {}
        expected_refs = list(coverage.get("expected_source_image_refs") or [])
        resolved_refs = list(coverage.get("resolved_source_image_refs") or [])
        requested_refs = list(coverage.get("requested_source_image_refs") or [])
        sent_refs = list(coverage.get("sent_source_image_refs") or [])
        sent_hashes, ordered_sha = _coverage_lineage_is_complete(
            coverage,
            expected_refs=expected_refs,
            resolved_refs=resolved_refs,
            requested_refs=requested_refs,
            sent_refs=sent_refs,
        )
        safe_receipt = safe_provider_receipt(receipt)
        request_trace = receipt.get("request_trace") or {}
        connection_id = (
            request_trace.get("connection_id")
            if isinstance(request_trace, dict)
            else None
        )
        if (
            safe_receipt.get("status") != "confirmed"
            or safe_receipt.get("full_sent") != "confirmed"
            or safe_receipt.get("receipt_capability_version")
            != "provider-image-receipt.v1"
            or safe_receipt.get("receipt_signature_verified") is not True
        ):
            raise ValueError("qualification_receipt_invalid")
        image_receipts = safe_receipt.get("image_receipts")
        if (
            safe_receipt.get("actual_model") != call.actual_model
            or safe_receipt.get("image_count_received") != len(sent_hashes)
            or not isinstance(image_receipts, list)
            or len(image_receipts) != len(sent_hashes)
            or any(
                not isinstance(item, dict)
                or item.get("source_index") != index
                or item.get("status") != "confirmed"
                or item.get("sent_sha256") != digest
                for index, (item, digest) in enumerate(zip(image_receipts, sent_hashes))
            )
            or safe_receipt.get("image_ordered_sha256") != ordered_sha
        ):
            raise ValueError("qualification_receipt_invalid")
        return {
            "run_id": run.id,
            "session_id": run.session_id,
            "study_id": run.study_id,
            "trace_namespace": run.trace_namespace,
            "release_fingerprint": run.release_fingerprint,
            "model_call_id": call.id,
            "provider_key": call.provider_key,
            "connection_id": connection_id,
            "requested_model": call.requested_model,
            "actual_model": call.actual_model,
            "prompt_key": call.prompt_key,
            "prompt_version": call.prompt_version,
            "prompt_checksum": call.prompt_sha256,
            "rendered_sha256": call.rendered_sha256,
            "schema_key": call.schema_key,
            "schema_sha256": call.schema_sha256,
            "image_count": len(expected_refs),
            "expected_source_image_refs": expected_refs,
            "resolved_source_image_refs": resolved_refs,
            "requested_source_image_refs": requested_refs,
            "sent_source_image_refs": sent_refs,
            "expected_image_sha256": list(coverage.get("expected_image_sha256") or []),
            "resolved_image_sha256": list(coverage.get("resolved_image_sha256") or []),
            "requested_image_sha256": list(coverage.get("requested_image_sha256") or []),
            "sent_image_sha256": sent_hashes,
            "image_ordered_sha256": ordered_sha,
            "receipt": safe_receipt,
            "raw_output_sha256": call.raw_output_sha256,
            "parsed_output_sha256": call.parsed_output_sha256,
            "finish_reason": call.finish_reason,
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "latency_ms": call.latency_ms,
            "retry_index": call.retry_index,
            "fallback_used": call.fallback_used,
            "medical_verdict_produced": False,
        }

    async def get_transport_qualification_evidence(
        self,
        *,
        tenant_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Return committed G1-T evidence without asserting Provider receipt."""

        run = await self.run_dal.get_by_id(run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        checkpoints = await self.checkpoint_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        model_calls = await self.model_call_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        outbox_rows = await self.outbox_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id
        )
        if run.execution_status != "completed" or run.engineering_eligibility != "clean":
            raise ValueError("qualification_run_not_completed")
        if run.ai_medical_status != "not_produced":
            raise ValueError("qualification_medical_status_invalid")
        if not any(
            row.status == "completed" and row.stage_key == "request_gate"
            for row in checkpoints
        ):
            raise ValueError("qualification_checkpoint_not_completed")
        if not any(
            row.publish_status == "published" and row.consumer_status == "completed"
            for row in outbox_rows
        ):
            raise ValueError("qualification_outbox_not_completed")
        successful_calls = [row for row in model_calls if row.error_class is None]
        if not successful_calls:
            raise ValueError("qualification_model_call_not_recorded")
        call = successful_calls[-1]
        receipt = call.receipt_json or {}
        coverage = receipt.get("coverage_evidence") or {}
        expected_refs = list(coverage.get("expected_source_image_refs") or [])
        resolved_refs = list(coverage.get("resolved_source_image_refs") or [])
        requested_refs = list(coverage.get("requested_source_image_refs") or [])
        sent_refs = list(coverage.get("sent_source_image_refs") or [])
        sent_hashes, ordered_sha = _coverage_lineage_is_complete(
            coverage,
            expected_refs=expected_refs,
            resolved_refs=resolved_refs,
            requested_refs=requested_refs,
            sent_refs=sent_refs,
        )
        safe_receipt = safe_provider_receipt(receipt)
        proof = safe_receipt.get("adapter_egress_proof")
        manifest = [
            {"source_index": index, "sent_sha256": digest}
            for index, digest in enumerate(sent_hashes)
        ]
        request_trace = receipt.get("request_trace") or {}
        connection_id = (
            request_trace.get("connection_id")
            if isinstance(request_trace, dict)
            else None
        )
        expected_key_fingerprint = None
        expected_endpoint = None
        if isinstance(connection_id, str) and settings.AI_CONFIG_VERSION.strip():
            bundle = await AIGovernanceService(self.run_dal.db).resolve(
                version=settings.AI_CONFIG_VERSION,
                language="en",
            )
            connection = next(
                (item for item in bundle.connection_entries if item.connection_id == connection_id),
                None,
            )
            if connection is not None:
                expected_key_fingerprint = secret_fingerprint(connection.api_key)
                expected_endpoint = connection.base_url
        if expected_endpoint is None:
            raise ValueError("qualification_connection_not_in_pool")
        if (
            coverage.get("coverage_status") != "egress_proven"
            and safe_receipt.get("status") != "confirmed"
        ):
            raise ValueError("qualification_egress_not_proven")
        if not adapter_egress_proof_is_valid(
            proof,
            signing_key=settings.AI_EGRESS_PROOF_SIGNING_KEY,
            expected_transport_status="qualified",
            expected_endpoint_sha256=openai_compatible_endpoint_fingerprint(expected_endpoint or ""),
            expected_model=call.requested_model,
            expected_key_fingerprint=expected_key_fingerprint,
            expected_prompt_sha256=call.prompt_sha256,
            expected_rendered_sha256=call.rendered_sha256,
            expected_schema_sha256=call.schema_sha256,
            expected_image_ordered_sha256=ordered_sha,
            expected_images=manifest,
        ):
            raise ValueError("qualification_egress_proof_invalid")
        if expected_key_fingerprint is None:
            raise ValueError("qualification_egress_key_binding_invalid")
        if proof.get("key_fingerprint") != expected_key_fingerprint:
            raise ValueError("qualification_egress_key_binding_invalid")
        return {
            "run_id": run.id,
            "session_id": run.session_id,
            "study_id": run.study_id,
            "trace_namespace": run.trace_namespace,
            "release_fingerprint": run.release_fingerprint,
            "model_call_id": call.id,
            "provider_key": call.provider_key,
            "connection_id": connection_id,
            "requested_model": call.requested_model,
            "actual_model": call.actual_model,
            "prompt_key": call.prompt_key,
            "prompt_version": call.prompt_version,
            "prompt_checksum": call.prompt_sha256,
            "rendered_sha256": call.rendered_sha256,
            "schema_key": call.schema_key,
            "schema_sha256": call.schema_sha256,
            "image_count": len(sent_hashes),
            "image_manifest": manifest,
            "image_ordered_sha256": ordered_sha,
            "expected_image_sha256": list(coverage.get("expected_image_sha256") or []),
            "sent_image_sha256": sent_hashes,
            "adapter_egress_proof": proof,
            "receipt_status": safe_receipt.get("status"),
            "raw_output_sha256": call.raw_output_sha256,
            "parsed_output_sha256": call.parsed_output_sha256,
            "finish_reason": call.finish_reason,
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "latency_ms": call.latency_ms,
            "retry_index": call.retry_index,
            "fallback_used": call.fallback_used,
            "medical_verdict_produced": False,
        }


__all__ = ["XRayExecutionService"]
