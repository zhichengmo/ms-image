from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.imaging.object_store import ObjectStoreError
from app.schemas.base import GenericResponse
from app.service.image_service import (
    ImageIdempotencyConflictError,
    ImageNotFoundError,
    ImageStateConflictError,
)
from app.service.session_service import (
    SessionAccessDeniedError,
    SessionIdempotencyConflictError,
    SessionNotFoundError,
    SessionStateConflictError,
)
from app.service.study_service import (
    SeriesNotFoundError,
    StudyIdempotencyConflictError,
    StudyNotFoundError,
    StudyStateConflictError,
)


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
        exc, (SessionNotFoundError, StudyNotFoundError, SeriesNotFoundError, ImageNotFoundError)
    ):
        return _response(404, 4041, "资源不存在")
    if isinstance(
        exc,
        (
            SessionIdempotencyConflictError,
            StudyIdempotencyConflictError,
            ImageIdempotencyConflictError,
        ),
    ):
        return _response(409, 4091, "幂等请求内容冲突")
    if isinstance(
        exc, (SessionStateConflictError, StudyStateConflictError, ImageStateConflictError)
    ):
        return _response(409, 4092, "资源状态冲突")
    raise exc


__all__ = ["rollback_and_map"]
