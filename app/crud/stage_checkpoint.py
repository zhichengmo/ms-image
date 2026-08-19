from datetime import datetime
from typing import Any

from sqlalchemy import or_
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

    async def claim(self, *, checkpoint_id: str, expected_version: int, owner_id: str, now: datetime, lease_expires_at: datetime) -> StageCheckpoint | None:
        claimed = await self.conditional_update(v_where=[self.model.id == checkpoint_id, self.model.status == "queued", self.model.state_version == expected_version, or_(self.model.lease_expires_at.is_(None), self.model.lease_expires_at <= now)], data={"status": "running", "lease_owner_id": owner_id, "lease_generation": self.model.lease_generation + 1, "lease_expires_at": lease_expires_at, "heartbeat_at": now, "started_at": now})
        if not claimed:
            return None
        return await self.get_data(data_id=checkpoint_id, v_return_none=True, v_expire_all=True)

    async def heartbeat(self, *, checkpoint_id: str, owner_id: str, lease_generation: int, now: datetime, lease_expires_at: datetime) -> bool:
        return await self.conditional_update(v_where=[self.model.id == checkpoint_id, self.model.status == "running", self.model.lease_owner_id == owner_id, self.model.lease_generation == lease_generation, self.model.lease_expires_at > now], data={"heartbeat_at": now, "lease_expires_at": lease_expires_at})

    async def finish_with_lease(self, *, checkpoint_id: str, expected_version: int, owner_id: str, lease_generation: int, now: datetime, values: dict[str, Any]) -> StageCheckpoint | None:
        allowed = {"status", "output_json", "output_sha256", "error_code", "finished_at"}
        if values.get("status") not in {"completed", "failed", "cancelled", "dead_letter"} or not set(values).issubset(allowed):
            raise ValueError("stage_finish_fields_invalid")
        terminal = dict(values)
        terminal.update({"lease_owner_id": None, "lease_expires_at": None, "heartbeat_at": None, "next_retry_at": None})
        return await self.cas_put_data(data_id=checkpoint_id, expected_version=expected_version, data=terminal, v_where=[self.model.status == "running", self.model.lease_owner_id == owner_id, self.model.lease_generation == lease_generation, self.model.lease_expires_at > now])

    async def list_expired_running(self, *, now: datetime, limit: int) -> list[StageCheckpoint]:
        return await self.get_datas(page=1, limit=limit, v_where=[self.model.status == "running", self.model.lease_expires_at.is_not(None), self.model.lease_expires_at <= now], v_order_field="lease_expires_at", v_return_objs=True)

    async def recover_expired(self, *, checkpoint_id: str, expected_version: int, lease_generation: int, now: datetime, max_attempts: int) -> StageCheckpoint | None:
        row = await self.get_by_id(checkpoint_id)
        if row is None:
            return None
        exhausted = row.retry_count + 1 >= max_attempts
        return await self.cas_put_data(data_id=checkpoint_id, expected_version=expected_version, data={"status": "dead_letter" if exhausted else "queued", "lease_owner_id": None, "lease_expires_at": None, "heartbeat_at": None, "retry_count": row.retry_count + 1, "next_retry_at": None if exhausted else now, "error_code": "stage_attempts_exhausted" if exhausted else "stage_lease_expired", "finished_at": now if exhausted else None}, v_where=[self.model.status == "running", self.model.lease_generation == lease_generation, self.model.lease_expires_at <= now])


__all__ = ["StageCheckpointDal"]
