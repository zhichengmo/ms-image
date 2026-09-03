from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.dependencies import (
    ImageStorageDependencies,
    get_async_session,
    get_image_service,
    get_image_storage_dependencies,
    require_resource_scope,
)
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.schemas.image import (
    ImageAbortCommand,
    ImageCompleteUploadRequest,
    ImageListMultipartPartsRequest,
    ImageMultipartPartReceipt,
    ImageMultipartPartsResponse,
    ImageMultipartUploadTicket,
    ImagePageItemResponse,
    ImagePageQuery,
    ImagePrepareMultipartRequest,
    ImagePreparePartsRequest,
    ImagePrepareUploadRequest,
    ImageReplaceMultipartRequest,
    ImageReplaceRequest,
    ImageResponse,
    ImageUploadTicket,
)
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.image_service import ImageService


router = APIRouter(prefix="/images", tags=["Imaging images"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.post(
    "/prepare-upload",
    response_model=GenericResponse[ImageUploadTicket],
    status_code=status.HTTP_201_CREATED,
    summary="准备影像直传",
)
async def prepare_upload(
    payload: ImagePrepareUploadRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    """创建或恢复一条影像上传记录，并签发对象存储直传凭证。

    前置条件：Series、Study、Session 必须存在且属于当前调用方；Session 应处于
    ``processing``，Study 不得失效。同一逻辑影像已有 ``ready`` 版本时必须使用替换
    接口；已有 ``validating`` 版本时拒绝并发覆盖。

    新 Image 会进入 ``uploading`` 状态。对相同逻辑键和相同上传合同的重放，会通过
    CAS 刷新上传有效期并返回同一 Image。响应 ticket 包含 signed URL、必须携带的
    headers、过期时间和 generation。

    客户端随后直接 ``PUT`` signed OSS URL；该 PUT 是外部对象存储调用，不经过本
    Runtime endpoint，也不会更新数据库状态。本接口不接收文件字节、不验证对象内容、
    不把 Image 标记为 ``ready``，也不会触发 AI。
    """
    try:
        data = await dependencies.service.issue_direct_upload(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传已准备", data=data)


@router.post(
    "/replace",
    response_model=GenericResponse[ImageUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def replace_image(
    payload: ImageReplaceRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.issue_direct_replacement(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 替换上传已准备", data=data)


@router.post(
    "/replace-multipart",
    response_model=GenericResponse[ImageMultipartUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def replace_image_multipart(
    payload: ImageReplaceMultipartRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.issue_multipart_replacement(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片替换上传已准备", data=data)


@router.post(
    "/prepare-multipart-upload",
    response_model=GenericResponse[ImageMultipartUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def prepare_multipart_upload(
    payload: ImagePrepareMultipartRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.issue_multipart_upload(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片上传已准备", data=data)


@router.post(
    "/prepare-upload-parts",
    response_model=GenericResponse[ImageMultipartPartsResponse],
)
async def prepare_upload_parts(
    payload: ImagePreparePartsRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.issue_multipart_part_urls(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片上传地址已准备", data=data)


@router.post(
    "/list-upload-parts",
    response_model=GenericResponse[list[ImageMultipartPartReceipt]],
)
async def list_upload_parts(
    payload: ImageListMultipartPartsRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.list_multipart_parts(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 已上传分片查询成功", data=data)


@router.post(
    "/complete-upload",
    response_model=GenericResponse[ImageResponse],
    summary="确认影像上传并进入校验",
)
async def complete_upload(
    payload: ImageCompleteUploadRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    """根据对象存储中的真实对象确认上传完成，并投递异步校验事件。

    Service 会先核对 Image 归属、``expected_state_version``、generation 与上传模式，
    再通过对象存储 ``HEAD``（分片上传则先完成分片）获取真实对象信息，校验版本、大小、
    哈希和内容类型。全部一致后，使用 CAS 将 Image 从 ``uploading`` 推进为
    ``validating``，并在同一事务中创建唯一的 ``validate_image`` Outbox 事件。

    如果同一确认请求已使 Image 进入 ``validating``，仅在对象版本、manifest 和
    Outbox 合同完全一致时幂等返回；任何版本、对象或事件不一致都失败关闭。

    返回“已进入校验”不代表 Image 已 ``ready``，也不代表 Study 已完成或 AI 已启动；
    业务客户端仍需通过 Image 查询接口等待异步校验收敛。
    """
    try:
        data = await dependencies.service.complete_upload_workflow(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传完成，已进入校验", data=data)


@router.get(
    "",
    response_model=GenericResponse[ImageResponse],
    summary="查询单个影像状态",
)
async def get_image(
    image_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: ImageService = Depends(get_image_service),
    db: AsyncSession = Depends(get_async_session),
):
    """按 ``id`` 查询当前调用方拥有的单个 Image。

    该接口沿 Image → Series → Study → Session 校验资源归属，返回当前持久化状态，
    可用于观察 ``uploading``、``validating``、``ready`` 或失败状态。它是纯读取接口，
    不刷新 signed URL、不触发校验、不推进状态，也不会启动 AI。
    """
    try:
        data = await service.get_image(image_id=image_id, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Image 查询成功", data=data)


@router.get(
    "/page",
    response_model=PagedResponse[ImagePageItemResponse],
    summary="分页查询序列影像状态",
)
async def page_images(
    query: Annotated[ImagePageQuery, Query()],
    context: dict = Depends(resource_context),
    service: ImageService = Depends(get_image_service),
    db: AsyncSession = Depends(get_async_session),
):
    """分页列出指定 Series 下属于当前调用方的 Image。

    可按状态、影像角色和 ``current_only`` 等条件过滤，适合批量上传后轮询全部影像是否
    已经收敛到 ``ready``。分页结果只反映数据库中的当前事实，不跨 Series 查询，也不
    重算版本归属、签发临时 URL、触发校验或调用 AI。
    """
    try:
        result = await service.page_images(
            query=query,
            requester_id=context["subject"],
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return PagedResponse(
        message="Image 分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post("/abort-upload", response_model=GenericResponse[ImageResponse])
async def abort_upload(
    payload: ImageAbortCommand,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        data = await dependencies.service.abort_upload_workflow(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传已终止", data=data)


__all__ = ["router"]
