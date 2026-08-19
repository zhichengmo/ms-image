from fastapi import APIRouter
from app.api.admin_v1.endpoints import admin, ai_config, xray_control, xray_qualification

admin_api_router = APIRouter()

# 注册管理员路由
admin_api_router.include_router(admin.router, tags=["管理员"])
admin_api_router.include_router(xray_control.router)
admin_api_router.include_router(xray_qualification.router)
admin_api_router.include_router(ai_config.router)
