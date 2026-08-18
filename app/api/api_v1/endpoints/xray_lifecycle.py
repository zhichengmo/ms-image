from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_session, get_xray_lifecycle_service, require_tenant_scope
from app.core.config import settings
from app.schemas.base import GenericResponse
from app.schemas.xray_accuracy import (
    XRaySessionCancelRequest,
    XRaySessionCreate,
    XRaySessionResponse,
    XRaySessionEventResponse,
    XRayImageAssetResponse,
    XRayStudyDetailResponse,
    XRayStudyPreparationResponse,
    XRayStudyPreparationCreate,
)
from app.service.xray_accuracy.errors import (
    IdempotencyConflictError,
    InputContractError,
    LeakageInputError,
    SessionNotFoundError,
    StudyNotFoundError,
)
from app.service.xray_accuracy.lifecycle_service import XRayLifecycleService


router = APIRouter(prefix="/xray", tags=["XRay session/study lifecycle"])


def _error_response(http_status: int, error_code: int, message: str):
    return JSONResponse(
        status_code=http_status,
        content=GenericResponse(
            success=False, message=message, data=None, error_code=error_code
        ).model_dump(),
    )


def _map_error(exc: Exception):
    if isinstance(exc, SQLAlchemyError):
        return _error_response(503, 5031, "服务依赖未就绪")
    if isinstance(exc, LeakageInputError):
        return _error_response(422, 4002, "请求包含禁止输入字段")
    if isinstance(exc, InputContractError):
        return _error_response(422, 4001, "请求合同无效")
    if isinstance(exc, IdempotencyConflictError):
        return _error_response(409, 4091, "幂等请求内容冲突")
    if isinstance(exc, SessionNotFoundError):
        return _error_response(404, 4042, "Session 不存在")
    if isinstance(exc, StudyNotFoundError):
        return _error_response(404, 4043, "Study 不存在")
    raise exc


async def _rollback(db: AsyncSession, exc: Exception):
    await db.rollback()
    return _map_error(exc)


@router.post(
    "/sessions",
    response_model=GenericResponse[XRaySessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建 XRay 业务 Session",
)
async def create_session(
    payload: XRaySessionCreate,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_session(context=context, payload=payload)
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Session 已创建", data=data)


@router.get(
    "/sessions",
    response_model=GenericResponse[XRaySessionResponse],
    summary="查询 XRay Session",
)
async def get_session(
    session_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_session(
            tenant_id=context["tenant_id"], subject_id=context["subject"], session_id=session_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Session 查询成功", data=data)


@router.post(
    "/session-cancellations",
    response_model=GenericResponse[XRaySessionResponse],
    summary="取消 XRay Session",
)
async def cancel_session(
    payload: XRaySessionCancelRequest,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.cancel_session(
            context=context, session_id=payload.session_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Session 已取消", data=data)


@router.post(
    "/study-preparations",
    response_model=GenericResponse[XRayStudyPreparationResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="受理 Study 影像准备与对象存储任务",
)
async def create_study_preparation(
    payload: XRayStudyPreparationCreate,
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_study_preparation(context=context, payload=payload)
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Study preparation 已受理", data=data)


@router.get(
    "/studies",
    response_model=GenericResponse[XRayStudyDetailResponse],
    summary="查询 Study Snapshot 与影像资产摘要",
)
async def get_study(
    study_revision_id: str = Query(..., min_length=1, max_length=128),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_study(
            tenant_id=context["tenant_id"], subject_id=context["subject"], study_revision_id=study_revision_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Study 查询成功", data=data)


@router.get(
    "/study-assets",
    response_model=GenericResponse[list[XRayImageAssetResponse]],
    summary="查询 Study 的影像资产工程摘要",
    description="只返回资产状态、hash、尺寸和对象可用性，不返回 signed URL 或原图内容。",
)
async def get_study_assets(
    study_revision_id: str = Query(..., min_length=1, max_length=128),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_study_assets(
            tenant_id=context["tenant_id"], subject_id=context["subject"], study_revision_id=study_revision_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Study 资产查询成功", data=data)


@router.get(
    "/session-events",
    response_model=GenericResponse[list[XRaySessionEventResponse]],
    summary="查询 Session 生命周期事件",
    description="记录 session-start、取消等业务生命周期事件；不替代 Run Trace。",
)
async def get_session_events(
    session_id: str = Query(..., min_length=1, max_length=64),
    context: dict = Depends(require_tenant_scope(settings.XRAY_REQUIRED_SCOPE)),
    service: XRayLifecycleService = Depends(get_xray_lifecycle_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_session_events(
            tenant_id=context["tenant_id"], subject_id=context["subject"], session_id=session_id
        )
    except Exception as exc:
        return await _rollback(db, exc)
    return GenericResponse(success=True, message="Session 事件查询成功", data=data)
