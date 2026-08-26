"""AI Control API v1 router registration."""

from fastapi import APIRouter

from apps.backend.services.ai_control.api.api_v1.endpoints import (
    ai_config,
    ai_connection,
    ai_control_audit,
    ai_model_pool,
    ai_prompt,
    ai_prompt_import,
)

api_router = APIRouter()
api_router.include_router(ai_prompt.router)
api_router.include_router(ai_prompt_import.router)
api_router.include_router(ai_connection.router)
api_router.include_router(ai_model_pool.router)
api_router.include_router(ai_config.router)
api_router.include_router(ai_control_audit.router)

__all__ = ["api_router"]
