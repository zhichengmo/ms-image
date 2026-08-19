from fastapi import APIRouter
from app.api.api_v1.endpoints import (
    health,
    images,
    sessions,
    studies,
    tasks,
    xray_legacy_compat,
    xray_lifecycle,
    xray_runs,
)

api_router = APIRouter()

# 注册路由
api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(sessions.router)
api_router.include_router(studies.router)
api_router.include_router(images.router)
api_router.include_router(tasks.router)
api_router.include_router(xray_runs.router)
api_router.include_router(xray_lifecycle.router)
api_router.include_router(xray_legacy_compat.router)
