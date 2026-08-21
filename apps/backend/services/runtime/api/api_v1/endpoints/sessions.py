from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.backend.core.dependencies import (
    get_async_session,
    get_session_service,
    require_resource_scope,
)
from apps.backend.core.config import settings
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.session import (
    SessionCancelCommand,
    SessionCreate,
    SessionResponse,
    SessionVersionCommand,
)
from apps.backend.services.runtime.service.session_service import SessionService


router = APIRouter(prefix="/sessions", tags=["Imaging sessions"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.post("", response_model=GenericResponse[SessionResponse], status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_session(payload=payload, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Session 已创建", data=data)


@router.get("", response_model=GenericResponse[SessionResponse])
async def get_session(
    session_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_session(
            session_id=session_id, requester_id=context["subject"]
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Session 查询成功", data=data)


@router.post("/complete", response_model=GenericResponse[SessionResponse])
async def complete_session(
    payload: SessionVersionCommand,
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.complete_session(
            session_id=payload.id,
            requester_id=context["subject"],
            expected_state_version=payload.expected_state_version,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Session 已完成", data=data)


@router.post("/close", response_model=GenericResponse[SessionResponse])
async def close_session(
    payload: SessionVersionCommand,
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.close_session(
            session_id=payload.id,
            requester_id=context["subject"],
            expected_state_version=payload.expected_state_version,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Session 已关闭", data=data)


@router.post("/cancel", response_model=GenericResponse[SessionResponse])
async def cancel_session(
    payload: SessionCancelCommand,
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.cancel_session(
            session_id=payload.id,
            requester_id=context["subject"],
            expected_state_version=payload.expected_state_version,
            cancel_reason=payload.cancel_reason,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Session 已取消", data=data)


__all__ = ["router"]
