"""Non-sensitive operational status for online and Evaluation control planes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.backend.services.runtime.admin_api.endpoints.control_plane_errors import (
    rollback_and_map_control_plane,
)
from apps.backend.core.dependencies import require_control_plane_scope
from apps.backend.core.async_db import get_async_session, get_evaluation_async_session
from apps.backend.core.config import settings
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.readiness import build_readiness
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.operations import OperationalStatusResponse
from apps.backend.services.runtime.service.operational_status_service import OperationalStatusService


router = APIRouter(prefix="/operations", tags=["Operational ControlPlane"])
control = require_control_plane_scope(settings.ADMIN_REQUIRED_SCOPE)


async def get_service(
    online_db: AsyncSession = Depends(get_async_session),
    evaluation_db: AsyncSession = Depends(get_evaluation_async_session),
) -> OperationalStatusService:
    return OperationalStatusService(
        online_db=online_db,
        evaluation_db=evaluation_db,
    )


@router.get("/status", response_model=GenericResponse[OperationalStatusResponse])
async def get_operational_status(
    request: Request,
    _: ControlPlaneContext = Depends(control),
    service: OperationalStatusService = Depends(get_service),
    online_db: AsyncSession = Depends(get_async_session),
    evaluation_db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        readiness = await build_readiness(request.app.state.redis_manager)
        data = await service.snapshot(readiness=readiness)
    except Exception as exc:
        await online_db.rollback()
        return await rollback_and_map_control_plane(evaluation_db, exc)
    return GenericResponse(message="运行状态查询成功", data=data)


__all__ = ["router"]
