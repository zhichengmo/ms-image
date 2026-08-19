from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_session, require_control_plane_scope
from app.core.contexts import ControlPlaneContext
from app.schemas.ai_config import AIConfigActivateRequest, AIConfigCreate, AIConfigResponse
from app.schemas.base import GenericResponse
from app.service.ai_config_service import AIConfigService

router = APIRouter(prefix="/ai-configs", tags=["AI Config ControlPlane"])
control = require_control_plane_scope()

async def get_service(db: AsyncSession = Depends(get_async_session)) -> AIConfigService:
    return AIConfigService(db)

@router.post("", response_model=GenericResponse[AIConfigResponse], status_code=status.HTTP_201_CREATED)
async def create(payload: AIConfigCreate, _: ControlPlaneContext = Depends(control), service: AIConfigService = Depends(get_service)):
    return GenericResponse(message="AI Config 已创建", data=await service.create(payload))

@router.post("/validate", response_model=GenericResponse[AIConfigResponse])
async def validate(payload: AIConfigActivateRequest, _: ControlPlaneContext = Depends(control), service: AIConfigService = Depends(get_service)):
    return GenericResponse(message="AI Config 已验证", data=await service.validate(payload.id, payload.expected_state_version))

@router.post("/activate", response_model=GenericResponse[AIConfigResponse])
async def activate(payload: AIConfigActivateRequest, _: ControlPlaneContext = Depends(control), service: AIConfigService = Depends(get_service)):
    return GenericResponse(message="AI Config 已激活", data=await service.activate(payload.id, payload.expected_state_version))

@router.get("", response_model=GenericResponse[AIConfigResponse])
async def get_active(config_key: str = Query(...), modality_type: str = Query(...), task_type: str = Query(...), _: ControlPlaneContext = Depends(control), service: AIConfigService = Depends(get_service)):
    return GenericResponse(message="Active AI Config 查询成功", data=await service.get_active(config_key=config_key, modality_type=modality_type, task_type=task_type))
