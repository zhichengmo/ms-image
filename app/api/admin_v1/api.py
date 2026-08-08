from fastapi import APIRouter
from app.api.admin_v1.endpoints import admin

admin_api_router = APIRouter()

# 注册管理员路由
admin_api_router.include_router(admin.router, tags=["管理员"])