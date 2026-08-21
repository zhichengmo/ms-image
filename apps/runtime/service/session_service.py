from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.crud.session import SessionDal
from apps.runtime.models.session import Session
from apps.runtime.schemas.session import SessionCreate, SessionResponse


class SessionServiceError(ValueError):
    pass


class SessionNotFoundError(SessionServiceError):
    pass


class SessionAccessDeniedError(SessionServiceError):
    pass


class SessionIdempotencyConflictError(SessionServiceError):
    pass


class SessionStateConflictError(SessionServiceError):
    pass


class SessionService:
    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)
        self._db = db

    @staticmethod
    def _response(session: Session) -> SessionResponse:
        return SessionResponse.model_validate(session)

    @staticmethod
    def _immutable_values(payload: SessionCreate, requester_id: str) -> dict[str, Any]:
        return {
            **payload.model_dump(),
            "requester_id": requester_id,
            "status": "open",
            "state_version": 0,
        }

    @staticmethod
    def _matches_create(session: Session, values: dict[str, Any]) -> bool:
        immutable_fields = (
            "source_system",
            "source_session_id",
            "source_medical_record_id",
            "subject_id",
            "requester_id",
            "started_at",
        )
        return all(getattr(session, field) == values[field] for field in immutable_fields)

    async def create_session(
        self, *, payload: SessionCreate, requester_id: str
    ) -> SessionResponse:
        requester_id = requester_id.strip()
        if not requester_id or len(requester_id) > 128:
            raise SessionAccessDeniedError("session_requester_invalid")
        values = self._immutable_values(payload, requester_id)

        existing = await self.session_dal.get_by_request_id(payload.request_id)
        if existing is None:
            existing = await self.session_dal.get_by_source(
                source_system=payload.source_system,
                source_session_id=payload.source_session_id,
            )
        if existing is not None:
            if not self._matches_create(existing, values):
                raise SessionIdempotencyConflictError("session_idempotency_conflict")
            return self._response(existing)

        created = await self.session_dal.create_idempotent(values)
        if created is not None:
            return self._response(created)

        existing = await self.session_dal.get_by_request_id(payload.request_id)
        if existing is None:
            existing = await self.session_dal.get_by_source(
                source_system=payload.source_system,
                source_session_id=payload.source_session_id,
            )
        if existing is None:
            raise SessionStateConflictError("session_create_race")
        if not self._matches_create(existing, values):
            raise SessionIdempotencyConflictError("session_idempotency_conflict")
        return self._response(existing)

    async def get_session(
        self, *, session_id: str, requester_id: str
    ) -> SessionResponse:
        return self._response(
            await self._owned_session(session_id=session_id, requester_id=requester_id)
        )

    async def mark_processing(
        self, *, session_id: str, requester_id: str, expected_state_version: int
    ) -> SessionResponse:
        session = await self._owned_session(
            session_id=session_id, requester_id=requester_id
        )
        if session.status == "processing" and session.state_version in {
            expected_state_version,
            expected_state_version + 1,
        }:
            return self._response(session)
        if session.status != "open" or session.state_version != expected_state_version:
            raise SessionStateConflictError("session_state_conflict")
        updated = await self.session_dal.cas_update(
            session_id=session.id,
            expected_version=expected_state_version,
            values={"status": "processing"},
        )
        if updated is None:
            raise SessionStateConflictError("session_state_conflict")
        return self._response(updated)

    async def complete_session(
        self,
        *,
        session_id: str,
        requester_id: str,
        expected_state_version: int,
    ) -> SessionResponse:
        from apps.runtime.crud.image import ImageDal
        from apps.runtime.crud.series import SeriesDal
        from apps.runtime.crud.study import StudyDal

        session = await self._owned_session(
            session_id=session_id, requester_id=requester_id
        )
        if session.status == "completed":
            return self._response(session)
        if session.status != "processing" or session.state_version != expected_state_version:
            raise SessionStateConflictError("session_state_conflict")
        studies = await StudyDal(self._db).list_for_session(session.id)
        if not studies:
            raise SessionStateConflictError("session_study_required")
        series_dal = SeriesDal(self._db)
        image_dal = ImageDal(self._db)
        for study in studies:
            if study.status in {"ingesting", "validating"}:
                raise SessionStateConflictError("session_children_active")
            for series in await series_dal.list_for_study(study.id):
                images = await image_dal.list_for_series(series.id)
                if any(image.status in {"uploading", "validating"} for image in images):
                    raise SessionStateConflictError("session_children_active")
        updated = await self.session_dal.cas_update(
            session_id=session.id,
            expected_version=expected_state_version,
            values={"status": "completed", "completed_at": datetime.utcnow()},
        )
        if updated is None:
            raise SessionStateConflictError("session_state_conflict")
        return self._response(updated)

    async def cancel_session(
        self,
        *,
        session_id: str,
        requester_id: str,
        expected_state_version: int,
        cancel_reason: str,
    ) -> SessionResponse:
        from apps.runtime.crud.image import ImageDal
        from apps.runtime.crud.series import SeriesDal
        from apps.runtime.crud.study import StudyDal

        session = await self._owned_session(
            session_id=session_id, requester_id=requester_id
        )
        if session.status == "cancelled":
            if session.cancel_reason == cancel_reason:
                return self._response(session)
            raise SessionStateConflictError("session_cancel_conflict")
        if session.status not in {"open", "processing"} or session.state_version != expected_state_version:
            raise SessionStateConflictError("session_state_conflict")
        if session.status == "processing":
            series_dal = SeriesDal(self._db)
            image_dal = ImageDal(self._db)
            for study in await StudyDal(self._db).list_for_session(session.id):
                for series in await series_dal.list_for_study(study.id):
                    images = await image_dal.list_for_series(series.id)
                    if any(image.status in {"uploading", "validating"} for image in images):
                        raise SessionStateConflictError("session_children_must_be_closed")
        normalized_reason = cancel_reason.strip()
        if not normalized_reason or len(normalized_reason) > 200:
            raise SessionStateConflictError("session_cancel_reason_invalid")
        updated = await self.session_dal.cas_update(
            session_id=session.id,
            expected_version=expected_state_version,
            values={
                "status": "cancelled",
                "cancelled_by_id": requester_id,
                "cancel_reason": normalized_reason,
                "cancelled_at": datetime.utcnow(),
            },
        )
        if updated is None:
            raise SessionStateConflictError("session_state_conflict")
        return self._response(updated)

    async def close_session(
        self,
        *,
        session_id: str,
        requester_id: str,
        expected_state_version: int,
    ) -> SessionResponse:
        session = await self._owned_session(
            session_id=session_id, requester_id=requester_id
        )
        if session.status == "closed":
            return self._response(session)
        if session.status != "completed" or session.state_version != expected_state_version:
            raise SessionStateConflictError("session_state_conflict")
        updated = await self.session_dal.cas_update(
            session_id=session.id,
            expected_version=expected_state_version,
            values={"status": "closed", "closed_at": datetime.utcnow()},
        )
        if updated is None:
            raise SessionStateConflictError("session_state_conflict")
        return self._response(updated)

    async def _owned_session(self, *, session_id: str, requester_id: str) -> Session:
        session = await self.session_dal.get_by_id(session_id.strip())
        if session is None:
            raise SessionNotFoundError("session_not_found")
        if session.requester_id != requester_id.strip():
            raise SessionAccessDeniedError("session_access_denied")
        return session


__all__ = [
    "SessionAccessDeniedError",
    "SessionIdempotencyConflictError",
    "SessionNotFoundError",
    "SessionService",
    "SessionServiceError",
    "SessionStateConflictError",
]
