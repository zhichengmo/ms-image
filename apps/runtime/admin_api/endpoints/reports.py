from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.admin_api.endpoints.control_plane_errors import rollback_and_map_control_plane
from apps.runtime.api.deps import get_async_session, require_control_plane_scope
from apps.runtime.core.contexts import ControlPlaneContext
from apps.runtime.schemas.base import GenericResponse
from apps.runtime.schemas.report import ReportResponse, ReportStateRequest
from apps.runtime.service.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Report ControlPlane"])
control = require_control_plane_scope()

async def get_report_service(db: AsyncSession = Depends(get_async_session)) -> ReportService:
    return ReportService(db)

@router.post("/publish", response_model=GenericResponse[ReportResponse])
async def publish(payload: ReportStateRequest, _: ControlPlaneContext = Depends(control), service: ReportService = Depends(get_report_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.publish(report_id=payload.id, expected_version=payload.expected_state_version)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Report 已发布", data=data)

@router.post("/void", response_model=GenericResponse[ReportResponse])
async def void(payload: ReportStateRequest, _: ControlPlaneContext = Depends(control), service: ReportService = Depends(get_report_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.void(report_id=payload.id, expected_version=payload.expected_state_version)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Report 已作废", data=data)
