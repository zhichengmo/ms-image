from fastapi import APIRouter

from apps.backend.services.runtime.api.api_v1.endpoints import (
    anatomy_localizations,
    health,
    images,
    pet_info,
    pet_profiles,
    reports,
    sessions,
    studies,
    tasks,
    xray_quality,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(sessions.router)
api_router.include_router(studies.router)
api_router.include_router(images.router)
api_router.include_router(pet_profiles.router)
api_router.include_router(pet_info.router)
api_router.include_router(reports.router)
api_router.include_router(tasks.router)
api_router.include_router(anatomy_localizations.router)
api_router.include_router(xray_quality.router)
