from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import (
    get_xray_execution_service,
    get_xray_run_service,
    get_xray_trace_service,
    require_tenant_scope,
)
from app.schemas.base import GenericResponse, PageInfo, PagedResponse
from app.schemas.xray_accuracy import (
    XRayCancelRequest,
    XRayExecutionResponse,
    XRayRunCreate,
    XRayRunResponse,
    XRayTraceResponse,
)
from app.service.xray_accuracy import XRayExecutionService, XRayRunService, XRayTraceService
from app.service.xray_accuracy.errors import (
    CASConflictError,
    IdempotencyConflictError,
    InputContractError,
    LeakageInputError,
    QualificationAccessError,
    RunNotFoundError,
)
from app.core.async_db import get_async_session
from app.core.config import settings

router = APIRouter(prefix="/xray", tags=["XRay validation-only"])


def _error_response(http_status: int, error_code: int, message: str, data=None):
    return JSONResponse(
        status_code=http_status,
        content=GenericResponse(
            success=False,
            message=message,
            data=data,
            error_code=error_code,
        ).model_dump(),
    )


def _service_error(exc: Exception):
    if isinstance(exc, SQLAlchemyError):
        return _error_response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, LeakageInputError):
        # The matched paths are request-derived and may reveal arbitrary
        # nested field names. Keep them in internal diagnostics only; the
        # public contract exposes a stable code without echoing input shape.
        return _error_response(422, 4002, "请求包含禁止输入字段")
    if isinstance(exc, QualificationAccessError):
        return _error_response(403, 4033, "Provider Qualification 仅允许受控离线流程")
    if isinstance(exc, InputContractError):
        return _error_response(422, 4001, "请求合同无效")
    if isinstance(exc, IdempotencyConflictError):
        return _error_response(409, 4091, "幂等请求内容冲突")
    if isinstance(exc, CASConflictError):
        return _error_response(409, 4092, "状态版本冲突")
    if isinstance(exc, RunNotFoundError):
        return _error_response(404, 4041, "Run 不存在")
    raise exc


async def _rollback_and_service_error(db: AsyncSession, exc: Exception):
    # The session dependency owns the outer transaction.  Because this
    # endpoint translates domain/DB exceptions into response objects, it must
    # explicitly roll back first; otherwise the dependency would see a normal
    # return and could commit a partial Run/Snapshot/Checkpoint/Outbox graph.
    await db.rollback()
    return _service_error(exc)


@router.post(
    "/runs",
    response_model=GenericResponse[XRayRunResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="受理 validation-only XRay Run",
)
async def create_xray_run(
    payload: XRayRunCreate,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayRunService = Depends(get_xray_run_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_run(context=context, payload=payload)
    except Exception as exc:
        return await _rollback_and_service_error(db, exc)
    return GenericResponse(success=True, message="Run 已受理（validation-only）", data=data)


@router.get(
    "/runs",
    response_model=GenericResponse[XRayRunResponse] | PagedResponse[XRayRunResponse],
    summary="按 tenant scope 查询 Run",
)
async def query_xray_runs(
    run_id: str | None = Query(default=None, min_length=1, max_length=64),
    page: int = Query(default=1, ge=1, le=100000),
    limit: int = Query(default=20, ge=1, le=100),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayRunService = Depends(get_xray_run_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        if run_id:
            data = await service.get_run(tenant_id=context["tenant_id"], run_id=run_id)
            return GenericResponse(success=True, message="查询成功", data=data)
        rows, total = await service.list_runs(
            tenant_id=context["tenant_id"], page=page, limit=limit
        )
        return PagedResponse(
            success=True,
            message="查询成功",
            data=rows,
            page_info=PageInfo(
                total=total,
                page=page,
                limit=limit,
                total_pages=(total + limit - 1) // limit if total else 0,
            ),
        )
    except Exception as exc:
        return await _rollback_and_service_error(db, exc)


@router.post(
    "/run-cancellations",
    response_model=GenericResponse[XRayRunResponse],
    summary="按 CAS 版本取消 Run",
)
async def cancel_xray_run(
    payload: XRayCancelRequest,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayRunService = Depends(get_xray_run_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.cancel_run(tenant_id=context["tenant_id"], request=payload)
    except Exception as exc:
        return await _rollback_and_service_error(db, exc)
    return GenericResponse(success=True, message="取消请求已记录", data=data)


@router.get(
    "/executions",
    response_model=GenericResponse[XRayExecutionResponse],
    summary="查询 validation-only 技术执行结果",
)
async def query_xray_execution(
    run_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayExecutionService = Depends(get_xray_execution_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_execution(
            tenant_id=context["tenant_id"], run_id=run_id
        )
        return GenericResponse(success=True, message="执行结果查询成功", data=data)
    except Exception as exc:
        return await _rollback_and_service_error(db, exc)


@router.get(
    "/traces",
    response_model=PagedResponse[XRayTraceResponse],
    summary="按 tenant scope 查询技术 Trace",
)
async def query_xray_traces(
    run_id: str = Query(..., min_length=1, max_length=64),
    page: int = Query(default=1, ge=1, le=100000),
    limit: int = Query(default=50, ge=1, le=100),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    run_service: XRayRunService = Depends(get_xray_run_service),
    trace_service: XRayTraceService = Depends(get_xray_trace_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        await run_service.get_run(tenant_id=context["tenant_id"], run_id=run_id)
        rows, total = await trace_service.list_trace(
            tenant_id=context["tenant_id"], run_id=run_id, page=page, limit=limit
        )
        data = [
            XRayTraceResponse(
                trace_id=row.id,
                run_id=row.run_id,
                stage_key=row.stage_key,
                event_type=row.event_type,
                state_version=row.state_version,
                late_flag="yes" if "late" in row.event_type.casefold() else "no",
                fingerprint=row.fingerprint,
            )
            for row in rows
        ]
        return PagedResponse(
            success=True,
            message="Trace 查询成功",
            data=data,
            page_info=PageInfo(
                total=total, page=page, limit=limit,
                total_pages=(total + limit - 1) // limit if total else 0,
            ),
        )
    except Exception as exc:
        return await _rollback_and_service_error(db, exc)
