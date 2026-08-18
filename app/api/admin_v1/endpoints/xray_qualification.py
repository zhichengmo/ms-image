"""Admin-only Provider transport qualification and readiness APIs."""

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_xray_provider_qualification_service,
    require_admin_tenant_scope,
)
from app.core.config import settings
from app.core.readiness import build_readiness
from app.schemas.base import GenericResponse
from app.service.xray_accuracy import XRayProviderQualificationService


router = APIRouter(prefix="/xray", tags=["XRay Provider 资格"])


@router.post(
    "/provider-transport-qualifications",
    response_model=GenericResponse[dict],
    summary="执行一次真实 Provider 工程传输资格验证",
)
async def qualify_provider_transport(
    _context: dict = Depends(
        require_admin_tenant_scope(settings.ADMIN_REQUIRED_WRITE_SCOPE)
    ),
    service: XRayProviderQualificationService = Depends(
        get_xray_provider_qualification_service
    ),
):
    try:
        data = await service.run_transport_qualification()
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=GenericResponse(
                success=False,
                message="Provider 资格任务状态冲突",
                data=None,
                error_code=4094,
            ).model_dump(),
        )
    qualified = data.get("status") == "qualified"
    return JSONResponse(
        status_code=status.HTTP_200_OK if qualified else status.HTTP_409_CONFLICT,
        content=GenericResponse(
            success=qualified,
            message="Transport Qualification 已通过" if qualified else "Transport Qualification 被阻断",
            data=data,
            error_code=None if qualified else 4095,
        ).model_dump(),
    )


@router.get(
    "/provider-qualifications",
    response_model=GenericResponse[dict],
    summary="按资格 ID 查询已签名证据",
)
async def get_provider_qualification(
    qualification_id: str = Query(min_length=1, max_length=128),
    _context: dict = Depends(
        require_admin_tenant_scope(settings.ADMIN_REQUIRED_SCOPE)
    ),
    service: XRayProviderQualificationService = Depends(
        get_xray_provider_qualification_service
    ),
):
    try:
        data = await service.get_qualification(qualification_id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=GenericResponse(
                success=False,
                message="Provider 资格记录不存在",
                data=None,
                error_code=4044,
            ).model_dump(),
        )
    return GenericResponse(success=True, message="查询成功", data=data)


@router.get(
    "/readiness",
    response_model=GenericResponse[dict],
    summary="查询 XRay 双门禁就绪状态",
)
async def xray_readiness(
    request: Request,
    _context: dict = Depends(
        require_admin_tenant_scope(settings.ADMIN_REQUIRED_SCOPE)
    ),
):
    manager = getattr(request.app.state, "redis_manager", None)
    if manager is None:
        data = {"ready": False, "components": {}, "error": "redis_manager_uninitialized"}
    else:
        data = await build_readiness(manager)
    return JSONResponse(
        status_code=status.HTTP_200_OK
        if data.get("engineering_worker_ready")
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=GenericResponse(
            success=bool(data.get("engineering_worker_ready")),
            message=(
                "XRay 工程 Worker 已就绪"
                if data.get("engineering_worker_ready")
                else "XRay 工程 Worker 未就绪"
            ),
            data=data,
        ).model_dump(),
    )


__all__ = ["router"]
