from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_model_pool import AIModelPool


class AIModelPoolDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AIModelPool)

    async def create_idempotent(self, values: dict[str, Any]) -> AIModelPool | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            if "duplicate" not in str(getattr(exc, "orig", exc)).casefold():
                raise
            return None

    async def get_by_id(self, pool_id: str) -> AIModelPool | None:
        return await self.get_data(data_id=pool_id, v_return_none=True)

    async def get_by_key_version(self, pool_key: str, version: str) -> AIModelPool | None:
        return await self.get_data(pool_key=pool_key, version=version, v_return_none=True)

    async def page(self, *, page: int, limit: int, execution_mode: str | None, status: str | None) -> tuple[list[AIModelPool], int]:
        return await self.get_datas(page=page, limit=limit, execution_mode=execution_mode, status=status, v_order="desc", v_order_field="created_at", v_return_objs=True, v_return_count=True)

    async def cas_update(self, *, pool_id: str, expected_version: int, values: dict[str, Any]) -> AIModelPool | None:
        allowed = {"name", "description", "execution_mode", "winner_policy", "lane_count", "lane_plan_json", "pool_sha256", "status", "validated_at", "retired_at", "updated_by_id"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_model_pool_update_fields_invalid")
        return await self.cas_put_data(data_id=pool_id, expected_version=expected_version, data=values)


__all__ = ["AIModelPoolDal"]
