from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.schemas.base import GenericResponse
from app.core.readiness import build_readiness
from datetime import datetime

router = APIRouter()


@router.get("/health", response_model=GenericResponse[dict], summary="健康检查")
async def health_check():
    """
    健康检查接口
    """
    return GenericResponse(
        success=True,
        message="服务运行正常",
        data={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "MS Scaffold Service"
        }
    )


@router.get("/version", response_model=GenericResponse[dict], summary="版本信息")
async def get_version():
    """
    获取服务版本信息
    """
    return GenericResponse(
        success=True,
        message="获取版本信息成功",
        data={
            "version": "1.0.0",
            "name": "MS Scaffold Service",
            "description": "微服务脚手架",
            "build_time": datetime.now().isoformat()
        }
    )


@router.get("/readiness", response_model=GenericResponse[dict], summary="依赖就绪检查")
async def readiness_check(request: Request):
    """区分进程存活与依赖就绪；依赖失败时返回 503。"""
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
