from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_v1.endpoints.control_plane_errors import rollback_and_map_control_plane
from app.api.deps import require_control_plane_scope
from app.core.async_db import get_evaluation_async_session
from app.core.config import settings
from app.core.contexts import ControlPlaneContext
from app.schemas.base import GenericResponse
from app.schemas.evaluation import (
    EvaluationArtifactResponse,
    EvaluationJobCreate,
    EvaluationJobResponse,
    EvaluationJobStateRequest,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from app.service.evaluation_service import EvaluationService


router = APIRouter(prefix="/evaluation", tags=["Evaluation ControlPlane"])
control = require_control_plane_scope(settings.EVALUATION_REQUIRED_SCOPE)


async def get_service(
    db: AsyncSession = Depends(get_evaluation_async_session),
) -> EvaluationService:
    return EvaluationService(db)


@router.post(
    "/jobs",
    response_model=GenericResponse[EvaluationJobResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    payload: EvaluationJobCreate,
    context: ControlPlaneContext = Depends(control),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.create_job(payload=payload, context=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Job 已创建", data=data)


@router.get("/jobs", response_model=GenericResponse[EvaluationJobResponse])
async def get_job(
    job_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control),
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
    _: ControlPlaneContext = Depends(control),
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
    _: ControlPlaneContext = Depends(control),
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
    _: ControlPlaneContext = Depends(control),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.list_runs(job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Run 查询成功", data=data)


@router.get(
    "/artifacts",
    response_model=GenericResponse[list[EvaluationArtifactResponse]],
)
async def list_artifacts(
    job_id: str = Query(..., min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control),
    service: EvaluationService = Depends(get_service),
    db: AsyncSession = Depends(get_evaluation_async_session),
):
    try:
        data = await service.list_artifacts(job_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Evaluation Artifact 查询成功", data=data)
