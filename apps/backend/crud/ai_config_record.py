from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_config_record import AIConfigRecord


class AIConfigRecordDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AIConfigRecord)

    async def create_idempotent(self, values: dict[str, Any]) -> AIConfigRecord | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_ai_config_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, config_id: str) -> AIConfigRecord | None:
        return await self.get_data(data_id=config_id, v_return_none=True)

    async def get_active(self, activation_slot: str) -> AIConfigRecord | None:
        return await self.get_data(activation_slot=activation_slot, status="active", v_return_none=True)

    async def cas_update(self, *, config_id: str, expected_version: int, values: dict[str, Any]) -> AIConfigRecord | None:
        allowed = {"activation_slot", "status", "error_code"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_config_update_fields_invalid")
        return await self.cas_put_data(data_id=config_id, expected_version=expected_version, data=values)


__all__ = ["AIConfigRecordDal"]
