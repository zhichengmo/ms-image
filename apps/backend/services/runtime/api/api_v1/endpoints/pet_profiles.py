from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.dependencies import (
    get_async_session,
    get_pet_profile_service,
    require_resource_scope,
)
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.schemas.pet_profile import (
    PetProfileArchiveCommand,
    PetProfileCreate,
    PetProfileHistoryQuery,
    PetProfileHistoryResponse,
    PetProfilePageQuery,
    PetProfileResponse,
    PetProfileRestoreCommand,
    PetProfileUpdateCommand,
)
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.pet_profile_service import PetProfileService


router = APIRouter(prefix="/pet-profiles", tags=["Pet profiles"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.post(
    "",
    response_model=GenericResponse[PetProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_pet_profile(
    payload: PetProfileCreate,
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_profile(
            payload=payload,
            owner_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物档案已创建", data=data)


@router.get("", response_model=GenericResponse[PetProfileResponse])
async def get_pet_profile(
    pet_profile_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_profile(
            pet_profile_id=pet_profile_id,
            owner_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物档案查询成功", data=data)


@router.get("/page", response_model=PagedResponse[PetProfileResponse])
async def page_pet_profiles(
    query: Annotated[PetProfilePageQuery, Query()],
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page_profiles(
            query=query,
            owner_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return PagedResponse(
        message="宠物档案分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post("/update", response_model=GenericResponse[PetProfileResponse])
async def update_pet_profile(
    payload: PetProfileUpdateCommand,
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.update_profile(
            payload=payload,
            owner_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物档案已更新", data=data)


@router.post("/archive", response_model=GenericResponse[PetProfileResponse])
async def archive_pet_profile(
    payload: PetProfileArchiveCommand,
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.archive_profile(
            pet_profile_id=payload.id,
            owner_id=context["subject"],
            expected_state_version=payload.expected_state_version,
            archive_reason=payload.archive_reason,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物档案已归档", data=data)


@router.post("/restore", response_model=GenericResponse[PetProfileResponse])
async def restore_pet_profile(
    payload: PetProfileRestoreCommand,
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.restore_profile(
            pet_profile_id=payload.id,
            owner_id=context["subject"],
            expected_state_version=payload.expected_state_version,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="宠物档案已恢复", data=data)


@router.get("/history", response_model=PagedResponse[PetProfileHistoryResponse])
async def page_pet_profile_history(
    query: Annotated[PetProfileHistoryQuery, Query()],
    context: dict = Depends(resource_context),
    service: PetProfileService = Depends(get_pet_profile_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page_history(
            query=query,
            owner_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return PagedResponse(
        message="宠物档案变更历史查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


__all__ = ["router"]
