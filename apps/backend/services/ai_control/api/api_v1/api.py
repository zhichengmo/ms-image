"""AI Control API v1 router registration."""

from fastapi import APIRouter

from apps.backend.services.ai_control.api.api_v1.endpoints import ai_config


api_router = APIRouter()
api_router.include_router(ai_config.router)

__all__ = ["api_router"]
