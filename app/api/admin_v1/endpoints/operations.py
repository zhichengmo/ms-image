"""Non-sensitive operational status for online and Evaluation control planes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_v1.endpoints.control_plane_errors import (
    rollback_and_map_control_plane,
)
from app.api.deps import require_control_plane_scope
from app.core.async_db import get_async_session, get_evaluation_async_session
from app.core.config import settings
from app.core.contexts import ControlPlaneContext
from app.schemas.base import GenericResponse
from app.schemas.operations import OperationalStatusResponse
from app.service.operational_status_service import OperationalStatusService


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
    _: ControlPlaneContext = Depends(control),
    service: OperationalStatusService = Depends(get_service),
    online_db: AsyncSession = Depends(get_async_session),
    evaluation_db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.snapshot()
    except Exception as exc:
        await online_db.rollback()
        return await rollback_and_map_control_plane(evaluation_db, exc)
    return GenericResponse(message="运行状态查询成功", data=data)


__all__ = ["router"]
