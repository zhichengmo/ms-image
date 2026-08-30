from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.imaging.object_store import (
    MultipartPart,
    OSSObjectStore,
    ObjectHead,
    ObjectStorageGateway,
    ObjectValidation,
)
from apps.backend.core.imaging.manifest import (
    PROJECTION_SOURCE_CALLER,
    ManifestContractError,
    build_projection_metadata,
    canonical_json_bytes,
    projection_fact_from_image,
)
from apps.backend.crud.image import ImageDal
from apps.backend.crud.object_reconcile_cursor import ObjectReconcileCursorDal
from apps.backend.crud.outbox import OutboxDal
from apps.backend.crud.series import SeriesDal
from apps.backend.crud.session import SessionDal
from apps.backend.crud.study import StudyDal
from apps.backend.models.image import Image
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.models.object_reconcile_cursor import ObjectReconcileCursor
from apps.backend.schemas.image import (
    ImageAbortCommand,
    ImageCompleteUploadRequest,
    ImageCreate,
    ImageListMultipartPartsRequest,
    ImageMultipartPartReceipt,
    ImageMultipartPartsResponse,
    ImageMultipartUploadTicket,
    ImagePageItemResponse,
    ImagePageQuery,
    ImagePageResult,
    ImageProjectionProvenance,
    ImagePrepareMultipartRequest,
    ImagePreparePartsRequest,
    ImagePrepareUploadRequest,
    ImageReplaceRequest,
    ImageReplaceMultipartRequest,
    ImageResponse,
    ImageUploadTicket,
)
from apps.backend.schemas.outbox import ValidateImageMessage
from apps.backend.services.runtime.service.session_service import SessionAccessDeniedError, SessionNotFoundError
from apps.backend.services.runtime.service.study_service import StudyService, StudyStateConflictError
from apps.backend.services.runtime.service.image_upload_workflow import ImageUploadWorkflow


class ImageServiceError(ValueError):
    pass


class ImageNotFoundError(ImageServiceError):
    pass


class ImageIdempotencyConflictError(ImageServiceError):
    pass


class ImageStateConflictError(ImageServiceError):
    pass


@dataclass(frozen=True)
class ImageValidationClaim:
    outcome: str
    event_id: str
    image_id: str
    expected_state_version: int
    trace_id: str
    series_id: str | None = None
    storage_profile: str | None = None
    object_key: str | None = None
    object_version_id: str | None = None
    file_format: str | None = None
    declared_content_type: str | None = None
    expected_sha256: str | None = None
    expected_size_bytes: int | None = None
    lease_generation: int | None = None
    attempt_count: int | None = None


@dataclass(frozen=True)
class ImageValidationEventCandidate:
    event_id: str
    message: dict[str, Any]
    message_version: str
    trace_id: str


@dataclass(frozen=True)
class ImageObjectCandidate:
    image_id: str
    state_version: int
    series_id: str
    storage_profile: str
    object_key: str
    object_version_id: str | None
    file_format: str
    declared_content_type: str | None
    expected_sha256: str | None
    expected_size_bytes: int | None


@dataclass(frozen=True)
class ImageReadyReconcileCursor:
    """Frozen cursor lease and position facts used by the one-shot reconciler."""

    cursor_id: str
    state_version: int
    lease_generation: int
    last_ready_updated_at: datetime | None
    last_ready_image_id: str | None


@dataclass(frozen=True)
class ImageReadyReconcileCandidate:
    """Minimal ready-image pagination facts; object validation stays in the worker."""

    image_id: str
    updated_at: datetime


@dataclass(frozen=True)
class ImageUploadOperationCandidate:
    image_id: str
    state_version: int
    generation: int
    status: str
    storage_profile: str
    object_key: str
    upload_mode: str
    upload_session_ref: str | None
    expected_part_count: int | None
    declared_content_type: str | None


class ImageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_dal = SessionDal(db)
        self.study_dal = StudyDal(db)
        self.series_dal = SeriesDal(db)
        self.image_dal = ImageDal(db)
        self.object_reconcile_cursor_dal = ObjectReconcileCursorDal(db)
        self.outbox_dal = OutboxDal(db)
        self.study_service = StudyService(db)
        self.upload_workflow = ImageUploadWorkflow(self)

    @staticmethod
    def _response(image: Image) -> ImageResponse:
        try:
            projection, provenance = projection_fact_from_image(image)
        except ManifestContractError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        return ImageResponse.model_validate(image).model_copy(
            update={
                "projection": projection,
                "projection_provenance": ImageProjectionProvenance.model_validate(
                    provenance
                ),
            }
        )

    @staticmethod
    def _page_response(image: Image) -> ImagePageItemResponse:
        try:
            projection, provenance = projection_fact_from_image(image)
        except ManifestContractError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        return ImagePageItemResponse.model_validate(image).model_copy(
            update={
                "projection": projection,
                "projection_provenance": ImageProjectionProvenance.model_validate(
                    provenance
                ),
            }
        )

    async def create_uploading_image(
        self, *, payload: ImageCreate, requester_id: str
    ) -> ImageResponse:
        series = await self.series_dal.get_by_id(payload.series_id)
        if series is None:
            raise ImageNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise ImageNotFoundError("study_not_found")
        session = await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        if session.status != "processing" or study.status == "invalid":
            raise ImageStateConflictError("study_not_accepting_images")

        existing_object = await self.image_dal.get_by_object(
            storage_profile=payload.storage_profile, object_key=payload.object_key
        )
        if existing_object is not None:
            self._assert_create_match(existing_object, payload)
            return self._response(existing_object)

        latest = await self.image_dal.get_latest_logical(
            series_id=series.id, logical_image_key=payload.logical_image_key
        )
        if latest is not None and latest.status in {"uploading", "validating"}:
            raise ImageStateConflictError("image_version_in_progress")
        image_version_no = 1 if latest is None else latest.image_version_no + 1
        values: dict[str, Any] = {
            "series_id": series.id,
            "source_image_id": payload.source_image_id,
            "logical_image_key": payload.logical_image_key,
            "image_version_no": image_version_no,
            "supersedes_image_id": None,
            "source_manifest_json": payload.source_manifest,
            "sequence_no": payload.sequence_no,
            "image_role": payload.image_role,
            "image_kind": payload.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": payload.storage_profile,
            "object_key": payload.object_key,
            "file_format": payload.file_format,
            "upload_mode": payload.upload_mode,
            "upload_session_ref": payload.upload_session_ref,
            "expected_part_count": payload.expected_part_count,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": payload.projection,
            "technical_metadata_json": build_projection_metadata(
                payload.technical_metadata,
                source=PROJECTION_SOURCE_CALLER,
            ),
            "status": "uploading",
            "state_version": 0,
            "validation_lease_generation": 0,
            "validation_attempt_count": 0,
            "upload_expires_at": payload.upload_expires_at,
        }
        created = await self.image_dal.create_idempotent(values)
        if created is not None:
            return self._response(created)

        existing_object = await self.image_dal.get_by_object(
            storage_profile=payload.storage_profile, object_key=payload.object_key
        )
        if existing_object is not None:
            self._assert_create_match(existing_object, payload)
            return self._response(existing_object)
        raise ImageStateConflictError("image_version_conflict")

    async def get_image(
        self, *, image_id: str, requester_id: str
    ) -> ImageResponse:
        return self._response(
            await self._owned_image(image_id=image_id, requester_id=requester_id)
        )

    async def page_images(
        self, *, query: ImagePageQuery, requester_id: str
    ) -> ImagePageResult:
        series = await self.series_dal.get_by_id(query.series_id)
        if series is None:
            raise ImageNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise ImageNotFoundError("study_not_found")
        await self._owned_session(
            session_id=study.session_id,
            requester_id=requester_id,
        )
        rows, total = await self.image_dal.page_for_series(
            series_id=series.id,
            status=query.status,
            image_role=query.image_role,
            current_only=query.resolved_current_only,
            page=query.page,
            limit=query.page_size,
        )
        return ImagePageResult(
            data=[self._page_response(item) for item in rows],
            total=total,
            page=query.page,
            limit=query.page_size,
        )

    async def issue_direct_upload(
        self,
        *,
        payload: ImagePrepareUploadRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageUploadTicket:
        return await self.upload_workflow.issue_direct_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def issue_direct_replacement(
        self,
        *,
        payload: ImageReplaceRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageUploadTicket:
        return await self.upload_workflow.issue_direct_replacement(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def issue_multipart_upload(
        self,
        *,
        payload: ImagePrepareMultipartRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageMultipartUploadTicket:
        return await self.upload_workflow.issue_multipart_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def issue_multipart_replacement(
        self,
        *,
        payload: ImageReplaceMultipartRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageMultipartUploadTicket:
        return await self.upload_workflow.issue_multipart_replacement(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def issue_multipart_part_urls(
        self,
        *,
        payload: ImagePreparePartsRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageMultipartPartsResponse:
        return await self.upload_workflow.issue_multipart_part_urls(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def list_multipart_parts(
        self,
        *,
        payload: ImageListMultipartPartsRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> list[ImageMultipartPartReceipt]:
        return await self.upload_workflow.list_multipart_parts(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def complete_upload_workflow(
        self,
        *,
        payload: ImageCompleteUploadRequest,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageResponse:
        return await self.upload_workflow.complete_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def abort_upload_workflow(
        self,
        *,
        payload: ImageAbortCommand,
        requester_id: str,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ) -> ImageResponse:
        return await self.upload_workflow.abort_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
        )

    async def prepare_direct_upload(
        self,
        *,
        payload: ImagePrepareUploadRequest,
        requester_id: str,
        storage_profile: str,
        upload_expires_at: datetime,
    ) -> ImageResponse:
        profile = storage_profile.strip()
        if not profile or len(profile) > 40:
            raise ImageStateConflictError("image_storage_profile_invalid")
        series = await self.series_dal.get_by_id(payload.series_id)
        if series is None:
            raise ImageNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise ImageNotFoundError("study_not_found")
        session = await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        if session.status != "processing" or study.status == "invalid":
            raise ImageStateConflictError("study_not_accepting_images")

        try:
            current_ready = await self.image_dal.get_ready_logical(
                series_id=series.id,
                logical_image_key=payload.logical_image_key,
            )
        except ValueError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        if current_ready is not None:
            raise ImageStateConflictError("image_replace_required")
        latest = await self.image_dal.get_latest_logical(
            series_id=series.id,
            logical_image_key=payload.logical_image_key,
        )
        if latest is not None and latest.status == "uploading":
            self._assert_prepare_match(latest, payload, profile)
            refreshed = await self.image_dal.refresh_upload_expiry(
                image_id=latest.id,
                expected_version=latest.state_version,
                upload_expires_at=upload_expires_at,
            )
            if refreshed is None:
                raise ImageStateConflictError("image_prepare_conflict")
            return self._response(refreshed)
        if latest is not None and latest.status == "validating":
            raise ImageStateConflictError("image_validation_in_progress")

        image_version_no = 1 if latest is None else latest.image_version_no + 1
        image_id = new_opaque_id()
        object_key = OSSObjectStore.new_image_object_key(
            image_id=image_id,
            generation=image_version_no,
            file_format=payload.file_format,
        )
        values: dict[str, Any] = {
            "id": image_id,
            "series_id": series.id,
            "source_image_id": payload.source_image_id,
            "logical_image_key": payload.logical_image_key,
            "image_version_no": image_version_no,
            "supersedes_image_id": None,
            "source_manifest_json": payload.source_manifest,
            "sequence_no": payload.sequence_no,
            "image_role": payload.image_role,
            "image_kind": payload.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": profile,
            "object_key": object_key,
            "file_format": payload.file_format,
            "upload_mode": "direct_put",
            "upload_session_ref": None,
            "expected_part_count": None,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": payload.projection,
            "technical_metadata_json": build_projection_metadata(
                payload.technical_metadata,
                source=PROJECTION_SOURCE_CALLER,
            ),
            "status": "uploading",
            "state_version": 0,
            "validation_lease_generation": 0,
            "validation_attempt_count": 0,
            "upload_expires_at": upload_expires_at,
        }
        created = await self.image_dal.create_idempotent(values)
        if created is not None:
            return self._response(created)
        latest = await self.image_dal.get_latest_logical(
            series_id=series.id,
            logical_image_key=payload.logical_image_key,
        )
        if latest is None or latest.status != "uploading":
            raise ImageStateConflictError("image_prepare_race")
        self._assert_prepare_match(latest, payload, profile)
        return self._response(latest)

    async def prepare_multipart_upload(
        self,
        *,
        payload: ImagePrepareMultipartRequest,
        requester_id: str,
        storage_profile: str,
        upload_expires_at: datetime,
    ) -> ImageResponse:
        profile = storage_profile.strip()
        if not profile or len(profile) > 40:
            raise ImageStateConflictError("image_storage_profile_invalid")
        series = await self.series_dal.get_by_id(payload.series_id)
        if series is None:
            raise ImageNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise ImageNotFoundError("study_not_found")
        session = await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        if session.status != "processing" or study.status == "invalid":
            raise ImageStateConflictError("study_not_accepting_images")
        try:
            current_ready = await self.image_dal.get_ready_logical(
                series_id=series.id,
                logical_image_key=payload.logical_image_key,
            )
        except ValueError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        if current_ready is not None:
            raise ImageStateConflictError("image_replace_required")
        latest = await self.image_dal.get_latest_logical(
            series_id=series.id,
            logical_image_key=payload.logical_image_key,
        )
        if latest is not None and latest.status == "uploading":
            self._assert_multipart_prepare_match(latest, payload, profile)
            refreshed = await self.image_dal.refresh_upload_expiry(
                image_id=latest.id,
                expected_version=latest.state_version,
                upload_expires_at=upload_expires_at,
            )
            if refreshed is None:
                raise ImageStateConflictError("image_prepare_conflict")
            return self._response(refreshed)
        if latest is not None and latest.status == "validating":
            raise ImageStateConflictError("image_validation_in_progress")

        image_version_no = 1 if latest is None else latest.image_version_no + 1
        image_id = new_opaque_id()
        object_key = OSSObjectStore.new_image_object_key(
            image_id=image_id,
            generation=image_version_no,
            file_format=payload.file_format,
        )
        values: dict[str, Any] = {
            "id": image_id,
            "series_id": series.id,
            "source_image_id": payload.source_image_id,
            "logical_image_key": payload.logical_image_key,
            "image_version_no": image_version_no,
            "supersedes_image_id": None,
            "source_manifest_json": payload.source_manifest,
            "sequence_no": payload.sequence_no,
            "image_role": payload.image_role,
            "image_kind": payload.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": profile,
            "object_key": object_key,
            "file_format": payload.file_format,
            "upload_mode": "multipart",
            "upload_session_ref": None,
            "expected_part_count": payload.expected_part_count,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": payload.projection,
            "technical_metadata_json": build_projection_metadata(
                payload.technical_metadata,
                source=PROJECTION_SOURCE_CALLER,
            ),
            "status": "uploading",
            "state_version": 0,
            "validation_lease_generation": 0,
            "validation_attempt_count": 0,
            "upload_expires_at": upload_expires_at,
        }
        created = await self.image_dal.create_idempotent(values)
        if created is not None:
            return self._response(created)
        latest = await self.image_dal.get_latest_logical(
            series_id=series.id,
            logical_image_key=payload.logical_image_key,
        )
        if latest is None or latest.status != "uploading":
            raise ImageStateConflictError("image_prepare_race")
        self._assert_multipart_prepare_match(latest, payload, profile)
        return self._response(latest)

    async def prepare_direct_replacement(
        self,
        *,
        payload: ImageReplaceRequest,
        requester_id: str,
        storage_profile: str,
        upload_expires_at: datetime,
    ) -> ImageResponse:
        old = await self._owned_image(
            image_id=payload.old_image_id, requester_id=requester_id
        )
        if old.status != "ready" or old.state_version != payload.expected_state_version:
            raise ImageStateConflictError("image_replace_source_conflict")
        profile = storage_profile.strip()
        if profile != old.storage_profile:
            raise ImageStateConflictError("image_storage_profile_conflict")
        latest = await self.image_dal.get_latest_logical(
            series_id=old.series_id,
            logical_image_key=old.logical_image_key,
        )
        if latest is not None and latest.id != old.id:
            if latest.status == "uploading" and latest.supersedes_image_id == old.id:
                self._assert_replacement_match(latest, old, payload, profile)
                refreshed = await self.image_dal.refresh_upload_expiry(
                    image_id=latest.id,
                    expected_version=latest.state_version,
                    upload_expires_at=upload_expires_at,
                )
                if refreshed is None:
                    raise ImageStateConflictError("image_replace_prepare_conflict")
                return self._response(refreshed)
            if latest.status == "validating" and latest.supersedes_image_id == old.id:
                raise ImageStateConflictError("image_validation_in_progress")
            if not (
                latest.status == "quarantined"
                and latest.supersedes_image_id == old.id
            ):
                raise ImageStateConflictError("image_replace_source_stale")
        version = max(
            old.image_version_no,
            latest.image_version_no if latest is not None else old.image_version_no,
        ) + 1
        image_id = new_opaque_id()
        projection, projection_metadata = self._replacement_projection_values(
            old=old,
            projection=payload.projection,
            technical_metadata=payload.technical_metadata,
        )
        values: dict[str, Any] = {
            "id": image_id,
            "series_id": old.series_id,
            "source_image_id": payload.source_image_id or old.source_image_id,
            "logical_image_key": old.logical_image_key,
            "image_version_no": version,
            "supersedes_image_id": old.id,
            "source_manifest_json": old.source_manifest_json,
            "sequence_no": old.sequence_no,
            "image_role": old.image_role,
            "image_kind": old.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": profile,
            "object_key": OSSObjectStore.new_image_object_key(
                image_id=image_id,
                generation=version,
                file_format=payload.file_format,
            ),
            "file_format": payload.file_format,
            "upload_mode": "direct_put",
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": projection,
            "technical_metadata_json": projection_metadata,
            "status": "uploading",
            "state_version": 0,
            "validation_lease_generation": 0,
            "validation_attempt_count": 0,
            "upload_expires_at": upload_expires_at,
        }
        created = await self.image_dal.create_idempotent(values)
        if created is None:
            latest = await self.image_dal.get_latest_logical(
                series_id=old.series_id,
                logical_image_key=old.logical_image_key,
            )
            if latest is None or latest.supersedes_image_id != old.id:
                raise ImageStateConflictError("image_replace_prepare_race")
            self._assert_replacement_match(latest, old, payload, profile)
            created = latest
        return self._response(created)

    async def prepare_multipart_replacement(
        self,
        *,
        payload: ImageReplaceMultipartRequest,
        requester_id: str,
        storage_profile: str,
        upload_expires_at: datetime,
    ) -> ImageResponse:
        old = await self._owned_image(
            image_id=payload.old_image_id, requester_id=requester_id
        )
        if old.status != "ready" or old.state_version != payload.expected_state_version:
            raise ImageStateConflictError("image_replace_source_conflict")
        profile = storage_profile.strip()
        if profile != old.storage_profile:
            raise ImageStateConflictError("image_storage_profile_conflict")
        latest = await self.image_dal.get_latest_logical(
            series_id=old.series_id,
            logical_image_key=old.logical_image_key,
        )
        if latest is not None and latest.id != old.id:
            if latest.status == "uploading" and latest.supersedes_image_id == old.id:
                self._assert_replacement_match(
                    latest,
                    old,
                    payload,
                    profile,
                    upload_mode="multipart",
                    expected_part_count=payload.expected_part_count,
                )
                refreshed = await self.image_dal.refresh_upload_expiry(
                    image_id=latest.id,
                    expected_version=latest.state_version,
                    upload_expires_at=upload_expires_at,
                )
                if refreshed is None:
                    raise ImageStateConflictError("image_replace_prepare_conflict")
                return self._response(refreshed)
            if latest.status == "validating" and latest.supersedes_image_id == old.id:
                raise ImageStateConflictError("image_validation_in_progress")
            if not (
                latest.status == "quarantined"
                and latest.supersedes_image_id == old.id
            ):
                raise ImageStateConflictError("image_replace_source_stale")
        version = max(
            old.image_version_no,
            latest.image_version_no if latest is not None else old.image_version_no,
        ) + 1
        image_id = new_opaque_id()
        projection, projection_metadata = self._replacement_projection_values(
            old=old,
            projection=payload.projection,
            technical_metadata=payload.technical_metadata,
        )
        values: dict[str, Any] = {
            "id": image_id,
            "series_id": old.series_id,
            "source_image_id": payload.source_image_id or old.source_image_id,
            "logical_image_key": old.logical_image_key,
            "image_version_no": version,
            "supersedes_image_id": old.id,
            "source_manifest_json": old.source_manifest_json,
            "sequence_no": old.sequence_no,
            "image_role": old.image_role,
            "image_kind": old.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": profile,
            "object_key": OSSObjectStore.new_image_object_key(
                image_id=image_id,
                generation=version,
                file_format=payload.file_format,
            ),
            "file_format": payload.file_format,
            "upload_mode": "multipart",
            "upload_session_ref": None,
            "expected_part_count": payload.expected_part_count,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": projection,
            "technical_metadata_json": projection_metadata,
            "status": "uploading",
            "state_version": 0,
            "validation_lease_generation": 0,
            "validation_attempt_count": 0,
            "upload_expires_at": upload_expires_at,
        }
        created = await self.image_dal.create_idempotent(values)
        if created is None:
            latest = await self.image_dal.get_latest_logical(
                series_id=old.series_id,
                logical_image_key=old.logical_image_key,
            )
            if latest is None or latest.supersedes_image_id != old.id:
                raise ImageStateConflictError("image_replace_prepare_race")
            self._assert_replacement_match(
                latest,
                old,
                payload,
                profile,
                upload_mode="multipart",
                expected_part_count=payload.expected_part_count,
            )
            created = latest
        return self._response(created)

    async def bind_multipart_upload_session(
        self,
        *,
        image_id: str,
        requester_id: str,
        expected_state_version: int,
        generation: int | None,
        upload_session_ref: str,
        upload_expires_at: datetime,
    ) -> ImageResponse:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
        self._validate_upload_operation(
            image=image,
            expected_state_version=expected_state_version,
            generation=generation,
            required_mode="multipart",
        )
        if image.upload_session_ref:
            if image.upload_session_ref != upload_session_ref:
                raise ImageStateConflictError("multipart_upload_session_conflict")
            return self._response(image)
        updated = await self.image_dal.bind_multipart_upload_session(
            image_id=image.id,
            expected_version=expected_state_version,
            upload_session_ref=upload_session_ref,
            upload_expires_at=upload_expires_at,
        )
        if updated is None:
            raise ImageStateConflictError("multipart_upload_bind_conflict")
        return self._response(updated)

    async def get_upload_operation_candidate(
        self,
        *,
        image_id: str,
        requester_id: str,
        expected_state_version: int,
        generation: int | None,
        operation: str,
    ) -> ImageUploadOperationCandidate:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
        if generation is not None and image.image_version_no != generation:
            raise ImageStateConflictError("image_generation_conflict")
        if operation == "parts":
            if generation is None:
                raise ImageStateConflictError("image_generation_required")
            self._validate_upload_operation(
                image=image,
                expected_state_version=expected_state_version,
                generation=generation,
                required_mode="multipart",
            )
            if not image.upload_session_ref:
                raise ImageStateConflictError("multipart_upload_session_missing")
        elif operation == "list_parts":
            if generation is None:
                raise ImageStateConflictError("image_generation_required")
            self._validate_upload_operation(
                image=image,
                expected_state_version=expected_state_version,
                generation=generation,
                required_mode="multipart",
            )
            if not image.upload_session_ref:
                raise ImageStateConflictError("multipart_upload_session_missing")
        elif operation == "multipart_prepare":
            if generation is None:
                raise ImageStateConflictError("image_generation_required")
            self._validate_upload_operation(
                image=image,
                expected_state_version=expected_state_version,
                generation=generation,
                required_mode="multipart",
            )
        elif operation == "complete":
            if generation is None:
                raise ImageStateConflictError("image_generation_required")
            if image.status == "uploading":
                if image.state_version != expected_state_version:
                    raise ImageStateConflictError("image_upload_state_conflict")
                if image.upload_mode == "multipart" and not image.upload_session_ref:
                    raise ImageStateConflictError("multipart_upload_session_missing")
            elif image.status == "validating":
                if image.state_version != expected_state_version + 1:
                    raise ImageStateConflictError("image_complete_conflict")
            else:
                raise ImageStateConflictError("image_complete_conflict")
        elif operation == "abort":
            if image.status != "uploading" or image.state_version != expected_state_version:
                raise ImageStateConflictError("image_abort_conflict")
        else:
            raise ImageStateConflictError("image_upload_operation_invalid")
        if image.state_version not in {expected_state_version, expected_state_version + 1}:
            raise ImageStateConflictError("image_upload_state_conflict")
        return ImageUploadOperationCandidate(
            image_id=image.id,
            state_version=image.state_version,
            generation=image.image_version_no,
            status=image.status,
            storage_profile=image.storage_profile,
            object_key=image.object_key,
            upload_mode=image.upload_mode,
            upload_session_ref=image.upload_session_ref,
            expected_part_count=image.expected_part_count,
            declared_content_type=image.declared_content_type,
        )

    @staticmethod
    def validate_multipart_part_numbers(
        candidate: ImageUploadOperationCandidate, part_numbers: list[int]
    ) -> list[int]:
        expected = candidate.expected_part_count
        if candidate.upload_mode != "multipart" or expected is None:
            raise ImageStateConflictError("multipart_upload_contract_missing")
        if any(number < 1 or number > expected for number in part_numbers):
            raise ImageStateConflictError("multipart_part_number_invalid")
        return sorted(part_numbers)

    @staticmethod
    def build_multipart_completion_parts(
        candidate: ImageUploadOperationCandidate,
        receipts: list[ImageMultipartPartReceipt] | None,
    ) -> list[MultipartPart]:
        if candidate.upload_mode == "direct_put":
            if receipts:
                raise ImageStateConflictError("direct_upload_parts_forbidden")
            return []
        if candidate.upload_mode != "multipart" or candidate.expected_part_count is None:
            raise ImageStateConflictError("multipart_upload_contract_missing")
        if not receipts or len(receipts) != candidate.expected_part_count:
            raise ImageStateConflictError("multipart_part_count_mismatch")
        numbers = [item.part_number for item in receipts]
        if numbers != list(range(1, candidate.expected_part_count + 1)):
            raise ImageStateConflictError("multipart_part_manifest_invalid")
        return [
            MultipartPart(
                part_number=item.part_number,
                etag=item.etag,
                size_bytes=item.size_bytes,
            )
            for item in receipts
        ]

    @staticmethod
    def multipart_manifest_sha256(parts: list[MultipartPart]) -> str:
        import hashlib

        manifest = [
            {
                "part_number": item.part_number,
                "etag": item.etag,
                "size_bytes": item.size_bytes,
            }
            for item in parts
        ]
        return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()

    async def abort_upload(
        self,
        *,
        image_id: str,
        requester_id: str,
        expected_state_version: int,
        generation: int | None = None,
    ) -> ImageResponse:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
        if generation is not None and image.image_version_no != generation:
            raise ImageStateConflictError("image_generation_conflict")
        if image.status == "quarantined" and image.error_code == "upload_aborted":
            return self._response(image)
        if image.status != "uploading" or image.state_version != expected_state_version:
            raise ImageStateConflictError("image_abort_conflict")
        updated = await self.image_dal.cas_update(
            image_id=image.id,
            expected_version=expected_state_version,
            values={
                "status": "quarantined",
                "upload_session_ref": None,
                "error_code": "upload_aborted",
                "next_validation_at": None,
            },
        )
        if updated is None:
            raise ImageStateConflictError("image_state_conflict")
        return self._response(updated)

    async def accept_upload_complete(
        self,
        *,
        image_id: str,
        requester_id: str,
        expected_state_version: int,
        object_head: ObjectHead,
        trace_id: str,
        multipart_manifest_sha256: str | None = None,
    ) -> ImageResponse:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
        return await self._accept_upload_complete_for_image(
            image=image,
            expected_state_version=expected_state_version,
            object_head=object_head,
            trace_id=trace_id,
            multipart_manifest_sha256=multipart_manifest_sha256,
        )

    async def accept_reconciled_upload(
        self,
        *,
        image_id: str,
        expected_state_version: int,
        object_head: ObjectHead,
        trace_id: str,
        multipart_manifest_sha256: str | None = None,
    ) -> ImageResponse:
        image = await self.image_dal.get_by_id(image_id.strip())
        if image is None:
            raise ImageNotFoundError("image_not_found")
        return await self._accept_upload_complete_for_image(
            image=image,
            expected_state_version=expected_state_version,
            object_head=object_head,
            trace_id=trace_id,
            multipart_manifest_sha256=multipart_manifest_sha256,
        )

    async def _accept_upload_complete_for_image(
        self,
        *,
        image: Image,
        expected_state_version: int,
        object_head: ObjectHead,
        trace_id: str,
        multipart_manifest_sha256: str | None,
    ) -> ImageResponse:
        self._validate_head(image, object_head)
        if image.upload_mode == "multipart" and multipart_manifest_sha256 is not None:
            if len(multipart_manifest_sha256) != 64:
                raise ImageStateConflictError("multipart_manifest_sha256_invalid")
        elif image.upload_mode != "multipart" and multipart_manifest_sha256 is not None:
            raise ImageStateConflictError("direct_upload_manifest_forbidden")
        if image.status == "validating":
            if image.state_version != expected_state_version + 1:
                raise ImageStateConflictError("image_complete_conflict")
            if image.object_version_id != object_head.object_version_id:
                raise ImageStateConflictError("image_object_version_conflict")
            stored_manifest = (image.technical_metadata_json or {}).get(
                "multipart_manifest_sha256"
            )
            if multipart_manifest_sha256 is not None and (
                stored_manifest != multipart_manifest_sha256
            ):
                raise ImageStateConflictError("multipart_manifest_conflict")
            event_key = f"image:{image.id}:validate:{image.state_version}"
            existing = await self.outbox_dal.get_by_event_key(event_key)
            if existing is None:
                raise ImageStateConflictError("image_validation_event_missing")
            try:
                self.outbox_dal.validate_image_event(existing)
            except ValueError as exc:
                raise ImageStateConflictError("image_validation_event_conflict") from exc
            return self._response(image)
        if image.status != "uploading" or image.state_version != expected_state_version:
            raise ImageStateConflictError("image_complete_conflict")
        technical_metadata = dict(image.technical_metadata_json or {})
        if multipart_manifest_sha256 is not None:
            technical_metadata["multipart_manifest_sha256"] = (
                multipart_manifest_sha256
            )
        updated = await self.image_dal.cas_update(
            image_id=image.id,
            expected_version=expected_state_version,
            values={
                "status": "validating",
                "object_version_id": object_head.object_version_id,
                "upload_session_ref": None,
                "technical_metadata_json": technical_metadata,
                "next_validation_at": datetime.utcnow(),
                "error_code": None,
            },
        )
        if updated is None:
            raise ImageStateConflictError("image_state_conflict")
        normalized_trace_id = trace_id.strip()
        if not normalized_trace_id or len(normalized_trace_id) > 128:
            raise ImageStateConflictError("image_trace_id_invalid")
        message = {
            "image_id": updated.id,
            "expected_state_version": updated.state_version,
            "trace_id": normalized_trace_id,
        }
        event_key = f"image:{updated.id}:validate:{updated.state_version}"
        event_values = {
            "id": new_opaque_id(),
            "aggregate_type": "image",
            "aggregate_id": updated.id,
            "aggregate_version": updated.state_version,
            "event_key": event_key,
            "event_type": "validate_image",
            "destination_key": OutboxDal.IMAGE_DESTINATION_KEY,
            "trace_id": normalized_trace_id,
            "message_version": OutboxDal.IMAGE_MESSAGE_VERSION,
            "message_json": message,
            "message_sha256": OutboxDal.message_sha256(message),
            "publish_status": "pending",
            "publish_attempt_count": 0,
        }
        created_event = await self.outbox_dal.create_idempotent(event_values)
        if created_event is None:
            existing = await self.outbox_dal.get_by_event_key(event_key)
            try:
                existing_message = (
                    self.outbox_dal.validate_image_event(existing)
                    if existing is not None
                    else None
                )
            except ValueError as exc:
                raise ImageStateConflictError("image_validation_event_conflict") from exc
            if existing_message is None or existing_message.model_dump() != message:
                raise ImageStateConflictError("image_validation_event_conflict")
        return self._response(updated)

    async def recover_expired_validation_leases(
        self, *, now: datetime, limit: int, max_attempts: int
    ) -> dict[str, int]:
        rows = await self.image_dal.list_expired_validation_leases(
            now=now, limit=limit
        )
        recovered = 0
        quarantined = 0
        for image in rows:
            updated = await self.image_dal.recover_expired_validation_lease(
                image_id=image.id,
                expected_version=image.state_version,
                lease_generation=image.validation_lease_generation,
                now=now,
                max_attempts=max_attempts,
            )
            if updated is None:
                continue
            if updated.status == "quarantined":
                quarantined += 1
            else:
                recovered += 1
        return {"recovered": recovered, "quarantined": quarantined}

    async def list_validation_reconcile_events(
        self, *, now: datetime, limit: int
    ) -> list[ImageValidationEventCandidate]:
        rows = await self.image_dal.list_validation_candidates(now=now, limit=limit)
        candidates: list[ImageValidationEventCandidate] = []
        for image in rows:
            event_key = f"image:{image.id}:validate:{image.state_version}"
            event = await self.outbox_dal.get_by_event_key(event_key)
            if event is None:
                await self.image_dal.cas_update(
                    image_id=image.id,
                    expected_version=image.state_version,
                    values={
                        "status": "quarantined",
                        "error_code": "validation_event_missing",
                        "next_validation_at": None,
                    },
                )
                continue
            try:
                message = self.outbox_dal.validate_image_event(event)
            except ValueError:
                await self.image_dal.cas_update(
                    image_id=image.id,
                    expected_version=image.state_version,
                    values={
                        "status": "quarantined",
                        "error_code": "validation_event_invalid",
                        "next_validation_at": None,
                    },
                )
                continue
            if event.publish_status not in {"publishing", "published"}:
                continue
            candidates.append(
                ImageValidationEventCandidate(
                    event_id=event.id,
                    message=message.model_dump(),
                    message_version=event.message_version,
                    trace_id=event.trace_id,
                )
            )
        return candidates

    async def list_expired_upload_candidates(
        self, *, now: datetime, limit: int
    ) -> list[ImageObjectCandidate]:
        rows = await self.image_dal.list_expired_uploads(now=now, limit=limit)
        return [self._object_candidate(image) for image in rows]

    async def quarantine_expired_upload(
        self,
        *,
        image_id: str,
        expected_state_version: int,
        error_code: str,
        now: datetime,
    ) -> bool:
        image = await self.image_dal.get_by_id(image_id)
        if (
            image is None
            or image.status != "uploading"
            or image.state_version != expected_state_version
            or image.upload_expires_at is None
            or image.upload_expires_at > now
        ):
            return False
        updated = await self.image_dal.cas_update(
            image_id=image.id,
            expected_version=expected_state_version,
            values={
                "status": "quarantined",
                "upload_session_ref": None,
                "error_code": error_code.strip()[:80],
                "next_validation_at": None,
            },
        )
        return updated is not None

    async def get_ready_object_candidate(
        self, *, image_id: str
    ) -> ImageObjectCandidate | None:
        image = await self.image_dal.get_by_id(image_id.strip())
        if image is None or image.status != "ready":
            return None
        return self._object_candidate(image)

    async def claim_ready_reconcile_cursor(
        self,
        *,
        cursor_key: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> ImageReadyReconcileCursor | None:
        cursor = await self.object_reconcile_cursor_dal.get_by_key(cursor_key)
        if cursor is None:
            await self.object_reconcile_cursor_dal.create_idempotent(cursor_key)
        claimed = await self.object_reconcile_cursor_dal.claim(
            cursor_key=cursor_key,
            owner_id=owner_id,
            now=now,
            lease_expires_at=lease_expires_at,
        )
        return self._ready_reconcile_cursor(claimed) if claimed is not None else None

    async def list_ready_reconcile_candidates(
        self,
        *,
        cursor: ImageReadyReconcileCursor,
        limit: int,
    ) -> list[ImageReadyReconcileCandidate]:
        images = await self.image_dal.list_ready_after(
            updated_at=cursor.last_ready_updated_at,
            image_id=cursor.last_ready_image_id,
            limit=limit,
        )
        return [
            ImageReadyReconcileCandidate(
                image_id=image.id,
                updated_at=image.updated_at,
            )
            for image in images
        ]

    async def heartbeat_ready_reconcile_cursor(
        self,
        *,
        cursor: ImageReadyReconcileCursor,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        return await self.object_reconcile_cursor_dal.heartbeat(
            cursor_id=cursor.cursor_id,
            owner_id=owner_id,
            lease_generation=cursor.lease_generation,
            now=now,
            lease_expires_at=lease_expires_at,
        )

    async def advance_ready_reconcile_cursor(
        self,
        *,
        cursor: ImageReadyReconcileCursor,
        owner_id: str,
        now: datetime,
        last: ImageReadyReconcileCandidate | None,
        has_candidates: bool,
        next_scan_at: datetime,
    ) -> bool:
        advanced = await self.object_reconcile_cursor_dal.advance(
            cursor_id=cursor.cursor_id,
            expected_version=cursor.state_version,
            owner_id=owner_id,
            lease_generation=cursor.lease_generation,
            now=now,
            last_ready_updated_at=(
                last.updated_at
                if last is not None
                else (
                    cursor.last_ready_updated_at
                    if not has_candidates
                    else None
                )
            ),
            last_ready_image_id=(
                last.image_id
                if last is not None
                else (
                    cursor.last_ready_image_id
                    if not has_candidates
                    else None
                )
            ),
            next_scan_at=next_scan_at,
        )
        return advanced is not None

    async def invalidate_ready_image(
        self,
        *,
        image_id: str,
        expected_state_version: int,
        error_code: str,
        changed_at: datetime,
    ) -> bool:
        image = await self.image_dal.get_by_id(image_id)
        if (
            image is None
            or image.status != "ready"
            or image.state_version != expected_state_version
        ):
            return False
        series_id = image.series_id
        updated = await self.image_dal.cas_update(
            image_id=image.id,
            expected_version=expected_state_version,
            values={
                "status": "quarantined",
                "error_code": error_code.strip()[:80],
                "verified_at": None,
            },
        )
        if updated is None:
            return False
        try:
            await self.study_service.recompute_after_image_change(
                series_id=series_id,
                revision_reason="delete",
                changed_at=changed_at,
            )
        except StudyStateConflictError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        return True

    async def claim_validation_event(
        self,
        *,
        event_id: str,
        message: dict[str, Any],
        message_version: str,
        header_trace_id: str,
        owner_id: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
        max_attempts: int,
    ) -> ImageValidationClaim:
        try:
            received = ValidateImageMessage.model_validate(message)
        except ValueError as exc:
            raise ImageStateConflictError("image_validation_message_invalid") from exc
        expected_event_key = (
            f"image:{received.image_id}:validate:{received.expected_state_version}"
        )
        event = await self.outbox_dal.get_by_id(event_id.strip()) if event_id.strip() else None
        if event is None:
            event = await self.outbox_dal.get_by_event_key(expected_event_key)
        if event is None:
            raise ImageStateConflictError("image_validation_event_not_found")
        if event_id.strip() and event.id != event_id.strip():
            raise ImageStateConflictError("image_validation_event_identity_conflict")
        try:
            stored = self.outbox_dal.validate_image_event(event)
        except ValueError as exc:
            raise ImageStateConflictError("image_validation_event_conflict") from exc
        if stored.model_dump() != received.model_dump():
            raise ImageStateConflictError("image_validation_message_conflict")
        if message_version.strip() != event.message_version:
            raise ImageStateConflictError("image_validation_message_version_conflict")
        if header_trace_id.strip() != event.trace_id:
            raise ImageStateConflictError("image_validation_trace_conflict")
        if event.publish_status not in {"publishing", "published"}:
            raise ImageStateConflictError("image_validation_event_not_deliverable")

        image = await self.image_dal.get_by_id(received.image_id)
        if image is None:
            raise ImageNotFoundError("image_not_found")
        if image.state_version >= received.expected_state_version + 1:
            if image.status in {"ready", "superseded", "quarantined"}:
                return ImageValidationClaim(
                    outcome="already_applied",
                    event_id=event.id,
                    image_id=image.id,
                    expected_state_version=received.expected_state_version,
                    trace_id=received.trace_id,
                )
            raise ImageStateConflictError("image_validation_state_advanced")
        if (
            image.status != "validating"
            or image.state_version != received.expected_state_version
        ):
            raise ImageStateConflictError("image_validation_state_conflict")
        claimed_event_id = event.id
        claimed_image_id = image.id
        claimed_trace_id = received.trace_id
        claimed = await self.image_dal.claim_validation_lease(
            image_id=claimed_image_id,
            expected_version=received.expected_state_version,
            owner_id=owner_id,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            max_attempts=max_attempts,
        )
        if claimed is None:
            return ImageValidationClaim(
                outcome="lease_unavailable",
                event_id=claimed_event_id,
                image_id=claimed_image_id,
                expected_state_version=received.expected_state_version,
                trace_id=claimed_trace_id,
            )
        return ImageValidationClaim(
            outcome="claimed",
            event_id=claimed_event_id,
            image_id=claimed.id,
            expected_state_version=received.expected_state_version,
            trace_id=claimed_trace_id,
            series_id=claimed.series_id,
            storage_profile=claimed.storage_profile,
            object_key=claimed.object_key,
            object_version_id=claimed.object_version_id,
            file_format=claimed.file_format,
            declared_content_type=claimed.declared_content_type,
            expected_sha256=claimed.expected_sha256,
            expected_size_bytes=claimed.expected_size_bytes,
            lease_generation=claimed.validation_lease_generation,
            attempt_count=claimed.validation_attempt_count,
        )

    async def heartbeat_validation_claim(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        if claim.outcome != "claimed" or claim.lease_generation is None:
            raise ImageStateConflictError("image_validation_claim_invalid")
        return await self.image_dal.heartbeat_validation_lease(
            image_id=claim.image_id,
            expected_version=claim.expected_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )

    async def release_validation_retry(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        released_at: datetime,
        next_validation_at: datetime,
        error_code: str,
    ) -> bool:
        if claim.outcome != "claimed" or claim.lease_generation is None:
            return False
        return await self.image_dal.release_validation_retry(
            image_id=claim.image_id,
            expected_version=claim.expected_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            released_at=released_at,
            next_validation_at=next_validation_at,
            error_code=error_code,
        )

    async def quarantine_validation(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        error_code: str,
        finished_at: datetime,
    ) -> ImageResponse | None:
        if claim.outcome != "claimed" or claim.lease_generation is None:
            return None
        updated = await self.image_dal.finalize_validation(
            image_id=claim.image_id,
            expected_version=claim.expected_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            finished_at=finished_at,
            values={
                "status": "quarantined",
                "error_code": error_code.strip()[:80],
                "verified_at": None,
            },
        )
        return self._response(updated) if updated is not None else None

    async def complete_validation(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        validation: ObjectValidation,
        finished_at: datetime,
    ) -> ImageResponse:
        if (
            claim.outcome != "claimed"
            or claim.lease_generation is None
            or claim.series_id is None
        ):
            raise ImageStateConflictError("image_validation_claim_invalid")
        image = await self.image_dal.get_by_id(claim.image_id)
        if image is None:
            raise ImageNotFoundError("image_not_found")
        if validation.object_ref.storage_profile != image.storage_profile:
            raise ImageStateConflictError("image_validation_storage_profile_conflict")
        if validation.object_ref.object_key != image.object_key:
            raise ImageStateConflictError("image_validation_object_key_conflict")
        old_image = None
        if image.supersedes_image_id:
            old_image = await self.image_dal.get_by_id(image.supersedes_image_id)
            if (
                old_image is None
                or old_image.status != "ready"
                or old_image.series_id != image.series_id
                or old_image.logical_image_key != image.logical_image_key
            ):
                raise ImageStateConflictError("image_replace_source_conflict")
        metadata = dict(image.technical_metadata_json or {})
        metadata.update(
            {
                "pixel_width": validation.inspection.pixel_width,
                "pixel_height": validation.inspection.pixel_height,
                "orientation": validation.inspection.orientation,
            }
        )
        old_image_identity = (
            (old_image.id, old_image.state_version) if old_image is not None else None
        )
        updated = await self.image_dal.finalize_validation(
            image_id=claim.image_id,
            expected_version=claim.expected_state_version,
            owner_id=owner_id,
            lease_generation=claim.lease_generation,
            finished_at=finished_at,
            values={
                "object_version_id": validation.object_ref.object_version_id,
                "content_type": validation.object_ref.content_type,
                "sha256": validation.object_ref.sha256,
                "size_bytes": validation.object_ref.size_bytes,
                "kms_key_version": validation.object_ref.kms_key_version,
                "technical_metadata_json": metadata,
                "status": "ready",
                "error_code": None,
                "verified_at": finished_at,
            },
        )
        if updated is None:
            raise ImageStateConflictError("image_validation_lease_lost")
        updated_image_id = updated.id
        revision_reason = "replace" if updated.supersedes_image_id else "add"
        if old_image_identity is not None:
            old_image_id, old_image_state_version = old_image_identity
            superseded = await self.image_dal.cas_update(
                image_id=old_image_id,
                expected_version=old_image_state_version,
                values={"status": "superseded"},
            )
            if superseded is None:
                raise ImageStateConflictError("image_replace_source_cas_conflict")
        try:
            await self.study_service.recompute_after_image_change(
                series_id=claim.series_id,
                revision_reason=revision_reason,
                changed_at=finished_at,
            )
        except StudyStateConflictError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        refreshed = await self.image_dal.get_by_id(updated_image_id)
        if refreshed is None:
            raise ImageStateConflictError("image_validation_result_missing")
        return self._response(refreshed)

    async def _owned_image(self, *, image_id: str, requester_id: str) -> Image:
        image = await self.image_dal.get_by_id(image_id.strip())
        if image is None:
            raise ImageNotFoundError("image_not_found")
        series = await self.series_dal.get_by_id(image.series_id)
        if series is None:
            raise ImageNotFoundError("series_not_found")
        study = await self.study_dal.get_by_id(series.study_id)
        if study is None:
            raise ImageNotFoundError("study_not_found")
        await self._owned_session(
            session_id=study.session_id, requester_id=requester_id
        )
        return image

    async def _owned_session(self, *, session_id: str, requester_id: str):
        session = await self.session_dal.get_by_id(session_id.strip())
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.requester_id != requester_id.strip():
            raise SessionAccessDeniedError("session_access_denied")
        return session

    @staticmethod
    def _assert_create_match(image: Image, payload: ImageCreate) -> None:
        expected = {
            "series_id": payload.series_id,
            "source_image_id": payload.source_image_id,
            "logical_image_key": payload.logical_image_key,
            "source_manifest_json": payload.source_manifest,
            "sequence_no": payload.sequence_no,
            "image_role": payload.image_role,
            "image_kind": payload.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": payload.storage_profile,
            "object_key": payload.object_key,
            "file_format": payload.file_format,
            "upload_mode": payload.upload_mode,
            "expected_part_count": payload.expected_part_count,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": payload.projection,
            "technical_metadata_json": build_projection_metadata(
                payload.technical_metadata,
                source=PROJECTION_SOURCE_CALLER,
            ),
        }
        if any(getattr(image, field) != value for field, value in expected.items()):
            raise ImageIdempotencyConflictError("image_idempotency_conflict")

    @staticmethod
    def _assert_prepare_match(
        image: Image,
        payload: ImagePrepareUploadRequest,
        storage_profile: str,
        upload_mode: str = "direct_put",
    ) -> None:
        expected = {
            "series_id": payload.series_id,
            "source_image_id": payload.source_image_id,
            "logical_image_key": payload.logical_image_key,
            "source_manifest_json": payload.source_manifest,
            "sequence_no": payload.sequence_no,
            "image_role": payload.image_role,
            "image_kind": payload.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": storage_profile,
            "file_format": payload.file_format,
            "upload_mode": upload_mode,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": payload.projection,
            "technical_metadata_json": build_projection_metadata(
                payload.technical_metadata,
                source=PROJECTION_SOURCE_CALLER,
            ),
        }
        if any(getattr(image, field) != value for field, value in expected.items()):
            raise ImageIdempotencyConflictError("image_idempotency_conflict")

    @staticmethod
    def _assert_multipart_prepare_match(
        image: Image,
        payload: ImagePrepareMultipartRequest,
        storage_profile: str,
    ) -> None:
        ImageService._assert_prepare_match(
            image, payload, storage_profile, upload_mode="multipart"
        )
        if (
            image.upload_mode != "multipart"
            or image.expected_part_count != payload.expected_part_count
        ):
            raise ImageIdempotencyConflictError("image_idempotency_conflict")

    @staticmethod
    def _assert_replacement_match(
        image: Image,
        old: Image,
        payload: ImageReplaceRequest,
        storage_profile: str,
        upload_mode: str = "direct_put",
        expected_part_count: int | None = None,
    ) -> None:
        projection, projection_metadata = ImageService._replacement_projection_values(
            old=old,
            projection=payload.projection,
            technical_metadata=payload.technical_metadata,
        )
        expected = {
            "series_id": old.series_id,
            "source_image_id": payload.source_image_id or old.source_image_id,
            "logical_image_key": old.logical_image_key,
            "supersedes_image_id": old.id,
            "sequence_no": old.sequence_no,
            "image_role": old.image_role,
            "image_kind": old.image_kind,
            "metadata_schema_version": payload.metadata_schema_version,
            "storage_profile": storage_profile,
            "file_format": payload.file_format,
            "upload_mode": upload_mode,
            "expected_sha256": payload.expected_sha256,
            "expected_size_bytes": payload.expected_size_bytes,
            "declared_content_type": payload.declared_content_type,
            "projection": projection,
            "technical_metadata_json": projection_metadata,
        }
        if any(getattr(image, field) != value for field, value in expected.items()):
            raise ImageIdempotencyConflictError("image_idempotency_conflict")
        if image.expected_part_count != expected_part_count:
            raise ImageIdempotencyConflictError("image_idempotency_conflict")

    @staticmethod
    def _replacement_projection_values(
        *,
        old: Image,
        projection: str | None,
        technical_metadata: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        if projection is not None:
            source = PROJECTION_SOURCE_CALLER
            resolved_projection = projection
        else:
            try:
                resolved_projection, inherited = projection_fact_from_image(old)
            except ManifestContractError as exc:
                raise ImageStateConflictError(str(exc)) from exc
            source = inherited["source"]
        try:
            metadata = build_projection_metadata(
                technical_metadata,
                source=source,
            )
        except ManifestContractError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        return resolved_projection, metadata

    @staticmethod
    def _validate_upload_operation(
        *,
        image: Image,
        expected_state_version: int,
        generation: int,
        required_mode: str,
    ) -> None:
        if image.image_version_no != generation:
            raise ImageStateConflictError("image_generation_conflict")
        if image.upload_mode != required_mode:
            raise ImageStateConflictError("image_upload_mode_conflict")
        if image.status != "uploading" or image.state_version != expected_state_version:
            raise ImageStateConflictError("image_upload_state_conflict")

    @staticmethod
    def _validate_head(image: Image, head: ObjectHead) -> None:
        if head.storage_profile != image.storage_profile or head.object_key != image.object_key:
            raise ImageStateConflictError("image_object_identity_conflict")
        if head.size_bytes <= 0:
            raise ImageStateConflictError("image_object_empty")
        if image.expected_size_bytes is not None and head.size_bytes != image.expected_size_bytes:
            raise ImageStateConflictError("image_object_size_conflict")
        if (
            image.declared_content_type
            and head.content_type
            and image.declared_content_type.casefold() != head.content_type.casefold()
        ):
            raise ImageStateConflictError("image_object_content_type_conflict")

    @staticmethod
    def _object_candidate(image: Image) -> ImageObjectCandidate:
        return ImageObjectCandidate(
            image_id=image.id,
            state_version=image.state_version,
            series_id=image.series_id,
            storage_profile=image.storage_profile,
            object_key=image.object_key,
            object_version_id=image.object_version_id,
            file_format=image.file_format,
            declared_content_type=image.declared_content_type,
            expected_sha256=image.sha256 or image.expected_sha256,
            expected_size_bytes=image.size_bytes or image.expected_size_bytes,
        )

    @staticmethod
    def _ready_reconcile_cursor(
        cursor: ObjectReconcileCursor,
    ) -> ImageReadyReconcileCursor:
        return ImageReadyReconcileCursor(
            cursor_id=cursor.id,
            state_version=cursor.state_version,
            lease_generation=cursor.lease_generation,
            last_ready_updated_at=cursor.last_ready_updated_at,
            last_ready_image_id=cursor.last_ready_image_id,
        )


__all__ = [
    "ImageIdempotencyConflictError",
    "ImageNotFoundError",
    "ImageService",
    "ImageServiceError",
    "ImageStateConflictError",
    "ImageValidationClaim",
    "ImageValidationEventCandidate",
    "ImageObjectCandidate",
    "ImageReadyReconcileCandidate",
    "ImageReadyReconcileCursor",
    "ImageUploadOperationCandidate",
]
