from fastapi import APIRouter

from app.api.admin_v1.endpoints import admin, ai_config, evaluation, operations, reports

admin_api_router = APIRouter()

admin_api_router.include_router(admin.router, tags=["管理员"])
admin_api_router.include_router(ai_config.router)
admin_api_router.include_router(reports.router)
admin_api_router.include_router(evaluation.router)
admin_api_router.include_router(operations.router)
