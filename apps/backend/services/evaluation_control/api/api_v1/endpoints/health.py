"""Liveness and readiness endpoints for Evaluation Control."""

from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.responses import JSONResponse

from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.evaluation import (
    EvaluationControlHealthResponse,
    EvaluationControlReadinessResponse,
)
from apps.backend.services.evaluation_control.readiness import (
    build_evaluation_control_readiness,
)


router = APIRouter(tags=["Evaluation Control Health"])


@router.get(
    "/health",
    response_model=GenericResponse[EvaluationControlHealthResponse],
)
async def health_check() -> GenericResponse[EvaluationControlHealthResponse]:
    return GenericResponse(
        message="Evaluation Control 服务运行正常",
        data=EvaluationControlHealthResponse(
            status="healthy",
            service="evaluation_control",
            timestamp=datetime.now(timezone.utc),
        ),
    )


@router.get(
    "/readiness",
    response_model=GenericResponse[EvaluationControlReadinessResponse],
    responses={
        503: {
            "model": GenericResponse[EvaluationControlReadinessResponse],
            "description": "Evaluation Control 必需依赖未就绪",
        }
    },
)
async def readiness_check() -> JSONResponse:
    data = await build_evaluation_control_readiness()
    return JSONResponse(
        status_code=200 if data.ready else 503,
        content=GenericResponse(
            success=data.ready,
            message=(
                "Evaluation Control 依赖已就绪"
                if data.ready
                else "Evaluation Control 依赖未就绪"
            ),
            data=data,
        ).model_dump(mode="json"),
    )


__all__ = ["router"]
