from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.dependencies import (
    get_async_session,
    get_pet_info_service,
    require_resource_scope,
)
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.pet_info import PetInfoCatalogResponse, PetInfoQuery
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.pet_info_service import PetInfoService


router = APIRouter(prefix="/pet-info", tags=["Pet breed catalog"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.get("", response_model=GenericResponse[PetInfoCatalogResponse])
async def get_pet_info_catalog(
    query: Annotated[PetInfoQuery, Query()],
    _context: dict = Depends(resource_context),
    service: PetInfoService = Depends(get_pet_info_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_catalog(query=query)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物品种资料查询成功", data=data)


__all__ = ["router"]
