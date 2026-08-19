from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.stage_checkpoint import StageCheckpoint


class StageCheckpointDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=StageCheckpoint)

    async def create_idempotent(self, values: dict[str, Any]) -> StageCheckpoint | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_stage_checkpoint_task_instance" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, checkpoint_id: str) -> StageCheckpoint | None:
        return await self.get_data(data_id=checkpoint_id, v_return_none=True)

    async def list_for_task(self, task_id: str) -> list[StageCheckpoint]:
        return await self.get_datas(limit=0, task_id=task_id, v_order_field="stage_no", v_return_objs=True)

    async def cas_update(self, *, checkpoint_id: str, expected_version: int, values: dict[str, Any]) -> StageCheckpoint | None:
        allowed = {"status", "lease_owner_id", "lease_generation", "lease_expires_at", "heartbeat_at", "output_json", "output_sha256", "accepted_call_id", "retry_count", "next_retry_at", "error_code", "started_at", "finished_at"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("stage_checkpoint_update_fields_invalid")
        return await self.cas_put_data(data_id=checkpoint_id, expected_version=expected_version, data=values)


__all__ = ["StageCheckpointDal"]
