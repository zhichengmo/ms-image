from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.evaluation_control.errors import (
    rollback_and_map_control_plane,
)
from apps.backend.schemas.evaluation import (
    EvaluationArtifactResponse,
    EvaluationJobCreate,
    EvaluationJobResponse,
    EvaluationJobStateRequest,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from apps.backend.schemas.evaluation_export import (
    EvaluationExportJobCreate,
    EvaluationExportJobResponse,
)
from apps.backend.services.evaluation_control.service.evaluation_export_service import EvaluationExportService
from apps.backend.services.evaluation_control.service.evaluation_service import EvaluationService
from apps.backend.core.dependencies import require_control_plane_any_scope, require_control_plane_scope
from apps.backend.core.async_db import (
    get_evaluation_async_session,
    get_explicit_evaluation_transaction_session,
    get_explicit_transaction_session,
)
from apps.backend.services.evaluation_control.config import settings
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.imaging.object_store import OSSObjectStore, ObjectStorageGateway
from apps.backend.schemas.base import GenericResponse


router = APIRouter(prefix="/evaluation", tags=["Evaluation ControlPlane"])
control_read = require_control_plane_any_scope(
    settings.EVALUATION_READ_SCOPE,
    settings.EVALUATION_WRITE_SCOPE,
)
control_write = require_control_plane_scope(settings.EVALUATION_WRITE_SCOPE)


async def get_service(
    db: AsyncSession = Depends(get_evaluation_async_session),
) -> EvaluationService:
    return EvaluationService(db)


@dataclass(frozen=True)
class EvaluationExportDependencies:
    online_db: AsyncSession
    evaluation_db: AsyncSession
    gateway_factory: Callable[[], ObjectStorageGateway]


async def get_export_dependencies(
    online_db: AsyncSession = Depends(get_explicit_transaction_session),
    evaluation_db: AsyncSession = Depends(get_explicit_evaluation_transaction_session),
) -> EvaluationExportDependencies:
    return EvaluationExportDependencies(
        online_db=online_db,
        evaluation_db=evaluation_db,
        gateway_factory=OSSObjectStore,
    )


@router.post(
    "/jobs",
    response_model=GenericResponse[EvaluationJobResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    payload: EvaluationJobCreate,
    context: ControlPlaneContext = Depends(control_write),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.create_job(payload=payload, context=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Job 已创建", data=data)


@router.post(
    "/jobs/export",
    response_model=GenericResponse[EvaluationExportJobResponse],
    status_code=status.HTTP_201_CREATED,
)
async def export_job(
    payload: EvaluationExportJobCreate,
    context: ControlPlaneContext = Depends(control_write),
    dependencies: EvaluationExportDependencies = Depends(get_export_dependencies),
):
    service = EvaluationExportService(
        online_db=dependencies.online_db,
        evaluation_db=dependencies.evaluation_db,
        gateway_factory=dependencies.gateway_factory,
    )
    try:
        data = await service.export_and_create_job(
            payload=payload,
            context=context,
        )
    except Exception as exc:
        await dependencies.online_db.rollback()
        return await rollback_and_map_control_plane(dependencies.evaluation_db, exc)
    return GenericResponse(message="Evaluation 输入已导出并创建 Job", data=data)


@router.get("/jobs", response_model=GenericResponse[EvaluationJobResponse])
async def get_job(
    job_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control_read),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.get_job(job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Job 查询成功", data=data)


@router.post("/jobs/cancel", response_model=GenericResponse[EvaluationJobResponse])
async def cancel_job(
    payload: EvaluationJobStateRequest,
    _: ControlPlaneContext = Depends(control_write),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.cancel_job(payload.id, payload.expected_state_version)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Job 已取消", data=data)


@router.post("/runs", response_model=GenericResponse[EvaluationRunResponse])
async def create_run(
    payload: EvaluationRunCreate,
    _: ControlPlaneContext = Depends(control_write),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.create_run(payload.job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Run 已创建", data=data)


@router.get("/runs", response_model=GenericResponse[list[EvaluationRunResponse]])
async def list_runs(
    job_id: str = Query(..., min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control_read),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.list_runs(job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Run 查询成功", data=data)


@router.get("/runs/detail", response_model=GenericResponse[EvaluationRunResponse])
async def get_run(
    run_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control_read),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.get_run(run_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Run 查询成功", data=data)


@router.get(
    "/artifacts",
    response_model=GenericResponse[list[EvaluationArtifactResponse]],
)
async def list_artifacts(
    job_id: str = Query(..., min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control_read),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.list_artifacts(job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Artifact 查询成功", data=data)


@router.get(
    "/artifacts/detail",
    response_model=GenericResponse[EvaluationArtifactResponse],
)
async def get_artifact(
    artifact_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control_read),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.get_artifact(artifact_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Artifact 查询成功", data=data)
