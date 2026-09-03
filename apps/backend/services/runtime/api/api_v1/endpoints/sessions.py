from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.core.dependencies import (
    get_async_session,
    get_explicit_transaction_session,
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


async def get_session_write_service(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> SessionService:
    return SessionService(db)


@router.post(
    "",
    response_model=GenericResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建影像业务会话",
)
async def create_session(
    payload: SessionCreate,
    context: dict = Depends(resource_context),
    service: SessionService = Depends(get_session_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    """创建整条影像业务链的顶层会话。

    前置条件：调用方必须具有影像资源权限，且请求中的来源系统、来源会话标识和
    业务主体信息满足 Session 合同。创建成功后，Session 初始处于 ``open`` 状态，
    后续 Study、Series、Image 和 Task 都通过它建立资源归属关系。

    幂等语义：相同 ``request_id``，或相同来源系统与来源会话标识的等价重放，
    返回已经创建的 Session；如果幂等键相同但不可变字段不同，则拒绝为冲突。
    整个数据库写入在显式事务中完成，失败时统一回滚。

    本接口只创建会话，不会创建 Study、上传影像、提交诊断 Task，也不会同步调用 AI。
    """
    try:
        async with db.begin():
            data = await service.create_session(
                payload=payload, requester_id=context["subject"]
            )
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
    service: SessionService = Depends(get_session_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    try:
        async with db.begin():
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
    service: SessionService = Depends(get_session_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    try:
        async with db.begin():
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
    service: SessionService = Depends(get_session_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    try:
        async with db.begin():
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
