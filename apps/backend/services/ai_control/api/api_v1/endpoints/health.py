"""Liveness and readiness endpoints for the AI Control application."""

from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.responses import JSONResponse

from apps.backend.schemas.ai_control import (
    AIControlHealthResponse,
    AIControlReadinessResponse,
)
from apps.backend.schemas.base import GenericResponse
from apps.backend.services.ai_control.readiness import build_ai_control_readiness


router = APIRouter(tags=["AI Control Health"])


@router.get("/health", response_model=GenericResponse[AIControlHealthResponse])
async def health_check() -> GenericResponse[AIControlHealthResponse]:
    return GenericResponse(
        message="AI Control 服务运行正常",
        data=AIControlHealthResponse(
            status="healthy",
            service="ai_control",
            timestamp=datetime.now(timezone.utc),
        ),
    )


@router.get(
    "/readiness",
    response_model=GenericResponse[AIControlReadinessResponse],
    responses={
        503: {
            "model": GenericResponse[AIControlReadinessResponse],
            "description": "AI Control 必需依赖未就绪",
        }
    },
)
async def readiness_check() -> JSONResponse:
    data = await build_ai_control_readiness()
    return JSONResponse(
        status_code=200 if data.ready else 503,
        content=GenericResponse(
            success=data.ready,
            message=(
                "AI Control 依赖已就绪"
                if data.ready
                else "AI Control 依赖未就绪"
            ),
            data=data,
        ).model_dump(mode="json"),
    )


__all__ = ["router"]
