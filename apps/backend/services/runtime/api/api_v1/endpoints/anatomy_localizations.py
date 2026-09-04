from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.anatomy_localization_contract import (
    ANATOMY_LABEL_CONTRACT_V1,
    load_anatomy_label_contract,
)
from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.core.dependencies import (
    AnatomyLocalizationDisplayDependencies,
    get_anatomy_localization_display_dependencies,
    get_async_session,
    require_caller_scope,
)
from apps.backend.schemas.anatomy_localization import (
    AnatomyLocalizationLegendLabelResponse,
    AnatomyLocalizationLegendResponse,
    AnatomyLocalizationLegendSystemResponse,
    AnatomyLocalizationPrepareViewRequest,
    AnatomyLocalizationPrepareViewResponse,
    AnatomyLocalizationResponse,
)
from apps.backend.schemas.base import GenericResponse
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.task_service import TaskService

router = APIRouter(
    prefix="/anatomy-localizations",
    tags=["Anatomy localizations"],
)
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)

_SYSTEM_DISPLAY = {
    "cardiovascular": ("心血管系统", "#D64545"),
    "respiratory": ("呼吸系统", "#2D7DD2"),
    "digestive": ("消化系统", "#D97706"),
    "urogenital": ("泌尿生殖系统", "#7C3AED"),
    "axial_skeletal": ("中轴骨骼", "#475569"),
    "appendicular": ("四肢骨骼", "#059669"),
}
_LABEL_DISPLAY = {
    "heart": "心脏",
    "aorta": "主动脉",
    "pulmonary_artery": "肺动脉",
    "caudal_vena_cava": "后腔静脉",
    "lung_left": "左肺",
    "lung_right": "右肺",
    "trachea": "气管",
    "carina": "气管隆嵴",
    "diaphragm": "膈肌",
    "mediastinum": "纵隔",
    "liver": "肝脏",
    "stomach": "胃",
    "small_intestine": "小肠",
    "large_intestine": "大肠",
    "spleen": "脾脏",
    "kidney_left": "左肾",
    "kidney_right": "右肾",
    "bladder": "膀胱",
    "thoracic_spine": "胸椎",
    "lumbar_spine": "腰椎",
    "cervical_spine": "颈椎",
    "caudal_vertebrae": "尾椎",
    "ribs": "肋骨",
    "sternum": "胸骨",
    "pelvis": "骨盆",
    "skull": "颅骨",
    "scapula": "肩胛骨",
    "humerus": "肱骨",
    "radius": "桡骨",
    "ulna": "尺骨",
    "femur": "股骨",
    "tibia": "胫骨",
    "fibula": "腓骨",
    "patella": "髌骨",
    "carpal_bones": "腕骨",
    "tarsal_bones": "跗骨",
    "metacarpal_bones": "掌骨",
    "metatarsal_bones": "跖骨",
}


def _build_legend() -> AnatomyLocalizationLegendResponse:
    labels_by_system = load_anatomy_label_contract()
    if tuple(labels_by_system) != tuple(_SYSTEM_DISPLAY):
        raise RuntimeError("anatomy_localization_legend_system_drift")
    contract_labels = {
        label for labels in labels_by_system.values() for label in labels
    }
    if contract_labels != set(_LABEL_DISPLAY):
        raise RuntimeError("anatomy_localization_legend_label_drift")
    systems = []
    for system_order, (system, labels) in enumerate(
        labels_by_system.items(),
        start=1,
    ):
        display_name, color = _SYSTEM_DISPLAY[system]
        systems.append(
            AnatomyLocalizationLegendSystemResponse(
                system=system,
                display_name=display_name,
                color=color,
                sort_order=system_order,
                labels=[
                    AnatomyLocalizationLegendLabelResponse(
                        label=label,
                        display_name=_LABEL_DISPLAY[label],
                        sort_order=label_order,
                    )
                    for label_order, label in enumerate(labels, start=1)
                ],
            )
        )
    return AnatomyLocalizationLegendResponse(
        label_contract_version=ANATOMY_LABEL_CONTRACT_V1,
        locale="zh-CN",
        systems=systems,
    )


async def get_task_service(
    db: AsyncSession = Depends(get_async_session),
) -> TaskService:
    return TaskService(db)


@router.get("", response_model=GenericResponse[AnatomyLocalizationResponse])
async def get_anatomy_localization(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_anatomy_localization(
            task_id=task_id,
            caller=context,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="器官定位结果查询成功", data=data)


@router.post(
    "/prepare-view",
    response_model=GenericResponse[AnatomyLocalizationPrepareViewResponse],
)
async def prepare_anatomy_localization_view(
    payload: AnatomyLocalizationPrepareViewRequest,
    context: CallerContext = Depends(caller),
    dependencies: AnatomyLocalizationDisplayDependencies = Depends(
        get_anatomy_localization_display_dependencies
    ),
):
    try:
        data = await dependencies.service.prepare_anatomy_localization_view(
            payload=payload,
            caller=context,
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="器官定位展示影像已准备", data=data)


@router.get(
    "/legend",
    response_model=GenericResponse[AnatomyLocalizationLegendResponse],
)
async def get_anatomy_localization_legend(
    label_contract_version: Literal["xray-anatomy-labels.v1"] = Query(
        ANATOMY_LABEL_CONTRACT_V1
    ),
    locale: Literal["zh-CN"] = Query("zh-CN"),
    _context: CallerContext = Depends(caller),
):
    del label_contract_version, locale, _context
    return GenericResponse(message="器官定位图例查询成功", data=_build_legend())


__all__ = ["router"]
