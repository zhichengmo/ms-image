from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.session_event import XRaySessionEvent


class XRaySessionEventDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRaySessionEvent)

    async def create_event(self, values: dict[str, Any]) -> XRaySessionEvent:
        return await self.create_data(values, v_return_obj=True)

    async def list_for_session(
        self, *, tenant_id: str, session_id: str, page: int = 1, limit: int = 100
    ) -> tuple[list[XRaySessionEvent], int]:
        return await self.get_datas(
            page=page,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.session_id == session_id,
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_count=True,
            v_return_objs=True,
        )
