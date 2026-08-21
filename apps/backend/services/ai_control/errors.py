"""AI Control API error mapping."""

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.ai_control.service.ai_config_service import (
    AIConfigNotFoundError,
    AIConfigStateConflictError,
    AIConfigValidationError,
)
from apps.backend.schemas.base import GenericResponse


def _response(status_code: int, error_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=GenericResponse(
            success=False,
            message=message,
            data=None,
            error_code=error_code,
        ).model_dump(),
    )


async def rollback_and_map_control_plane(
    db: AsyncSession,
    exc: Exception,
) -> JSONResponse:
    """Rollback one AI Control request and return its stable public error."""
    await db.rollback()
    if isinstance(exc, SQLAlchemyError):
        return _response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, AIConfigNotFoundError):
        return _response(404, 4041, "AI Config 不存在")
    if isinstance(exc, AIConfigValidationError):
        return _response(422, 4221, "AI Config 合同无效")
    if isinstance(exc, AIConfigStateConflictError):
        return _response(409, 4091, "AI Config 状态冲突")
    raise exc


__all__ = ["rollback_and_map_control_plane"]
