"""External Prompt import control-plane endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.dependencies import get_async_session, require_control_plane_scope
from apps.backend.schemas.ai_control import PromptImportRequest, PromptImportResponse
from apps.backend.schemas.base import GenericResponse
from apps.backend.services.ai_control.errors import rollback_and_map_control_plane
from apps.backend.services.ai_control.service.prompt_import_service import (
    PromptImportService,
)

router = APIRouter(prefix="/ai-prompts/import", tags=["AI Prompt Import"])
control = require_control_plane_scope()


async def get_service(
    db: AsyncSession = Depends(get_async_session),
) -> PromptImportService:
    return PromptImportService(db)


@router.post(
    "",
    response_model=GenericResponse[PromptImportResponse],
    status_code=status.HTTP_201_CREATED,
)
async def import_prompt(
    payload: PromptImportRequest,
    context: ControlPlaneContext = Depends(control),
    service: PromptImportService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.import_prompt(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Prompt 已从外部来源导入", data=data)


__all__ = ["router"]
