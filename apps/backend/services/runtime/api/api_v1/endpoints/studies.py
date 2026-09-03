from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.core.dependencies import (
    get_async_session,
    get_explicit_transaction_session,
    get_study_service,
    require_resource_scope,
)
from apps.backend.core.config import settings
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.study import (
    SeriesCreate,
    SeriesResponse,
    StudyCreate,
    StudyDetailResponse,
    StudyFinalizeRequest,
    StudyResponse,
)
from apps.backend.services.runtime.service.study_service import StudyService


router = APIRouter(tags=["Imaging studies"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


async def get_study_write_service(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> StudyService:
    return StudyService(db)


@router.post(
    "/studies",
    response_model=GenericResponse[StudyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="在会话中创建影像检查",
)
async def create_study(
    payload: StudyCreate,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    """在指定 Session 下创建一个 Study（一次影像检查）。

    前置条件：Session 必须属于当前调用方并处于可接收检查的 ``open`` 或
    ``processing`` 状态；XRay 检查还会校验期望影像数量是否符合冻结合同。

    幂等语义：同一 Session 下相同 ``source_study_id`` 的等价请求返回原 Study；
    未提供来源检查标识时，Service 会从稳定请求内容生成确定性标识。新 Study 初始为
    ``ingesting``，并建立第一版 revision；必要时 Session 会由 ``open`` 推进为
    ``processing``。写入与状态推进处于同一显式事务中。

    本接口不会创建 Series 或 Image，不会 finalize Study，也不会提交或等待 AI Task。
    """
    try:
        async with db.begin():
            data = await service.create_study(
                payload=payload, requester_id=context["subject"]
            )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 已创建", data=data)


@router.get("/studies", response_model=GenericResponse[StudyDetailResponse])
async def get_study(
    study_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_study(
            study_id=study_id, requester_id=context["subject"]
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 查询成功", data=data)


@router.post(
    "/studies/finalize",
    response_model=GenericResponse[StudyResponse],
    summary="冻结并完成影像检查",
)
async def finalize_study(
    payload: StudyFinalizeRequest,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    """校验 Study 的完整性并将当前 revision 冻结为可执行状态。

    前置条件：调用方必须拥有该 Study；``expected_state_version`` 与
    ``current_revision_id`` 必须精确匹配；身份需已确认，至少存在一个 Series，所有
    Series 均已 ``ready``，且不存在仍在 ``uploading`` 或 ``validating`` 的影像。
    XRay 还会重建诊断影像 manifest，并核对 Series/Study 数量、manifest SHA 与
    ``completeness_status``。

    校验全部通过后使用 CAS 将 Study 推进为 ``ready``。对同一 revision 的已成功请求
    支持受限幂等重放；版本或冻结身份不一致时失败关闭，绝不静默采用数据库中的 latest。

    本接口只完成 Study 冻结，不会创建诊断 Task、调用 AI 或生成 Report。
    """
    try:
        async with db.begin():
            data = await service.finalize_study(
                payload=payload, requester_id=context["subject"]
            )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 已完成", data=data)


@router.post(
    "/series",
    response_model=GenericResponse[SeriesResponse],
    status_code=status.HTTP_201_CREATED,
    summary="在检查中创建影像序列",
)
async def create_series(
    payload: SeriesCreate,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    """在指定 Study 下创建一个用于归组影像的 Series。

    前置条件：Study 必须属于当前调用方，所属 Session 处于 ``open`` 或
    ``processing``，且 Study 未失效。XRay 会额外校验本 Series 的期望影像数量，
    以及 Study 下所有 Series 的总影像预算。

    幂等语义：同一 Study 下相同 ``series_key`` 的等价请求返回原 Series；如果不可变
    字段不一致则拒绝。新 Series 初始为 ``ingesting``、实际影像数为 0，并推进 Study
    revision，以便后续上传和 finalize 使用新的冻结身份。

    本接口不上传影像、不直接把 Series 标记为 ``ready``，也不产生 AI Task。
    """
    try:
        async with db.begin():
            data = await service.create_series(
                payload=payload, requester_id=context["subject"]
            )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Series 已创建", data=data)


__all__ = ["router"]
