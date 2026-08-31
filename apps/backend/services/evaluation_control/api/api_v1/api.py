"""Evaluation Control API v1 router registration."""

from fastapi import APIRouter

from apps.backend.services.evaluation_control.api.api_v1.endpoints import evaluation, health


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(evaluation.router)

__all__ = ["api_router"]
