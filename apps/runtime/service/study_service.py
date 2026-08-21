import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.core.imaging.manifest import (
    EMPTY_MANIFEST,
    ManifestContractError,
    build_series_manifest,
    build_study_manifest,
)
from apps.runtime.crud.image import ImageDal
from apps.runtime.crud.series import SeriesDal
from apps.runtime.crud.session import SessionDal
from apps.runtime.crud.study import StudyDal
from apps.runtime.models.imaging_base import new_opaque_id
from apps.runtime.models.series import Series
from apps.runtime.models.study import Study
from apps.runtime.schemas.study import (
    SeriesCreate,
    SeriesResponse,
    StudyCreate,
    StudyDetailResponse,
    StudyFinalizeRequest,
    StudyResponse,
)
from apps.runtime.service.session_service import (
    SessionAccessDeniedError,
    SessionNotFoundError,
    SessionStateConflictError,
)


class StudyServiceError(ValueError):
    pass


class StudyNotFoundError(StudyServiceError):
    pass


class StudyAccessDeniedError(StudyServiceError):
    pass


class StudyIdempotencyConflictError(StudyServiceError):
    pass


class StudyStateConflictError(StudyServiceError):
    pass


class SeriesNotFoundError(StudyServiceError):
    pass


@dataclass(frozen=True)
class StudyRevisionResult:
    series: Series
    study: Study


