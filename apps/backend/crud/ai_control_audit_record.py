from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_control_audit_record import AIControlAuditRecord


class AIControlAuditRecordDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AIControlAuditRecord)

    async def append_idempotent(self, values: dict[str, Any]) -> AIControlAuditRecord | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            if "duplicate" not in str(getattr(exc, "orig", exc)).casefold():
                raise
            return None

    async def get_by_command(self, *, request_id: str, resource_type: str, action_type: str) -> AIControlAuditRecord | None:
        return await self.get_data(request_id=request_id, resource_type=resource_type, action_type=action_type, v_return_none=True)

    async def page(self, *, page: int, limit: int, resource_type: str | None, resource_id: str | None, actor_id: str | None) -> tuple[list[AIControlAuditRecord], int]:
        return await self.get_datas(page=page, limit=limit, resource_type=resource_type, resource_id=resource_id, actor_id=actor_id, v_order="desc", v_order_field="created_at", v_return_objs=True, v_return_count=True)


__all__ = ["AIControlAuditRecordDal"]
