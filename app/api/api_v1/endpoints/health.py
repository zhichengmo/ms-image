from fastapi import APIRouter
from app.schemas.base import GenericResponse
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