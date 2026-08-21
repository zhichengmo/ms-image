from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.runtime.api.deps import get_async_session, require_caller_scope
from apps.runtime.config import settings
from apps.runtime.core.contexts import CallerContext
from apps.runtime.schemas.base import GenericResponse
from apps.runtime.schemas.report import ReportResponse
from apps.runtime.service.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Imaging reports"])
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)

async def get_report_service(db: AsyncSession = Depends(get_async_session)) -> ReportService:
    return ReportService(db)

@router.get("", response_model=GenericResponse[ReportResponse])
async def get_report(report_id: str = Query(..., alias="id", min_length=1, max_length=64), context: CallerContext = Depends(caller), service: ReportService = Depends(get_report_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.get_for_requester(report_id=report_id, requester_id=context.subject_id)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Report 查询成功", data=data)

@router.get("/history", response_model=GenericResponse[list[ReportResponse]])
async def report_history(task_id: str = Query(..., min_length=1, max_length=64), context: CallerContext = Depends(caller), service: ReportService = Depends(get_report_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.list_for_requester(task_id=task_id, requester_id=context.subject_id)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Report 历史查询成功", data=data)
