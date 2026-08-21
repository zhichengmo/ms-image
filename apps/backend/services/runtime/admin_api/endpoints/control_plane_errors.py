from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.base import GenericResponse
from apps.backend.services.runtime.service.report_service import ReportNotFoundError, ReportStateConflictError


def _response(status_code: int, error_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=GenericResponse(success=False, message=message, data=None, error_code=error_code).model_dump(),
    )


async def rollback_and_map_control_plane(db: AsyncSession, exc: Exception) -> JSONResponse:
    await db.rollback()
    if isinstance(exc, SQLAlchemyError):
        return _response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, ReportNotFoundError):
        return _response(404, 4042, "Report 不存在")
    if isinstance(exc, ReportStateConflictError):
        return _response(409, 4092, "Report 状态冲突")
    raise exc


__all__ = ["rollback_and_map_control_plane"]
