"""Session/Study/Image lifecycle services.

This module owns only business and engineering input state.  It never creates
or edits an AI medical verdict.  Image bytes are resolved later by a worker;
the API stores opaque source references and immutable manifest metadata only.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.xray_accuracy import (
    XRaySessionCreate,
    XRayStudyPreparationCreate,
)

from app.crud.xray_accuracy import (
    XRayImageAssetDal,
    XRaySessionDal,
    XRaySessionEventDal,
    XRayStudySnapshotDal,
)
from app.service.xray_accuracy.application_service import (
    XRayRunService,
    _sha256_json,
    _validate_safe_metadata,
)
from app.service.xray_accuracy.errors import (
    IdempotencyConflictError,
    InputContractError,
    SessionNotFoundError,
    StudyNotFoundError,
)


_OPAQUE_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}")


def _validate_ref(value: str, error: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_REF.fullmatch(value):
        raise InputContractError(error)
    return value


class XRayLifecycleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_dal = XRaySessionDal(db)
        self.session_event_dal = XRaySessionEventDal(db)
        self.study_dal = XRayStudySnapshotDal(db)
        self.asset_dal = XRayImageAssetDal(db)
        self.run_service = XRayRunService(db)

    @staticmethod
    def _session_response(session, event_count: int = 0) -> dict[str, Any]:
        return {
            "session_id": session.id,
            "tenant_id": session.tenant_id,
            "subject_id": session.subject_id,
            "case_request_id": session.case_request_id,
            "module_key": session.module_key,
            "session_status": session.session_status,
            "created_at": session.created_at,
            "closed_at": session.closed_at,
            "event_count": event_count,
        }

    async def _session_response_with_event_count(self, session: Any) -> dict[str, Any]:
        _, count = await self.session_event_dal.list_for_session(
            tenant_id=session.tenant_id, session_id=session.id
        )
        return self._session_response(session, event_count=count)

    @staticmethod
    def _study_response(snapshot) -> dict[str, Any]:
        return {
            "study_id": snapshot.study_id,
            "study_revision_id": snapshot.study_revision_id,
            "session_id": snapshot.session_id,
            "study_status": snapshot.study_status,
            "expected_image_count": snapshot.expected_image_count,
            "expected_manifest_sha256": snapshot.expected_manifest_sha256,
            "coverage_status": snapshot.coverage_status,
            "identity_confidence": snapshot.identity_confidence,
            "body_scope": snapshot.body_scope,
            "species": snapshot.species,
            "frozen_at": snapshot.frozen_at,
        }

    @staticmethod
    def _asset_response(asset) -> dict[str, Any]:
        return {
            "asset_id": asset.id,
            "study_revision_id": asset.study_revision_id,
            "source_index": asset.source_index,
            "asset_role": asset.asset_role,
            "asset_status": asset.asset_status,
            "content_sha256": asset.content_sha256,
            "mime_type": asset.mime_type,
            "byte_size": asset.byte_size,
            "pixel_width": asset.pixel_width,
            "pixel_height": asset.pixel_height,
            "projection": asset.projection,
            "body_part": asset.body_part,
            "object_available": bool(asset.object_key and asset.asset_status == "uploaded"),
        }

    async def _existing_preparation_response(
        self,
        *,
        tenant_id: str,
        payload: XRayStudyPreparationCreate,
        revision_id: str,
        preparation_metadata_sha256: str,
        existing: Any,
    ) -> dict[str, Any]:
        existing_assets = await self.asset_dal.list_originals_for_study(
            tenant_id=tenant_id, study_revision_id=revision_id
        )
        if (
            existing.study_id != payload.study_id
            or existing.session_id != payload.session_id
            or existing.preparation_metadata_sha256 != preparation_metadata_sha256
            or [(asset.source_index, asset.source_image_ref) for asset in existing_assets]
            != [(item.source_index, item.source_image_ref) for item in payload.images]
        ):
            raise IdempotencyConflictError("study_revision_idempotency_conflict")
        existing_run = await self.run_service.run_dal.get_by_request(
            tenant_id=tenant_id,
            request_id=f"prepare:{payload.request_id}",
            contract_version="xray-study-preparation.v1",
        )
        return {
            "study": self._study_response(existing),
            "assets": [self._asset_response(asset) for asset in existing_assets],
            "run": self.run_service._response(existing_run) if existing_run else None,
        }

    async def create_session(
        self, *, context: dict[str, Any], payload: XRaySessionCreate
    ) -> dict[str, Any]:
        if payload.metadata is not None:
            _validate_safe_metadata(payload.metadata, "$.metadata")
        tenant_id = context["tenant_id"]
        subject_id = context["subject"]
        existing = await self.session_dal.get_by_request(
            tenant_id=tenant_id, request_id=payload.request_id
        )
        if existing:
            if existing.subject_id != subject_id:
                raise SessionNotFoundError("session_not_found")
            if (
                existing.case_request_id != payload.case_request_id
                or existing.module_key != payload.module_key
                or _sha256_json(existing.metadata_json) != _sha256_json(payload.metadata)
            ):
                raise IdempotencyConflictError("session_idempotency_conflict")
            return await self._session_response_with_event_count(existing)

        session_id = uuid4().hex
        created = await self.session_dal.create_idempotent(
            {
                "id": session_id,
                "tenant_id": tenant_id,
                "subject_id": subject_id,
                "request_id": payload.request_id,
                "case_request_id": payload.case_request_id,
                "module_key": payload.module_key,
                "session_status": "open",
                "metadata_json": payload.metadata,
            }
        )
        if created is None:
            existing = await self.session_dal.get_by_request(
                tenant_id=tenant_id, request_id=payload.request_id
            )
            if existing is None or existing.subject_id != subject_id:
                raise InputContractError("session_create_race")
            if (
                existing.case_request_id != payload.case_request_id
                or existing.module_key != payload.module_key
                or _sha256_json(existing.metadata_json) != _sha256_json(payload.metadata)
            ):
                raise IdempotencyConflictError("session_idempotency_conflict")
            return await self._session_response_with_event_count(existing)

        event_payload = {
            "module_key": payload.module_key,
            "case_request_id_present": bool(payload.case_request_id),
        }
        await self.session_event_dal.create_event(
            {
                "id": uuid4().hex,
                "session_id": session_id,
                "tenant_id": tenant_id,
                "event_type": "session_started",
                "payload_hash": _sha256_json(event_payload),
                "trace_namespace": f"xray.session:{session_id}",
                "payload_json": event_payload,
                "created_by": subject_id,
            }
        )
        return self._session_response(created, event_count=1)

    async def get_session(
        self, *, tenant_id: str, subject_id: str, session_id: str
    ) -> dict[str, Any]:
        session = await self.session_dal.get_by_id(tenant_id=tenant_id, session_id=session_id)
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.subject_id != subject_id:
            raise SessionNotFoundError("session_not_found")
        events, count = await self.session_event_dal.list_for_session(
            tenant_id=tenant_id, session_id=session_id
        )
        del events
        return self._session_response(session, event_count=count)

    async def cancel_session(self, *, context: dict[str, Any], session_id: str) -> dict[str, Any]:
        tenant_id = context["tenant_id"]
        subject_id = context["subject"]
        session = await self.session_dal.get_by_id(tenant_id=tenant_id, session_id=session_id)
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.subject_id != subject_id:
            raise SessionNotFoundError("session_not_found")
        if session.session_status == "cancelled":
            return await self._session_response_with_event_count(session)
        if session.session_status == "closed":
            raise InputContractError("closed_session_cannot_cancel")
        updated = await self.session_dal.update_status(
            tenant_id=tenant_id,
            session_id=session_id,
            expected_status=session.session_status,
            values={"session_status": "cancelled", "closed_at": datetime.utcnow()},
        )
        if updated is None:
            raise InputContractError("session_state_conflict")
        await self.session_event_dal.create_event(
            {
                "id": uuid4().hex,
                "session_id": session_id,
                "tenant_id": tenant_id,
                "event_type": "session_cancelled",
                "payload_hash": _sha256_json({}),
                "trace_namespace": f"xray.session:{session_id}",
                "payload_json": {},
                "created_by": subject_id,
            }
        )
        return await self._session_response_with_event_count(updated)

    async def create_study_preparation(
        self, *, context: dict[str, Any], payload: XRayStudyPreparationCreate
    ) -> dict[str, Any]:
        tenant_id = context["tenant_id"]
        session = await self.session_dal.get_by_id(
            tenant_id=tenant_id, session_id=payload.session_id
        )
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.subject_id != context["subject"]:
            raise SessionNotFoundError("session_not_found")
        if session.session_status != "open":
            raise InputContractError("session_not_open")
        if payload.safe_metadata is not None:
            _validate_safe_metadata(payload.safe_metadata, "$.safe_metadata")

        indices = [item.source_index for item in payload.images]
        if indices != list(range(len(indices))):
            raise InputContractError("study_source_index_not_contiguous")
        for item in payload.images:
            _validate_ref(item.source_image_ref, "image_ref_must_be_opaque")
        for item in payload.images:
            if item.safe_metadata is not None:
                _validate_safe_metadata(item.safe_metadata, "$.images.safe_metadata")

        revision_id = payload.study_revision_id or _sha256_json(
            {
                "tenant_id": tenant_id,
                "session_id": payload.session_id,
                "study_id": payload.study_id,
                "request_id": payload.request_id,
            }
        )[:32]
        preparation_metadata_sha256 = _sha256_json(
            {
                "request_id": payload.request_id,
                "species": payload.species,
                "body_scope": payload.body_scope,
                "safe_metadata": payload.safe_metadata,
                "images": [
                    {
                        "source_index": item.source_index,
                        "source_image_ref": item.source_image_ref,
                        "mime_type": item.mime_type,
                        "projection": item.projection,
                        "body_part": item.body_part,
                        "safe_metadata": item.safe_metadata,
                    }
                    for item in payload.images
                ],
            }
        )
        existing = await self.study_dal.get_by_revision(
            tenant_id=tenant_id, study_revision_id=revision_id
        )
        if existing:
            return await self._existing_preparation_response(
                tenant_id=tenant_id,
                payload=payload,
                revision_id=revision_id,
                preparation_metadata_sha256=preparation_metadata_sha256,
                existing=existing,
            )

        asset_values: list[dict[str, Any]] = []
        asset_ids: list[str] = []
        for item in payload.images:
            asset_id = uuid4().hex
            asset_ids.append(asset_id)
            asset_values.append(
                {
                    "id": asset_id,
                    "tenant_id": tenant_id,
                    "study_revision_id": revision_id,
                    "source_image_ref": item.source_image_ref,
                    "asset_role": "original",
                    "source_index": item.source_index,
                    "mime_type": item.mime_type,
                    "projection": item.projection,
                    "body_part": item.body_part,
                    "asset_status": "pending",
                }
            )
        snapshot_manifest = [
            {"source_index": index, "source_image_ref": asset_id}
            for index, asset_id in enumerate(asset_ids)
        ]
        snapshot_values = {
            "id": uuid4().hex,
            "study_id": payload.study_id,
            "study_revision_id": revision_id,
            "session_id": payload.session_id,
            "tenant_id": tenant_id,
            "study_status": "assembling",
            "expected_image_count": len(asset_values),
            "expected_manifest_sha256": _sha256_json(snapshot_manifest),
            "preparation_metadata_sha256": preparation_metadata_sha256,
            "ordered_source_image_ids_json": asset_ids,
            "body_scope": payload.body_scope,
            "species": payload.species,
            "identity_confidence": "unknown",
            "coverage_status": "unknown",
        }
        snapshot = await self.study_dal.create_snapshot_idempotent(snapshot_values)
        if snapshot is None:
            existing = await self.study_dal.get_by_revision(
                tenant_id=tenant_id, study_revision_id=revision_id
            )
            if existing is None:
                raise IdempotencyConflictError("study_revision_create_race")
            return await self._existing_preparation_response(
                tenant_id=tenant_id,
                payload=payload,
                revision_id=revision_id,
                preparation_metadata_sha256=preparation_metadata_sha256,
                existing=existing,
            )
        assets = await self.asset_dal.create_assets(asset_values)
        run_payload = {
            "request_id": f"prepare:{payload.request_id}",
            "session_id": payload.session_id,
            "study_id": payload.study_id,
            "case_request_id": session.case_request_id,
            "contract_version": "xray-study-preparation.v1",
            "requested_operation": "prepare_study",
            "study_revision": revision_id,
            "expected_manifest": snapshot_manifest,
            "safe_metadata": payload.safe_metadata,
            "validation_only": True,
        }
        # The run service owns the existing Run/Snapshot/Checkpoint/Outbox
        # transaction contract.  Preparation only adds the Study/Asset facts.
        from app.schemas.xray_accuracy import XRayRunCreate

        run = await self.run_service.create_run(
            context=context, payload=XRayRunCreate.model_validate(run_payload)
        )
        return {
            "study": self._study_response(snapshot),
            "assets": [self._asset_response(asset) for asset in assets],
            "run": run,
        }

    async def get_study(
        self, *, tenant_id: str, subject_id: str, study_revision_id: str
    ) -> dict[str, Any]:
        snapshot = await self.study_dal.get_by_revision(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
        if snapshot is None:
            raise StudyNotFoundError("study_not_found")
        session = await self.session_dal.get_by_id(
            tenant_id=tenant_id, session_id=snapshot.session_id
        )
        if session is None or session.subject_id != subject_id:
            raise StudyNotFoundError("study_not_found")
        assets = await self.asset_dal.list_for_study(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
        return {
            "study": self._study_response(snapshot),
            "assets": [self._asset_response(asset) for asset in assets],
        }

    async def get_study_assets(
        self, *, tenant_id: str, subject_id: str, study_revision_id: str
    ) -> list[dict[str, Any]]:
        snapshot = await self.study_dal.get_by_revision(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
        if snapshot is None:
            raise StudyNotFoundError("study_not_found")
        session = await self.session_dal.get_by_id(
            tenant_id=tenant_id, session_id=snapshot.session_id
        )
        if session is None or session.subject_id != subject_id:
            raise StudyNotFoundError("study_not_found")
        assets = await self.asset_dal.list_for_study(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
        return [self._asset_response(asset) for asset in assets]

    async def get_session_events(
        self, *, tenant_id: str, subject_id: str, session_id: str
    ) -> list[dict[str, Any]]:
        session = await self.session_dal.get_by_id(
            tenant_id=tenant_id, session_id=session_id
        )
        if session is None or session.subject_id != subject_id:
            raise SessionNotFoundError("session_not_found")
        events, _ = await self.session_event_dal.list_for_session(
            tenant_id=tenant_id, session_id=session_id
        )
        return [
            {
                "event_id": event.id,
                "session_id": event.session_id,
                "event_type": event.event_type,
                "payload_hash": event.payload_hash,
                "trace_namespace": event.trace_namespace,
                "created_at": event.created_at,
                "created_by": event.created_by,
            }
            for event in events
        ]
