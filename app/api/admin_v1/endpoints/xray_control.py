from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_xray_execution_service,
    get_xray_run_service,
    require_admin_tenant_scope,
)
from app.core.async_db import get_async_session
from app.core.config import settings
from app.schemas.base import GenericResponse, PageInfo, PagedResponse
from app.schemas.xray_accuracy import XRayExecutionRequest, XRayRunResponse
from app.service.xray_accuracy import XRayExecutionService, XRayRunService
from app.service.xray_accuracy.errors import RunNotFoundError

router = APIRouter(prefix="/xray/control", tags=["XRay 控制面"])


@router.post(
    "/executions",
    response_model=GenericResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="触发一次 validation-only Worker 执行",
)
async def execute_xray_run(
    payload: XRayExecutionRequest,
    context: dict = Depends(
        require_admin_tenant_scope(settings.ADMIN_REQUIRED_WRITE_SCOPE)
    ),
    service: XRayExecutionService = Depends(get_xray_execution_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.execute_pending(
            tenant_id=context["tenant_id"],
            run_id=payload.run_id,
            owner_id=context["subject"],
        )
        return GenericResponse(success=True, message="Worker 执行完成", data=result)
    except RunNotFoundError:
        await db.rollback()
        return JSONResponse(
            status_code=404,
            content=GenericResponse(
                success=False, message="Run 不存在", data=None, error_code=4041
            ).model_dump(),
        )
    except SQLAlchemyError:
        await db.rollback()
        return JSONResponse(
            status_code=503,
            content=GenericResponse(
                success=False, message="服务依赖未就绪", data=None, error_code=5031
            ).model_dump(),
        )
    except ValueError:
        await db.rollback()
        return JSONResponse(
            status_code=409,
            content=GenericResponse(
                success=False, message="执行状态冲突", data=None, error_code=4093
            ).model_dump(),
        )


@router.get(
    "/runs",
    response_model=GenericResponse[XRayRunResponse] | PagedResponse[XRayRunResponse],
    summary="管理员按 tenant scope 查询 Run",
)
async def admin_query_xray_runs(
    run_id: str | None = Query(default=None, min_length=1, max_length=64),
    page: int = Query(default=1, ge=1, le=100000),
    limit: int = Query(default=20, ge=1, le=100),
    context: dict = Depends(require_admin_tenant_scope(settings.ADMIN_REQUIRED_SCOPE)),
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
    except RunNotFoundError:
        await db.rollback()
        return JSONResponse(
            status_code=404,
            content=GenericResponse(
                success=False, message="Run 不存在", data=None, error_code=4041
            ).model_dump(),
        )
    except SQLAlchemyError:
        await db.rollback()
        return JSONResponse(
            status_code=503,
            content=GenericResponse(
                success=False, message="服务依赖未就绪", data=None, error_code=5031
            ).model_dump(),
        )
