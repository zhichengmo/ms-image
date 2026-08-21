from fastapi import APIRouter

from apps.backend.services.runtime.api.api_v1.endpoints import health, images, reports, sessions, studies, tasks

api_router = APIRouter()

api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(sessions.router)
api_router.include_router(studies.router)
api_router.include_router(images.router)
api_router.include_router(reports.router)
api_router.include_router(tasks.router)
