"""Zero-model Run application service.

This service only creates and advances technical state.  It has no Provider,
Prompt, truth, scorer, or medical verdict logic.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.xray_accuracy import (
    XRayOutboxDal,
    XRayRequestSnapshotDal,
    XRayRunDal,
    XRayStageCheckpointDal,
    XRayTraceEventDal,
    XRaySessionDal,
    XRayStudySnapshotDal,
)
from app.core.config import settings
from app.schemas.xray_accuracy import XRayCancelRequest, XRayRunCreate, XRayRunResponse

from .errors import (
    CASConflictError,
    IdempotencyConflictError,
    InputContractError,
    LeakageInputError,
    QualificationAccessError,
    RunNotFoundError,
)


FORBIDDEN_INPUT_KEYS = {
    "abn",
    "nor",
    "disease_code",
    "filename",
    "file_name",
    "path",
    "history",
    "historical_output",
    "truth",
    "annotation",
    "ocr",
    "exif",
    "failure_bank",
    "score",
    "scorer",
    "diagnosis",
    "previous_output",
    "url",
    "signed_url",
    "image_url",
    "original_image",
    "authorization",
    "token",
    "secret",
}


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_expected_manifest_sha256(manifest: list[dict[str, Any]]) -> str:
    """Hash only immutable source index/ref identity, not optional hints."""
    return _sha256_json(
        [
            {
                "source_index": int(item["source_index"]),
                "source_image_ref": str(item["source_image_ref"]),
            }
            for item in manifest
        ]
    )


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in FORBIDDEN_INPUT_KEYS:
                paths.append(f"{path}.{key_text}")
            paths.extend(_find_forbidden_keys(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return paths


_SENSITIVE_VALUE_MARKERS = (
    "://",
    "bearer ",
    "authorization:",
    "signed_url",
    "signedurl",
    "token=",
    "secret=",
    "api_key",
    "-----begin ",
)


def _validate_safe_metadata(value: Any, path: str = "$.safe_metadata", depth: int = 0) -> None:
    """Fail closed when supposedly safe metadata contains credential/URL values."""
    if depth > 4:
        raise InputContractError("safe_metadata_nesting_too_deep")
    if isinstance(value, dict):
        if len(value) > 32:
            raise InputContractError("safe_metadata_too_many_fields")
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in FORBIDDEN_INPUT_KEYS:
                raise LeakageInputError([f"{path}.{key_text}"])
            _validate_safe_metadata(child, f"{path}.{key_text}", depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 64:
            raise InputContractError("safe_metadata_list_too_large")
        for index, child in enumerate(value):
            _validate_safe_metadata(child, f"{path}[{index}]", depth + 1)
        return
    if isinstance(value, str):
        if len(value) > 256:
            raise InputContractError("safe_metadata_string_too_large")
        lowered = value.casefold()
        if any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS):
            raise LeakageInputError([path])
        if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            raise InputContractError("safe_metadata_control_character")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise InputContractError("safe_metadata_value_type_invalid")


class XRayRunService:
    def __init__(self, db: AsyncSession):
        self.run_dal = XRayRunDal(db)
        self.snapshot_dal = XRayRequestSnapshotDal(db)
        self.checkpoint_dal = XRayStageCheckpointDal(db)
        self.trace_dal = XRayTraceEventDal(db)
        self.outbox_dal = XRayOutboxDal(db)
        self.session_dal = XRaySessionDal(db)
        self.study_dal = XRayStudySnapshotDal(db)

    @staticmethod
    def _response(run) -> XRayRunResponse:
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

    @staticmethod
    def _validate_payload(payload: XRayRunCreate) -> dict[str, Any]:
        data = payload.model_dump(mode="json")
        forbidden = _find_forbidden_keys(data)
        if forbidden:
            raise LeakageInputError(forbidden)
        if data.get("safe_metadata") is not None:
            _validate_safe_metadata(data["safe_metadata"])
        if len(json.dumps(data, ensure_ascii=False)) > 256 * 1024:
            raise InputContractError("request_too_large")
        if data.get("requested_operation") not in {"prepare_study", "diagnose", "qualification"}:
            raise InputContractError("requested_operation_invalid")
        if data.get("requested_operation") == "qualification":
            raise QualificationAccessError("qualification_controlled_only")
        if (
            settings.AI_REQUIRE_FROZEN_STUDY
            and data["requested_operation"] == "diagnose"
            and not data.get("study_id")
        ):
            raise InputContractError("diagnosis_study_required")
        indices = [item["source_index"] for item in data["expected_manifest"]]
        if len(indices) != len(set(indices)):
            raise InputContractError("manifest_duplicate_source_index")
        if indices != list(range(len(indices))):
            raise InputContractError("manifest_source_index_not_contiguous")
        for image in data["expected_manifest"]:
            ref = image["source_image_ref"]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}", ref):
                raise InputContractError("image_ref_must_be_opaque")
        return data

    async def create_run(self, *, context: dict[str, Any], payload: XRayRunCreate) -> XRayRunResponse:
        data = self._validate_payload(payload)
        tenant_id = context["tenant_id"]
        subject_id = context["subject"]
        # A diagnosis request is never valid without a frozen Study.  The
        # former feature flag made it possible for a misconfigured deployment
        # to bypass the storage/manifest gate and send caller-controlled
        # images directly to a Provider.
        if data["requested_operation"] == "diagnose":
            if not data.get("session_id") or not data.get("study_id"):
                raise InputContractError("diagnosis_session_and_study_required")
            session = await self.session_dal.get_by_id(
                tenant_id=tenant_id, session_id=data["session_id"]
            )
            if session is None or session.session_status != "open":
                raise InputContractError("diagnosis_session_not_open")
            study = await self.study_dal.get_by_revision(
                tenant_id=tenant_id, study_revision_id=data["study_revision"]
            )
            if (
                study is None
                or study.session_id != data["session_id"]
                or study.study_id != data["study_id"]
            ):
                raise InputContractError("diagnosis_study_binding_invalid")
            if study.study_status != "ready_full_study" or study.frozen_at is None:
                raise InputContractError("diagnosis_study_not_ready")
            manifest_ids = [item["source_image_ref"] for item in data["expected_manifest"]]
            if manifest_ids != study.ordered_source_image_ids_json:
                raise InputContractError("diagnosis_manifest_not_frozen_study")
            manifest_sha256 = _canonical_expected_manifest_sha256(
                data["expected_manifest"]
            )
            if manifest_sha256 != study.expected_manifest_sha256:
                raise InputContractError("diagnosis_manifest_hash_mismatch")
        payload_sha256 = _sha256_json(data)
        existing = await self.run_dal.get_by_request(
            tenant_id=tenant_id,
            request_id=data["request_id"],
            contract_version=data["contract_version"],
        )
        if existing:
            if existing.payload_sha256 != payload_sha256:
                raise IdempotencyConflictError("idempotency_conflict")
            return self._response(existing)

        run_id = uuid4().hex
        task_id = uuid4().hex
        trace_namespace = f"xray.v2:{run_id}"
        release_fingerprint = _sha256_json(
            {"contract_version": data["contract_version"], "validation_only": True}
        )[:32]
        now = datetime.utcnow()
        run_values = {
            "id": run_id,
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "session_id": data.get("session_id"),
            "study_id": data.get("study_id"),
            "request_id": data["request_id"],
            "case_request_id": data.get("case_request_id"),
            "requested_operation": data["requested_operation"],
            "contract_version": data["contract_version"],
            "payload_sha256": payload_sha256,
            "release_fingerprint": release_fingerprint,
            "trace_namespace": trace_namespace,
            "state_version": 0,
            "execution_status": "queued",
            "ai_medical_status": "not_produced",
            "delivery_status": "not_published",
            "engineering_eligibility": "unknown",
            "execution_mode": "validation_only",
        }
        created_run = await self.run_dal.create_idempotent(run_values)
        if created_run is None:
            existing = await self.run_dal.get_by_request(
                tenant_id=tenant_id,
                request_id=data["request_id"],
                contract_version=data["contract_version"],
            )
            if existing is None:
                raise IdempotencyConflictError("idempotency_race")
            if existing.payload_sha256 != payload_sha256:
                raise IdempotencyConflictError("idempotency_conflict")
            return self._response(existing)
        await self.snapshot_dal.create_snapshot(
            {
                "id": uuid4().hex,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "session_id": data.get("session_id"),
                "study_id": data.get("study_id"),
                "requested_operation": data["requested_operation"],
                "study_revision": data["study_revision"],
                "manifest_json": data["expected_manifest"],
                "safe_metadata_json": data.get("safe_metadata"),
                "immutable_at": now,
            }
        )
        await self.checkpoint_dal.create_checkpoint(
            {
                "id": uuid4().hex,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "stage_key": "request_gate",
                # The checkpoint id is the logical task carried by the
                # committed Outbox message.  Each Provider physical retry is
                # independently identified in ModelCall/receipt metadata.
                "attempt_id": task_id,
                "status": "queued",
                "expected_version": 0,
            }
        )
        await self.trace_dal.create_event(
            {
                "id": uuid4().hex,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "trace_namespace": trace_namespace,
                "stage_key": "request_gate",
                "event_type": "run_accepted",
                "event_payload_json": {"validation_only": True},
                "fingerprint": release_fingerprint,
                "state_version": 0,
            }
        )
        event_id = uuid4().hex
        message = {
            "run_id": run_id,
            "task_id": task_id,
            "stage_key": "request_gate",
            "release_fingerprint": release_fingerprint,
            "expected_version": 0,
            "trace_namespace": trace_namespace,
        }
        await self.outbox_dal.create_event(
            {
                "id": event_id,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "task_id": task_id,
                "stage_key": "request_gate",
                "event_type": "execute",
                "release_fingerprint": release_fingerprint,
                "expected_version": 0,
                "trace_namespace": trace_namespace,
                "message_json": message,
                "message_payload_hash": _sha256_json(message),
                "message_whitelist_version": "xray-message.v1",
                "publish_status": "pending",
                "attempt_count": 0,
            }
        )
        created = await self.run_dal.get_by_id(run_id, tenant_id)
        if created is None:
            raise InputContractError("run_create_not_visible")
        return self._response(created)

    async def get_run(self, *, tenant_id: str, run_id: str):
        run = await self.run_dal.get_by_id(run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        return self._response(run)

    async def list_runs(self, *, tenant_id: str, page: int, limit: int):
        rows, count = await self.run_dal.list_for_tenant(
            tenant_id=tenant_id, page=page, limit=limit
        )
        return [self._response(row) for row in rows], count

    async def cancel_run(self, *, tenant_id: str, request: XRayCancelRequest):
        run = await self.run_dal.get_by_id(request.run_id, tenant_id)
        if run is None:
            raise RunNotFoundError("run_not_found")
        # A repeated cancel request may carry the version observed before the
        # first cancel CAS.  Once the same technical transition is visible,
        # return it idempotently instead of forcing clients to invent a new
        # expected_version.  Any older version remains a real conflict.
        if run.execution_status == "cancel_requested":
            if request.expected_version in {run.state_version, run.state_version - 1}:
                return self._response(run)
            raise CASConflictError("cas_conflict")
        if run.execution_status == "cancelled":
            if request.expected_version in {run.state_version, run.state_version - 1}:
                return self._response(run)
            raise CASConflictError("cas_conflict")
        if run.state_version != request.expected_version:
            raise CASConflictError("cas_conflict")
        if run.execution_status in {"completed", "failed", "cancelled"}:
            return self._response(run)
        updated = await self.run_dal.cas_update(
            run_id=request.run_id,
            tenant_id=tenant_id,
            expected_version=request.expected_version,
            values={"execution_status": "cancel_requested"},
        )
        if updated is None:
            raise CASConflictError("cas_conflict")
        await self.trace_dal.create_event(
            {
                "id": uuid4().hex,
                "run_id": updated.id,
                "tenant_id": tenant_id,
                "trace_namespace": updated.trace_namespace,
                "stage_key": "cancel",
                "event_type": "run_cancel_requested",
                "event_payload_json": {},
                "fingerprint": updated.release_fingerprint,
                "state_version": updated.state_version,
            }
        )
        event_id = uuid4().hex
        task_id = uuid4().hex
        message = {
            "run_id": updated.id,
            "task_id": task_id,
            "stage_key": "cancel",
            "release_fingerprint": updated.release_fingerprint,
            "expected_version": updated.state_version,
            "trace_namespace": updated.trace_namespace,
        }
        await self.outbox_dal.create_event(
            {
                "id": event_id,
                "run_id": updated.id,
                "tenant_id": tenant_id,
                "task_id": task_id,
                "stage_key": "cancel",
                "event_type": "execute",
                "release_fingerprint": updated.release_fingerprint,
                "expected_version": updated.state_version,
                "trace_namespace": updated.trace_namespace,
                "message_json": message,
                "message_payload_hash": _sha256_json(message),
                "message_whitelist_version": "xray-message.v1",
                "publish_status": "pending",
                "attempt_count": 0,
            }
        )
        return self._response(updated)
