from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.imaging.object_store import ObjectHead, ObjectValidation
from app.crud.image import ImageDal
from app.crud.outbox import OutboxDal
from app.crud.series import SeriesDal
from app.crud.session import SessionDal
from app.crud.study import StudyDal
from app.models.image import Image
from app.models.imaging_base import new_opaque_id
from app.schemas.image import ImageCreate, ImageResponse
from app.schemas.outbox import ValidateImageMessage
from app.service.session_service import SessionAccessDeniedError, SessionNotFoundError
from app.service.study_service import StudyService, StudyStateConflictError


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


class ImageService:
    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)
        self.study_dal = StudyDal(db)
        self.series_dal = SeriesDal(db)
        self.image_dal = ImageDal(db)
        self.outbox_dal = OutboxDal(db)
        self.study_service = StudyService(db)

    @staticmethod
    def _response(image: Image) -> ImageResponse:
        return ImageResponse.model_validate(image)

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
            "technical_metadata_json": payload.technical_metadata,
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

    async def abort_upload(
        self,
        *,
        image_id: str,
        requester_id: str,
        expected_state_version: int,
    ) -> ImageResponse:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
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
    ) -> ImageResponse:
        image = await self._owned_image(image_id=image_id, requester_id=requester_id)
        self._validate_head(image, object_head)
        if image.status == "validating":
            if image.state_version != expected_state_version + 1:
                raise ImageStateConflictError("image_complete_conflict")
            if image.object_version_id != object_head.object_version_id:
                raise ImageStateConflictError("image_object_version_conflict")
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
        updated = await self.image_dal.cas_update(
            image_id=image.id,
            expected_version=expected_state_version,
            values={
                "status": "validating",
                "object_version_id": object_head.object_version_id,
                "upload_session_ref": None,
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
        claimed = await self.image_dal.claim_validation_lease(
            image_id=image.id,
            expected_version=received.expected_state_version,
            owner_id=owner_id,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            max_attempts=max_attempts,
        )
        if claimed is None:
            return ImageValidationClaim(
                outcome="lease_unavailable",
                event_id=event.id,
                image_id=image.id,
                expected_state_version=received.expected_state_version,
                trace_id=received.trace_id,
            )
        return ImageValidationClaim(
            outcome="claimed",
            event_id=event.id,
            image_id=claimed.id,
            expected_state_version=received.expected_state_version,
            trace_id=received.trace_id,
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
        metadata = dict(image.technical_metadata_json or {})
        metadata.update(
            {
                "pixel_width": validation.inspection.pixel_width,
                "pixel_height": validation.inspection.pixel_height,
                "orientation": validation.inspection.orientation,
            }
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
        try:
            await self.study_service.recompute_after_image_change(
                series_id=claim.series_id,
                revision_reason="replace" if updated.supersedes_image_id else "add",
                changed_at=finished_at,
            )
        except StudyStateConflictError as exc:
            raise ImageStateConflictError(str(exc)) from exc
        return self._response(updated)

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
            "technical_metadata_json": payload.technical_metadata,
        }
        if any(getattr(image, field) != value for field, value in expected.items()):
            raise ImageIdempotencyConflictError("image_idempotency_conflict")

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


__all__ = [
    "ImageIdempotencyConflictError",
    "ImageNotFoundError",
    "ImageService",
    "ImageServiceError",
    "ImageStateConflictError",
    "ImageValidationClaim",
]
