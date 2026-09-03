from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.backend.core.dependencies import get_async_session, require_caller_scope
from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.report import ReportResponse
from apps.backend.services.runtime.service.report_service import ReportService

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


@router.get(
    "/current",
    response_model=GenericResponse[ReportResponse | None],
    summary="查询任务当前报告",
)
async def current_report(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: ReportService = Depends(get_report_service),
    db: AsyncSession = Depends(get_async_session),
):
    """查询指定 Task 当前可用的 final 或 published Report。

    前置条件：Task 必须存在并属于当前调用方。若 Task 尚未产生当前报告，正常返回
    ``data=null``；若存在 ``current_report_id``，则只接受归属该 Task 且状态为
    ``final`` 或 ``published`` 的 Report，避免把 superseded/void 版本误当当前结果。

    本接口是纯读取操作，不等待 Task、不生成或改写报告、不发布报告，也不会调用 AI。
    """
    try:
        data = await service.get_current_for_requester(
            task_id=task_id,
            requester_id=context.subject_id,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Report 当前版本查询成功", data=data)


@router.get(
    "/history",
    response_model=GenericResponse[list[ReportResponse]],
    summary="查询任务报告历史",
)
async def report_history(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: ReportService = Depends(get_report_service),
    db: AsyncSession = Depends(get_async_session),
):
    """查询指定 Task 的全部报告 revision。

    Service 先校验 Task 归属，再按既有 DAL 顺序返回该 Task 的报告历史，其中可包含
    current、superseded 或 void 等版本事实。该接口不会筛选或重建当前版本，不会修改
    Report/Task 状态，也不会触发独立的报告生成 AI。
    """
    try:
        data = await service.list_for_requester(task_id=task_id, requester_id=context.subject_id)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Report 历史查询成功", data=data)
