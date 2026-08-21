from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.task import Task


class TaskDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Task)

    async def create_idempotent(self, values: dict[str, Any]) -> Task | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_task_record_business_key" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, task_id: str) -> Task | None:
        return await self.get_data(data_id=task_id, v_return_none=True)

    async def get_by_business_key(self, business_key: str) -> Task | None:
        return await self.get_data(business_key=business_key, v_return_none=True)

    async def cas_update(self, *, task_id: str, expected_version: int, values: dict[str, Any]) -> Task | None:
        allowed = {"execution_status", "ai_medical_status", "budget_consumed_json", "current_report_id", "next_retry_at", "error_code", "error_message", "cancel_requested_by_id", "cancel_reason", "cancel_requested_at", "started_at", "finished_at"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("task_update_fields_invalid")
        return await self.cas_put_data(data_id=task_id, expected_version=expected_version, data=values)


__all__ = ["TaskDal"]
