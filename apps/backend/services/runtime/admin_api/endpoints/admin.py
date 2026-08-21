from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import JSONResponse
from apps.backend.schemas.base import GenericResponse
from apps.backend.core.dependencies import require_admin_scope
from apps.backend.core.config import settings
from apps.backend.core.readiness import build_readiness
from datetime import datetime

router = APIRouter()


@router.get("/status", response_model=GenericResponse[dict], summary="管理员状态检查")
async def admin_status(
        auth: dict = Depends(require_admin_scope(settings.ADMIN_REQUIRED_SCOPE))
):
    """
    管理员状态检查接口
    需要管理员 JWT 和读取 scope
    """
    return GenericResponse(
        success=True,
        message="管理员接口正常",
        data={
            "status": "admin_healthy",
            "timestamp": datetime.now().isoformat(),
            "authenticated": True,
            "subject": auth["subject"],
            "scopes": auth["scopes"],
        }
    )


@router.get("/info", response_model=GenericResponse[dict], summary="管理员信息")
async def admin_info(
        auth: dict = Depends(require_admin_scope(settings.ADMIN_REQUIRED_SCOPE))
):
    """
    获取管理员服务信息
    """
    return GenericResponse(
        success=True,
        message="获取管理员信息成功",
        data={
            "admin_version": "1.0.0",
            "scopes": auth["scopes"],
            "subject": auth["subject"],
            "service": "MS-Image Admin Service",
            "timestamp": datetime.now().isoformat()
        }
    )


@router.get("/readiness", response_model=GenericResponse[dict], summary="管理员依赖就绪检查")
async def admin_readiness(
    request: Request,
    _auth: dict = Depends(require_admin_scope(settings.ADMIN_REQUIRED_SCOPE)),
):
    """管理员依赖探针；返回的组件状态也属于控制面信息。"""
    manager = getattr(request.app.state, "redis_manager", None)
    if manager is None:
        data = {
            "ready": False,
            "components": {},
            "error": "Redis manager is not initialized",
        }
    else:
        data = await build_readiness(manager)
    status_code = 200 if data.get("ready") else 503
    return JSONResponse(
        status_code=status_code,
        content=GenericResponse(
            success=bool(data.get("ready")),
            message="服务依赖已就绪" if data.get("ready") else "服务依赖未就绪",
            data=data,
        ).model_dump(),
    )
