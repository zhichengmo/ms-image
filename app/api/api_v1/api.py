from fastapi import APIRouter
from app.api.api_v1.endpoints import health

api_router = APIRouter()

# 注册路由
api_router.include_router(health.router, tags=["健康检查"])