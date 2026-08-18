"""Legacy XRay V2 API semantics backed by the new ms-image facts.

This module is an adapter, not a copy of the old persistence model. It maps
legacy calls onto Session/Study/Asset/Run/Outbox and never creates a second
task or report status source.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.xray_accuracy import (
    XRayOutboxDal,
    XRayRequestSnapshotDal,
    XRayRunDal,
    XRayStudySnapshotDal,
)
from app.schemas.xray_accuracy import (
    LegacyPreparationRequest,
    LegacyReportSubmitRequest,
    LegacySessionStartRequest,
    XRayImageRef,
    XRayRunCreate,
    XRaySessionCreate,
    XRayStudyImageCreate,
    XRayStudyPreparationCreate,
)

from .application_service import XRayRunService, _sha256_json
from .errors import InputContractError, RunNotFoundError, SessionNotFoundError
from .lifecycle_service import XRayLifecycleService


_OPAQUE_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}")
_ACTIVE_RUN_STATUSES = {"queued", "dispatched", "running", "retry_wait"}


class LegacyImageRefResolver:
    """Convert a legacy URL to an approved opaque reference without persisting it."""

    def __init__(self, mapping_path: str | None = None):
        self.mapping_path = (mapping_path or settings.AI_LEGACY_IMAGE_REF_MAP_PATH).strip()
        self._mapping: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._mapping is not None:
            return self._mapping
        if not self.mapping_path:
            self._mapping = {}
            return self._mapping
        path = Path(self.mapping_path).expanduser().resolve()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InputContractError("legacy_image_ref_map_invalid") from exc
        if not isinstance(loaded, dict) or len(loaded) > 4096:
            raise InputContractError("legacy_image_ref_map_invalid")
        mapping: dict[str, str] = {}
        for url_sha256, source_ref in loaded.items():
            if (
                not isinstance(url_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", url_sha256) is None
                or not isinstance(source_ref, str)
                or _OPAQUE_REF.fullmatch(source_ref) is None
            ):
                raise InputContractError("legacy_image_ref_map_invalid")
            mapping[url_sha256] = source_ref
        self._mapping = mapping
        return mapping

    def resolve(self, *, image_url: str | None, source_image_ref: str | None) -> str:
        if source_image_ref:
            if _OPAQUE_REF.fullmatch(source_image_ref) is None:
                raise InputContractError("legacy_source_image_ref_invalid")
            return source_image_ref
        if not image_url:
            raise InputContractError("legacy_image_source_required")
        parts = urlsplit(image_url)
        if parts.scheme.casefold() != "https" or not parts.hostname or parts.username or parts.password:
            raise InputContractError("legacy_image_url_invalid")
        digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
        source_ref = self._load().get(digest)
        if source_ref is None:
            raise InputContractError("legacy_image_url_not_approved")
        return source_ref


class XRayLegacyCompatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.lifecycle = XRayLifecycleService(db)
        self.run_service = XRayRunService(db)
        self.run_dal = XRayRunDal(db)
        self.snapshot_dal = XRayRequestSnapshotDal(db)
        self.study_dal = XRayStudySnapshotDal(db)
        self.outbox_dal = XRayOutboxDal(db)
        self.ref_resolver = LegacyImageRefResolver()

    @staticmethod
    def _legacy_status(run: Any) -> str:
        if run.execution_status in {"queued", "dispatched"}:
            return "queued"
        if run.execution_status in {"running", "retry_wait"}:
            return "processing"
        if run.execution_status in {"failed", "dead_letter"}:
            return "failed"
        if run.execution_status in {"cancel_requested", "cancelled"}:
            return "cancelled"
        if run.execution_status == "completed":
            if run.ai_medical_status == "not_produced":
                return "medical_not_produced"
            return "completed"
        return "unknown"

    async def _task_for_run(self, *, tenant_id: str, run_id: str):
        rows = await self.outbox_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id, limit=100
        )
        return rows[-1] if rows else None

    async def start_session(
        self, *, context: dict[str, Any], payload: LegacySessionStartRequest
    ) -> dict[str, Any]:
        if payload.module_type != 3:
            raise InputContractError("legacy_module_type_must_be_xray")
        pet_profile_id = str(payload.pet_profile_id).strip()
        if not pet_profile_id or len(pet_profile_id) > 128:
            raise InputContractError("legacy_pet_profile_id_invalid")
        request_id = payload.request_id or f"legacy-session:{uuid4().hex}"
        session = await self.lifecycle.create_session(
            context=context,
            payload=XRaySessionCreate(
                request_id=request_id,
                case_request_id=pet_profile_id,
                module_key="xray",
                metadata={"legacy_module_type": 3},
            ),
        )
        return {
            "session_id": session["session_id"],
            # Kept only as a response alias for old callers. No MedicalRecord
            # row is created and Session remains the single business fact.
            "medical_record_id": session["session_id"],
            "pet_profile_id": pet_profile_id,
            "session_status": session["session_status"],
        }

    def _normalize_images(
        self, payload_images
    ) -> tuple[list[XRayStudyImageCreate], int]:
        normalized: list[XRayStudyImageCreate] = []
        by_ref: dict[str, XRayStudyImageCreate] = {}
        duplicate_count = 0
        for fallback_index, image in enumerate(payload_images):
            source_ref = self.ref_resolver.resolve(
                image_url=image.image_url, source_image_ref=image.source_image_ref
            )
            if source_ref in by_ref:
                existing = by_ref[source_ref]
                if (
                    existing.mime_type != image.mime_type
                    or existing.projection != image.view_code
                    or existing.body_part != image.body_part
                ):
                    raise InputContractError("legacy_duplicate_image_metadata_conflict")
                duplicate_count += 1
                continue
            item = XRayStudyImageCreate(
                    source_index=len(normalized),
                    source_image_ref=source_ref,
                    mime_type=image.mime_type,
                    projection=image.view_code,
                    body_part=image.body_part,
                    safe_metadata={
                        "legacy_source_index": (
                            image.source_image_index
                            if image.source_image_index is not None
                            else fallback_index
                        ),
                        **(
                            {"study_event_key": image.study_event_key}
                            if image.study_event_key
                            else {}
                        ),
                    },
                )
            normalized.append(item)
            by_ref[source_ref] = item
        if not normalized:
            raise InputContractError("legacy_preparation_images_empty")
        return normalized, duplicate_count

    async def submit_preparation(
        self, *, context: dict[str, Any], payload: LegacyPreparationRequest
    ) -> dict[str, Any]:
        images, duplicate_count = self._normalize_images(payload.image_urls)
        request_id = payload.request_id or _sha256_json(
            {
                "session_id": payload.session_id,
                "refs": [image.source_image_ref for image in images],
                "species": payload.species,
                "body_scope": payload.body_scope,
            }
        )[:32]
        study_id = payload.study_id or f"study-{payload.session_id}"
        result = await self.lifecycle.create_study_preparation(
            context=context,
            payload=XRayStudyPreparationCreate(
                request_id=f"legacy:{request_id}",
                session_id=payload.session_id,
                study_id=study_id,
                images=images,
                species=payload.species,
                body_scope=payload.body_scope,
                safe_metadata={"legacy_entry": "xray_v2_preparations"},
            ),
        )
        run = result.get("run")
        if run is None:
            raise InputContractError("legacy_preparation_run_missing")
        task = await self._task_for_run(
            tenant_id=context["tenant_id"], run_id=run.run_id
        )
        if task is None:
            raise InputContractError("legacy_preparation_task_missing")
        assets = result["assets"]
        preparation_run = await self.run_dal.get_by_id(run.run_id, context["tenant_id"])
        if preparation_run is None:
            raise InputContractError("legacy_preparation_run_missing")
        success_count = sum(1 for asset in assets if asset["asset_status"] == "uploaded")
        failed_count = sum(
            1 for asset in assets if asset["asset_status"] in {"invalid", "failed"}
        )
        return {
            "session_id": payload.session_id,
            "study_id": result["study"]["study_id"],
            "study_revision_id": result["study"]["study_revision_id"],
            "status": self._legacy_status(preparation_run),
            "total": len(assets),
            "input_total": len(payload.image_urls),
            "unique_image_total": len(assets),
            "duplicate_input_count": duplicate_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "preparation_task_id": task.task_id,
            "results": [
                {
                    "source_index": asset["source_index"],
                    "source_image_ref": images[index].source_image_ref,
                    "asset_id": asset["asset_id"],
                    "status": asset["asset_status"],
                }
                for index, asset in enumerate(assets)
            ],
        }

    async def _select_study(
        self,
        *,
        tenant_id: str,
        session_id: str,
        study_revision_id: str | None,
        study_id: str | None = None,
    ):
        if study_revision_id:
            study = await self.study_dal.get_by_revision(
                tenant_id=tenant_id, study_revision_id=study_revision_id
            )
            if (
                study is None
                or study.session_id != session_id
                or (study_id is not None and study.study_id != study_id)
            ):
                raise InputContractError("legacy_study_not_found")
            return study
        studies, _ = await self.study_dal.list_for_session(
            tenant_id=tenant_id, session_id=session_id, page=1, limit=100
        )
        return next(
            (
                study
                for study in studies
                if (study_id is None or study.study_id == study_id)
                and study.study_status == "ready_full_study"
                and study.frozen_at is not None
            ),
            next(
                (study for study in studies if study_id is None or study.study_id == study_id),
                None,
            ),
        )

    async def submit_report(
        self, *, context: dict[str, Any], payload: LegacyReportSubmitRequest
    ) -> dict[str, Any]:
        if payload.force_refresh_preparation or payload.force_refresh_segmentation:
            # The new fact model keeps immutable Study revisions and complete
            # retry lineage. It must not emulate the old destructive refresh
            # semantics by deleting or overwriting prior work.
            raise InputContractError("legacy_force_refresh_not_supported")
        await self.lifecycle.get_session(
            tenant_id=context["tenant_id"],
            subject_id=context["subject"],
            session_id=payload.session_id,
        )
        if payload.image_urls:
            preparation = await self.submit_preparation(
                context=context,
                payload=LegacyPreparationRequest(
                    session_id=payload.session_id,
                    image_urls=payload.image_urls,
                    request_id=(payload.request_id or uuid4().hex) + ":prepare",
                    species=payload.species,
                    body_scope=payload.body_scope,
                ),
            )
            study = await self.study_dal.get_by_revision(
                tenant_id=context["tenant_id"],
                study_revision_id=preparation["study_revision_id"],
            )
        else:
            study = await self._select_study(
                tenant_id=context["tenant_id"],
                session_id=payload.session_id,
                study_revision_id=payload.study_revision_id,
            )
        if study is None:
            raise InputContractError("legacy_preparation_required")
        if payload.xray_list:
            selected = [str(value).strip() for value in payload.xray_list]
            if any(_OPAQUE_REF.fullmatch(value) is None for value in selected):
                raise InputContractError("legacy_xray_list_requires_asset_ids")
            if len(selected) != len(set(selected)):
                raise InputContractError("legacy_xray_list_duplicate")
            frozen_ids = list(study.ordered_source_image_ids_json or [])
            if selected != frozen_ids:
                # Diagnosis always uses the complete frozen Study. A partial
                # legacy image selection cannot silently reduce coverage.
                raise InputContractError("legacy_xray_list_must_match_full_study")
        if study.study_status != "ready_full_study" or study.frozen_at is None:
            preparation_run = await self.run_dal.get_latest_for_session_operation(
                tenant_id=context["tenant_id"],
                session_id=payload.session_id,
                requested_operation="prepare_study",
                study_id=study.study_id,
                study_revision_id=study.study_revision_id,
            )
            if preparation_run is None:
                raise InputContractError("legacy_preparation_required")
            task = await self._task_for_run(
                tenant_id=context["tenant_id"], run_id=preparation_run.id
            )
            if task is None:
                raise InputContractError("legacy_preparation_task_missing")
            return {
                "job_id": task.task_id,
                "task_id": task.task_id,
                "run_id": preparation_run.id,
                "session_id": payload.session_id,
                "study_revision_id": study.study_revision_id,
                "status": "preparation_processing",
                "report_type": "xray_v2",
                "reused": True,
                "medical_status": "not_produced",
            }
        existing = await self.run_dal.get_latest_for_session_operation(
            tenant_id=context["tenant_id"],
            session_id=payload.session_id,
            requested_operation="diagnose",
            study_id=study.study_id,
            study_revision_id=study.study_revision_id,
            execution_statuses=_ACTIVE_RUN_STATUSES,
        )
        reused = existing is not None
        if existing is None:
            request_id = payload.request_id or f"legacy-report:{uuid4().hex}"
            manifest = [
                XRayImageRef(source_index=index, source_image_ref=asset_id)
                for index, asset_id in enumerate(study.ordered_source_image_ids_json)
            ]
            response = await self.run_service.create_run(
                context=context,
                payload=XRayRunCreate(
                    request_id=request_id,
                    session_id=payload.session_id,
                    study_id=study.study_id,
                    requested_operation="diagnose",
                    contract_version="xray-legacy-report.v1",
                    study_revision=study.study_revision_id,
                    expected_manifest=manifest,
                    safe_metadata={"legacy_entry": "xray_v2_reports"},
                    validation_only=True,
                ),
            )
            existing = await self.run_dal.get_by_id(
                response.run_id, context["tenant_id"]
            )
        if existing is None:
            raise InputContractError("legacy_report_run_missing")
        task = await self._task_for_run(
            tenant_id=context["tenant_id"], run_id=existing.id
        )
        if task is None:
            raise InputContractError("legacy_report_task_missing")
        return {
            "job_id": task.task_id,
            "task_id": task.task_id,
            "run_id": existing.id,
            "session_id": payload.session_id,
            "study_revision_id": study.study_revision_id,
            "status": self._legacy_status(existing),
            "report_type": "xray_v2",
            "reused": reused,
            "medical_status": existing.ai_medical_status,
        }

    async def get_task_status(
        self, *, tenant_id: str, subject_id: str, task_id: str
    ) -> dict[str, Any]:
        task = await self.outbox_dal.get_by_task_id(
            tenant_id=tenant_id, task_id=task_id
        )
        if task is None:
            raise RunNotFoundError("task_not_found")
        run = await self.run_dal.get_by_id(task.run_id, tenant_id)
        if run is None or run.subject_id != subject_id:
            raise RunNotFoundError("task_not_found")
        return {
            "task_id": task.task_id,
            "run_id": run.id,
            "session_id": run.session_id,
            "status": self._legacy_status(run),
            "execution_status": run.execution_status,
            "medical_status": run.ai_medical_status,
            "publish_status": task.publish_status,
            "consumer_status": task.consumer_status,
        }

    async def get_report_view(
        self, *, tenant_id: str, subject_id: str, session_id: str
    ) -> dict[str, Any]:
        await self.lifecycle.get_session(
            tenant_id=tenant_id, subject_id=subject_id, session_id=session_id
        )
        run = await self.run_dal.get_latest_for_session_operation(
            tenant_id=tenant_id,
            session_id=session_id,
            requested_operation="diagnose",
        )
        if run is None:
            return {
                "session_id": session_id,
                "status": "not_started",
                "summary": {"medical_verdict_produced": False},
            }
        task = await self._task_for_run(tenant_id=tenant_id, run_id=run.id)
        request_snapshot = await self.snapshot_dal.get_by_run(
            tenant_id=tenant_id, run_id=run.id
        )
        if request_snapshot is None:
            raise InputContractError("legacy_report_snapshot_missing")
        study = await self._select_study(
            tenant_id=tenant_id,
            session_id=session_id,
            study_revision_id=request_snapshot.study_revision,
            study_id=run.study_id,
        )
        return {
            "session_id": session_id,
            "status": self._legacy_status(run),
            "run_id": run.id,
            "task_id": task.task_id if task else None,
            "study_id": run.study_id,
            "study_revision_id": study.study_revision_id if study else None,
            "decision": None,
            "primary_diagnosis": None,
            "review_required": None,
            "final_reason": None,
            "disease_list": [],
            "summary": {
                "execution_status": run.execution_status,
                "engineering_eligibility": run.engineering_eligibility,
                "ai_medical_status": run.ai_medical_status,
                "medical_verdict_produced": run.ai_medical_status != "not_produced",
            },
        }

    async def get_segmentation_view(
        self, *, tenant_id: str, subject_id: str, session_id: str
    ) -> dict[str, Any]:
        report = await self.get_report_view(
            tenant_id=tenant_id, subject_id=subject_id, session_id=session_id
        )
        study = await self._select_study(
            tenant_id=tenant_id,
            session_id=session_id,
            study_revision_id=report.get("study_revision_id"),
            study_id=report.get("study_id"),
        )
        return {
            "session_id": session_id,
            "status": "empty",
            "preview_status": "empty",
            "task_status": report.get("status", "not_started"),
            "medical_verdict_produced": False,
            "images": [],
            "study_revision_id": study.study_revision_id if study else None,
        }


__all__ = ["LegacyImageRefResolver", "XRayLegacyCompatService"]
