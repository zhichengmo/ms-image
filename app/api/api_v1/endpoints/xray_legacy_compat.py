from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_async_session,
    get_xray_legacy_compat_service,
    require_tenant_scope,
)
from app.core.config import settings
from app.schemas.base import GenericResponse
from app.schemas.xray_accuracy import (
    LegacyPreparationRequest,
    LegacyPreparationResponse,
    LegacyReportSubmitRequest,
    LegacyReportTaskResponse,
    LegacyReportViewResponse,
    LegacySessionStartRequest,
    LegacySessionStartResponse,
    LegacyTaskStatusResponse,
)
from app.service.xray_accuracy.errors import (
    IdempotencyConflictError,
    InputContractError,
    RunNotFoundError,
    SessionNotFoundError,
    StudyNotFoundError,
)
from app.service.xray_accuracy.legacy_compat_service import XRayLegacyCompatService


router = APIRouter(tags=["XRay V2 compatibility"])


def _error_response(http_status: int, error_code: int, message: str):
    return JSONResponse(
        status_code=http_status,
        content=GenericResponse(
            success=False, message=message, data=None, error_code=error_code
        ).model_dump(),
    )


def _map_error(exc: Exception):
    if isinstance(exc, SQLAlchemyError):
        return _error_response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, InputContractError):
        return _error_response(422, 4001, "旧链请求合同或影像来源无效")
    if isinstance(exc, IdempotencyConflictError):
        return _error_response(409, 4091, "幂等请求内容冲突")
    if isinstance(exc, (SessionNotFoundError, StudyNotFoundError, RunNotFoundError)):
        return _error_response(404, 4041, "XRay 资源不存在")
    raise exc


async def _rollback(db: AsyncSession, exc: Exception):
    await db.rollback()
    return _map_error(exc)


@router.post(
    "/session-start",
    response_model=GenericResponse[LegacySessionStartResponse],
    status_code=status.HTTP_201_CREATED,
    summary="兼容旧 XRay session-start 语义",
)
async def legacy_session_start(
    payload: LegacySessionStartRequest,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.start_session(context=context, payload=payload)
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay Session 已创建", data=data)


@router.post(
    "/x_ray/v2/preparations",
    response_model=GenericResponse[LegacyPreparationResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="兼容旧 XRay preparation 提交语义",
)
async def legacy_create_preparation(
    payload: LegacyPreparationRequest,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.submit_preparation(context=context, payload=payload)
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay preparation 已受理", data=data)


@router.post(
    "/x_ray/v2/reports",
    response_model=GenericResponse[LegacyReportTaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="兼容旧 XRay report 异步提交语义",
)
async def legacy_submit_report(
    payload: LegacyReportSubmitRequest,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.submit_report(context=context, payload=payload)
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay report 任务已受理", data=data)


@router.get(
    "/x_ray/v2/tasks",
    response_model=GenericResponse[LegacyTaskStatusResponse],
    summary="按 task_id 查询旧链兼容任务",
)
async def legacy_get_task(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_task_status(
            tenant_id=context["tenant_id"], subject_id=context["subject"], task_id=task_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay 任务查询成功", data=data)


@router.get(
    "/x_ray/v2/reports",
    response_model=GenericResponse[LegacyReportViewResponse],
    summary="按 session_id 查询旧链兼容报告视图",
)
async def legacy_get_report(
    session_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_report_view(
            tenant_id=context["tenant_id"],
            subject_id=context["subject"],
            session_id=session_id,
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay 报告视图查询成功", data=data)


@router.get(
    "/x_ray/v2/segmentations",
    response_model=GenericResponse[dict],
    summary="按 session_id 查询旧链 segmentation 兼容视图",
)
async def legacy_get_segmentations(
    session_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLegacyCompatService = Depends(get_xray_legacy_compat_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_segmentation_view(
            tenant_id=context["tenant_id"],
            subject_id=context["subject"],
            session_id=session_id,
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="XRay segmentation 视图查询成功", data=data)