class StudyService:
    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)
        self.study_dal = StudyDal(db)
        self.series_dal = SeriesDal(db)
        self.image_dal = ImageDal(db)

    @staticmethod
    def _study_response(study: Study) -> StudyResponse:
        return StudyResponse.model_validate(study)

    @staticmethod
    def _series_response(series: Series) -> SeriesResponse:
        return SeriesResponse.model_validate(series)

    @staticmethod
    def _source_study_id(payload: StudyCreate) -> str:
        if payload.source_study_id:
            return payload.source_study_id
        stable = payload.model_dump(mode="json", exclude={"source_study_id"})
        digest = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"generated:{digest[:48]}"

    async def create_study(
        self, *, payload: StudyCreate, requester_id: str
    ) -> StudyResponse:
        session = await self._owned_session(
            session_id=payload.session_id, requester_id=requester_id
        )
        if session.status not in {"open", "processing"}:
            raise StudyStateConflictError("session_not_accepting_studies")

        source_study_id = self._source_study_id(payload)
        existing = await self.study_dal.get_by_source(
            session_id=session.id, source_study_id=source_study_id
        )
        values = {
            "session_id": session.id,
            "source_study_id": source_study_id,
            "modality_type": payload.modality_type,
            "dicom_study_uid": payload.dicom_study_uid,
            "body_part": payload.body_part,
            "metadata_schema_version": payload.metadata_schema_version,
            "revision_no": 1,
            "revision_id": new_opaque_id(),
            "revision_reason": "initial",
            "revision_changed_at": datetime.utcnow(),
            "expected_image_count": payload.expected_image_count,
            "expected_manifest_sha256": payload.expected_manifest_sha256,
            "completeness_status": "unknown",
            "completeness_attested_by": payload.completeness_attested_by,
            "identity_status": payload.identity_status,
            "status": "ingesting",
            "state_version": 0,
            "technical_metadata_json": payload.technical_metadata,
            "acquired_at": payload.acquired_at,
        }
        if existing is not None:
            self._assert_study_match(existing, values)
            return self._study_response(existing)

        created = await self.study_dal.create_idempotent(values)
        if created is None:
            existing = await self.study_dal.get_by_source(
                session_id=session.id, source_study_id=source_study_id
            )
            if existing is None:
                raise StudyStateConflictError("study_create_race")
            self._assert_study_match(existing, values)
            created = existing

        if session.status == "open":
            updated_session = await self.session_dal.cas_update(
                session_id=session.id,
                expected_version=session.state_version,
                values={"status": "processing"},
            )
            if updated_session is None:
                raise SessionStateConflictError("session_state_conflict")
        return self._study_response(created)

    async def create_series(
        self, *, payload: SeriesCreate, requester_id: str
    ) -> SeriesResponse:
        study = await self._owned_study(
            study_id=payload.study_id, requester_id=requester_id
        )
        session = await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        if session.status not in {"open", "processing"} or study.status == "invalid":
            raise StudyStateConflictError("study_not_accepting_series")
        values = {
            "study_id": study.id,
            "series_key": payload.series_key,
            "dicom_series_uid": payload.dicom_series_uid,
            "series_no": payload.series_no,
            "metadata_schema_version": payload.metadata_schema_version,
            "expected_image_count": payload.expected_image_count,
            "actual_image_count": 0,
            "manifest_sha256": EMPTY_MANIFEST.sha256,
            "status": "ingesting",
            "state_version": 0,
            "technical_metadata_json": payload.technical_metadata,
            "acquired_at": payload.acquired_at,
        }
        existing = await self.series_dal.get_by_key(
            study_id=study.id, series_key=payload.series_key
        )
        if existing is not None:
            self._assert_series_match(existing, values)
            return self._series_response(existing)
        created = await self.series_dal.create_idempotent(values)
        if created is None:
            existing = await self.series_dal.get_by_key(
                study_id=study.id, series_key=payload.series_key
            )
            if existing is None:
                raise StudyStateConflictError("series_create_race")
            self._assert_series_match(existing, values)
            created = existing
        return self._series_response(created)

    async def get_study(
        self, *, study_id: str, requester_id: str
    ) -> StudyDetailResponse:
        study = await self._owned_study(study_id=study_id, requester_id=requester_id)
        series = await self.series_dal.list_for_study(study.id)
        series.sort(
            key=lambda item: (
                item.series_no is None,
                item.series_no if item.series_no is not None else 0,
                item.series_key,
            )
        )
        return StudyDetailResponse(
            study=self._study_response(study),
            series=[self._series_response(item) for item in series],
        )

    async def finalize_study(
        self, *, payload: StudyFinalizeRequest, requester_id: str
    ) -> StudyResponse:
        study = await self._owned_study(study_id=payload.id, requester_id=requester_id)
        if study.status == "ready":
            if (
                study.revision_id == payload.current_revision_id
                and study.state_version == payload.expected_state_version + 1
            ):
                return self._study_response(study)
            raise StudyStateConflictError("study_finalize_conflict")
        if (
            study.state_version != payload.expected_state_version
            or study.revision_id != payload.current_revision_id
        ):
            raise StudyStateConflictError("study_finalize_conflict")
        if study.identity_status != "confirmed":
            raise StudyStateConflictError("study_identity_not_confirmed")
        series_rows = await self.series_dal.list_for_study(study.id)
        if not series_rows:
            raise StudyStateConflictError("study_series_missing")
        if any(series.status != "ready" for series in series_rows):
            raise StudyStateConflictError("study_series_not_ready")
        if any(
            series.expected_image_count is not None
            and series.actual_image_count != series.expected_image_count
            for series in series_rows
        ):
            raise StudyStateConflictError("study_series_count_conflict")
        for series in series_rows:
            images = await self.image_dal.list_for_series(series.id)
            if any(image.status in {"uploading", "validating"} for image in images):
                raise StudyStateConflictError("study_image_in_progress")
        actual_count = sum(series.actual_image_count for series in series_rows)
        if (
            study.expected_image_count is not None
            and actual_count != study.expected_image_count
        ):
            raise StudyStateConflictError("study_image_count_conflict")
        if not study.resolved_manifest_sha256:
            raise StudyStateConflictError("study_manifest_unresolved")
        if study.expected_manifest_sha256 and (
            study.expected_manifest_sha256 != study.resolved_manifest_sha256
        ):
            raise StudyStateConflictError("study_manifest_conflict")
        if study.completeness_status != "complete":
            raise StudyStateConflictError("study_incomplete")
        updated = await self.study_dal.cas_finalize(
            study_id=study.id,
            expected_version=study.state_version,
            current_revision_id=study.revision_id,
            values={
                "completeness_status": "complete",
                "status": "ready",
                "ready_at": datetime.utcnow(),
            },
        )
        if updated is None:
            raise StudyStateConflictError("study_finalize_conflict")
        return self._study_response(updated)

    async def recompute_after_image_change(
        self,
        *,
        series_id: str,
        revision_reason: str,
        changed_at: datetime,
    ) -> StudyRevisionResult:
        if revision_reason not in {
            "add",
            "replace",
            "delete",
            "reorder",
            "metadata_correction",
        }:
            raise StudyStateConflictError("study_revision_reason_invalid")
        series = await self.series_dal.get_by_id(series_id.strip())
        if series is None:
            raise SeriesNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise StudyNotFoundError("study_not_found")

        ready_images = await self.image_dal.list_ready_for_series(series.id)
        try:
            series_manifest = build_series_manifest(ready_images)
        except ManifestContractError as exc:
            raise StudyStateConflictError(str(exc)) from exc
        actual_count = len(series_manifest.items)
        if series.expected_image_count is None:
            series_status = "validating" if actual_count else "ingesting"
        elif actual_count < series.expected_image_count:
            series_status = "validating"
        elif actual_count == series.expected_image_count:
            series_status = "ready"
        else:
            series_status = "invalid"
        updated_series = await self.series_dal.cas_update(
            series_id=series.id,
            expected_version=series.state_version,
            values={
                "actual_image_count": actual_count,
                "manifest_sha256": series_manifest.sha256,
                "status": series_status,
                "ready_at": changed_at if series_status == "ready" else None,
            },
        )
        if updated_series is None:
            raise StudyStateConflictError("series_manifest_conflict")

        series_rows = await self.series_dal.list_for_study(study.id)
        try:
            study_manifest = build_study_manifest(series_rows)
        except ManifestContractError as exc:
            raise StudyStateConflictError(str(exc)) from exc
        total_images = sum(item["actual_image_count"] for item in study_manifest.items)
        has_invalid_series = any(item.status == "invalid" for item in series_rows)
        all_series_ready = bool(series_rows) and all(
            item.status == "ready" for item in series_rows
        )
        if has_invalid_series:
            completeness = "conflict"
        elif (
            study.expected_image_count is not None
            and total_images > study.expected_image_count
        ):
            completeness = "conflict"
        elif study.expected_manifest_sha256 and (
            study.expected_manifest_sha256 != study_manifest.sha256
        ):
            completeness = "conflict"
        elif (
            study.expected_image_count is not None
            and total_images < study.expected_image_count
        ) or not all_series_ready:
            completeness = "partial"
        else:
            completeness = "complete"

        updated_study = await self.study_dal.cas_revision(
            study_id=study.id,
            expected_version=study.state_version,
            current_revision_id=study.revision_id,
            values={
                "revision_no": study.revision_no + 1,
                "revision_id": new_opaque_id(),
                "revision_reason": revision_reason,
                "revision_changed_at": changed_at,
                "resolved_manifest_sha256": study_manifest.sha256,
                "completeness_status": completeness,
                "status": "validating",
                "ready_at": None,
            },
        )
        if updated_study is None:
            raise StudyStateConflictError("study_revision_conflict")
        return StudyRevisionResult(series=updated_series, study=updated_study)

    async def _owned_session(self, *, session_id: str, requester_id: str):
        session = await self.session_dal.get_by_id(session_id.strip())
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.requester_id != requester_id.strip():
            raise SessionAccessDeniedError("session_access_denied")
        return session

    async def _owned_study(self, *, study_id: str, requester_id: str) -> Study:
        study = await self.study_dal.get_by_id(study_id.strip())
        if study is None:
            raise StudyNotFoundError("study_not_found")
        await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        return study

    @staticmethod
    def _assert_study_match(study: Study, values: dict[str, Any]) -> None:
        fields = (
            "session_id",
            "source_study_id",
            "modality_type",
            "dicom_study_uid",
            "body_part",
            "metadata_schema_version",
            "expected_image_count",
            "expected_manifest_sha256",
            "completeness_attested_by",
            "identity_status",
            "technical_metadata_json",
            "acquired_at",
        )
        if any(getattr(study, field) != values[field] for field in fields):
            raise StudyIdempotencyConflictError("study_idempotency_conflict")

    @staticmethod
    def _assert_series_match(series: Series, values: dict[str, Any]) -> None:
        fields = (
            "study_id",
            "series_key",
            "dicom_series_uid",
            "series_no",
            "metadata_schema_version",
            "expected_image_count",
            "technical_metadata_json",
            "acquired_at",
        )
        if any(getattr(series, field) != values[field] for field in fields):
            raise StudyIdempotencyConflictError("series_idempotency_conflict")


__all__ = [
    "SeriesNotFoundError",
    "StudyAccessDeniedError",
    "StudyIdempotencyConflictError",
    "StudyNotFoundError",
    "StudyService",
    "StudyServiceError",
    "StudyRevisionResult",
    "StudyStateConflictError",
]
