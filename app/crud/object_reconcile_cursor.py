from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.object_reconcile_cursor import ObjectReconcileCursor


class ObjectReconcileCursorDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=ObjectReconcileCursor)

    async def get_by_key(self, cursor_key: str) -> ObjectReconcileCursor | None:
        return await self.get_data(cursor_key=cursor_key, v_return_none=True)

    async def create_idempotent(self, cursor_key: str) -> ObjectReconcileCursor | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data({"cursor_key": cursor_key, "state_version": 0, "lease_generation": 0}, v_return_obj=True)
        except IntegrityError:
            return None

    async def claim(self, *, cursor_key: str, owner_id: str, now: datetime, lease_expires_at: datetime) -> ObjectReconcileCursor | None:
        claimed = await self.conditional_update(v_where=[self.model.cursor_key == cursor_key, or_(self.model.next_scan_at.is_(None), self.model.next_scan_at <= now), or_(self.model.lease_expires_at.is_(None), self.model.lease_expires_at <= now)], data={"lease_owner_id": owner_id, "lease_generation": self.model.lease_generation + 1, "lease_expires_at": lease_expires_at, "error_code": None})
        if not claimed:
            return None
        return await self.get_data(cursor_key=cursor_key, v_return_none=True, v_expire_all=True)

    async def heartbeat(
        self,
        *,
        cursor_id: str,
        owner_id: str,
        lease_generation: int,
        now: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        if lease_generation < 1 or lease_expires_at <= now:
            raise ValueError("object_reconcile_cursor_heartbeat_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == cursor_id,
                self.model.lease_owner_id == owner_id,
                self.model.lease_generation == lease_generation,
                self.model.lease_expires_at > now,
            ],
            data={"lease_expires_at": lease_expires_at},
        )

    async def advance(self, *, cursor_id: str, expected_version: int, owner_id: str, lease_generation: int, now: datetime, last_ready_updated_at: datetime | None, last_ready_image_id: str | None, next_scan_at: datetime) -> ObjectReconcileCursor | None:
        return await self.cas_put_data(data_id=cursor_id, expected_version=expected_version, data={"last_ready_updated_at": last_ready_updated_at, "last_ready_image_id": last_ready_image_id, "next_scan_at": next_scan_at, "lease_owner_id": None, "lease_expires_at": None, "error_code": None}, v_where=[self.model.lease_owner_id == owner_id, self.model.lease_generation == lease_generation, self.model.lease_expires_at > now])


__all__ = ["ObjectReconcileCursorDal"]
