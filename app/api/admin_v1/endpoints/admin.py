from fastapi import APIRouter, Depends
from app.schemas.base import GenericResponse
from app.api.deps import basic_auth
from datetime import datetime

router = APIRouter()


@router.get("/status", response_model=GenericResponse[dict], summary="管理员状态检查")
async def admin_status(auth: bool = Depends(basic_auth)):
    """
    管理员状态检查接口
    需要基础认证
    """
    return GenericResponse(
        success=True,
        message="管理员接口正常",
        data={
            "status": "admin_healthy",
            "timestamp": datetime.now().isoformat(),
            "authenticated": auth
        }
    )


@router.get("/info", response_model=GenericResponse[dict], summary="管理员信息")
async def admin_info(auth: bool = Depends(basic_auth)):
    """
    获取管理员服务信息
    """
    return GenericResponse(
        success=True,
        message="获取管理员信息成功",
        data={
            "admin_version": "1.0.0",
            "permissions": ["read", "write", "delete"],
            "service": "Admin MS Scaffold Service",
            "timestamp": datetime.now().isoformat()
        }
    )