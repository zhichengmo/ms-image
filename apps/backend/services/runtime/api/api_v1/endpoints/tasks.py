from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.core.dependencies import (
    get_async_session,
    get_explicit_transaction_session,
    require_caller_scope,
)
from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.schemas.task import (
    TaskCancelRequest,
    TaskCreate,
    TaskPageQuery,
    TaskResponse,
    TaskStatusResponse,
)
from apps.backend.services.runtime.service.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Imaging tasks"])
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)


async def get_task_service(
    db: AsyncSession = Depends(get_async_session),
) -> TaskService:
    return TaskService(db)


async def get_task_write_service(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> TaskService:
    return TaskService(db)


@router.post(
    "",
    response_model=GenericResponse[TaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="提交影像处理任务",
)
async def create_task(
    payload: TaskCreate,
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    """冻结 Study、配置和影像输入，创建异步执行 Task。

    前置条件：Study/Session 必须存在并属于当前调用方；Study 已 ``ready``，请求中的
    revision 与 resolved manifest 精确匹配；对应 AI Config 必须处于 active 状态，
    species、task type 与编译后的 Profile 合同必须一致。要求 Quality 上游的 Profile
    还必须提供同 Study/revision/manifest/species 的冻结 ``quality_review_task_id``。

    创建时会冻结请求快照，生成首个 Stage checkpoint 与 Outbox 事件。``diagnose``
    Task 会标记 ``report_required=true``，初始执行状态为 ``queued``、医学状态为
    ``not_produced``。相同 requester、``request_id`` 和 task type 的等价请求幂等返回
    原 Task；冻结输入或配置不一致则拒绝。

    HTTP 201 只表示 Task 已受理并持久化，不会在请求线程内调用 Provider、等待 Worker、
    保证 Task 已完成或保证 Report 已生成。
    """
    try:
        async with db.begin():
            data = await service.create_task(payload=payload, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 已受理", data=data)


@router.get(
    "",
    response_model=GenericResponse[TaskResponse],
    summary="查询任务执行状态",
)
async def get_task(
    task_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    """按 ``id`` 查询当前调用方拥有的 Task 及其持久化执行状态。

    业务客户端可轮询该接口观察 ``queued``、运行中和终态，以及取消请求、错误、当前
    Report 指针等 Task 事实。该接口是纯读取操作，不推进 Stage、不触发 Worker、
    不发起 Provider 请求，也不会为了查询而自动生成 Report。
    """
    try:
        data = await service.get_task(task_id=task_id, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 查询成功", data=data)


@router.get("/page", response_model=PagedResponse[TaskStatusResponse])
async def page_tasks(
    query: Annotated[TaskPageQuery, Query()],
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page_tasks(query=query, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return PagedResponse(
        message="Task 分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post("/cancel", response_model=GenericResponse[TaskResponse])
async def cancel_task(
    payload: TaskCancelRequest,
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    try:
        async with db.begin():
            data = await service.cancel_task(
                task_id=payload.id,
                expected_version=payload.expected_state_version,
                reason=payload.reason,
                caller=context,
            )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 取消请求已记录", data=data)
