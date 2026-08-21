from fastapi import APIRouter

from apps.backend.services.runtime.admin_api.endpoints import admin, operations, reports

admin_api_router = APIRouter()

admin_api_router.include_router(admin.router, tags=["管理员"])
admin_api_router.include_router(reports.router)
admin_api_router.include_router(operations.router)
