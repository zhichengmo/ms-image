"""AI Control API error mapping."""

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.base import GenericResponse
from apps.backend.services.ai_control.service.errors import (
    AIControlNotFoundError,
    AIControlStateConflictError,
    AIControlValidationError,
)

# The v1 Config service is intentionally still importable during the v1/v2
# compatibility window.  Its legacy exception classes remain mapped until the
# service is replaced by the v2 compiler implementation.
from apps.backend.services.ai_control.service.ai_config_service import (
    AIConfigNotFoundError,
    AIConfigStateConflictError,
    AIConfigValidationError,
)


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
    """Rollback the request transaction and map stable control-plane errors."""
    await db.rollback()
    if isinstance(exc, SQLAlchemyError):
        return _response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, (AIControlNotFoundError, AIConfigNotFoundError)):
        return _response(404, 4041, "AI 控制面资源不存在")
    if isinstance(exc, (AIControlValidationError, AIConfigValidationError)):
        return _response(422, 4221, "AI 控制面合同无效")
    if isinstance(exc, (AIControlStateConflictError, AIConfigStateConflictError)):
        return _response(409, 4091, "AI 控制面状态冲突")
    raise exc


__all__ = ["rollback_and_map_control_plane"]
