"""Read-only control-plane audit endpoint."""

from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.dependencies import get_async_session, require_control_plane_scope
from apps.backend.schemas.ai_control import ControlAuditResponse, PageResult
from apps.backend.schemas.base import PageInfo, PagedResponse
from apps.backend.services.ai_control.errors import rollback_and_map_control_plane
from apps.backend.services.ai_control.service.control_audit_service import AIControlAuditService

router = APIRouter(prefix="/ai-control-audits", tags=["AI ControlPlane Audit"])
control = require_control_plane_scope()


async def get_service(
    db: AsyncSession = Depends(get_async_session),
) -> AIControlAuditService:
    return AIControlAuditService(db)


def _paged(result: PageResult[ControlAuditResponse]) -> PagedResponse[ControlAuditResponse]:
    return PagedResponse(
        message="AI Control 审计分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.get("/page", response_model=PagedResponse[ControlAuditResponse])
async def page_audits(
    resource_type: str | None = Query(default=None, max_length=64),
    resource_id: str | None = Query(default=None, max_length=64),
    actor_id: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: ControlPlaneContext = Depends(control),
    service: AIControlAuditService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page(
            page=page,
            limit=page_size,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
        )
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return _paged(result)


__all__ = ["router"]
