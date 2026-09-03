from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.imaging.object_store import ObjectStoreError
from apps.backend.schemas.base import GenericResponse
from apps.backend.services.runtime.service.image_service import (
    ImageIdempotencyConflictError,
    ImageNotFoundError,
    ImageStateConflictError,
)
from apps.backend.services.runtime.service.session_service import (
    SessionAccessDeniedError,
    SessionIdempotencyConflictError,
    SessionNotFoundError,
    SessionStateConflictError,
)
from apps.backend.services.runtime.service.study_service import (
    SeriesNotFoundError,
    StudyIdempotencyConflictError,
    StudyNotFoundError,
    StudyStateConflictError,
)
from apps.backend.services.runtime.service.task_service import (
    TaskAccessDeniedError,
    TaskIdempotencyConflictError,
    TaskNotFoundError,
    TaskStateConflictError,
)
from apps.backend.services.runtime.service.pet_profile_service import (
    PetProfileAccessDeniedError,
    PetProfileIdempotencyConflictError,
    PetProfileNotFoundError,
    PetProfileStateConflictError,
)
from apps.backend.services.runtime.service.report_service import ReportNotFoundError, ReportStateConflictError


def _response(status_code: int, error_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=GenericResponse(
            success=False, message=message, data=None, error_code=error_code
        ).model_dump(),
    )


async def rollback_and_map(db: AsyncSession, exc: Exception) -> JSONResponse:
    await db.rollback()
    if isinstance(exc, SQLAlchemyError):
        return _response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, ObjectStoreError):
        return _response(503, 5032, "对象存储暂不可用")
    if isinstance(exc, SessionAccessDeniedError):
        return _response(404, 4041, "资源不存在")
    if isinstance(
        exc,
        (
            SessionNotFoundError,
            StudyNotFoundError,
            SeriesNotFoundError,
            ImageNotFoundError,
            TaskNotFoundError,
            TaskAccessDeniedError,
            ReportNotFoundError,
            PetProfileNotFoundError,
            PetProfileAccessDeniedError,
        ),
    ):
        return _response(404, 4041, "资源不存在")
    if isinstance(
        exc,
        (
            SessionIdempotencyConflictError,
            StudyIdempotencyConflictError,
            ImageIdempotencyConflictError,
            TaskIdempotencyConflictError,
            PetProfileIdempotencyConflictError,
        ),
    ):
        return _response(409, 4091, "幂等请求内容冲突")
    if isinstance(
        exc,
        (
            SessionStateConflictError,
            StudyStateConflictError,
            ImageStateConflictError,
            TaskStateConflictError,
            ReportStateConflictError,
            PetProfileStateConflictError,
        )
    ):
        return _response(409, 4092, "资源状态冲突")
    raise exc


__all__ = ["rollback_and_map"]
