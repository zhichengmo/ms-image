from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_api_connection import AIAPIConnection


class AIAPIConnectionDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AIAPIConnection)

    async def create_idempotent(self, values: dict[str, Any]) -> AIAPIConnection | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            if "duplicate" not in str(getattr(exc, "orig", exc)).casefold():
                raise
            return None

    async def get_by_id(self, connection_id: str) -> AIAPIConnection | None:
        return await self.get_data(data_id=connection_id, v_return_none=True)

    async def get_by_key_version(self, connection_key: str, version: str) -> AIAPIConnection | None:
        return await self.get_data(connection_key=connection_key, version=version, v_return_none=True)

    async def page(self, *, page: int, limit: int, provider_type: str | None, status: str | None) -> tuple[list[AIAPIConnection], int]:
        return await self.get_datas(page=page, limit=limit, provider_type=provider_type, status=status, v_order="desc", v_order_field="created_at", v_return_objs=True, v_return_count=True)

    async def cas_update(self, *, connection_id: str, expected_version: int, values: dict[str, Any]) -> AIAPIConnection | None:
        allowed = {"name", "provider_type", "api_format", "base_url", "region", "capability_json", "connection_sha256", "status", "validated_at", "retired_at", "updated_by_id"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_api_connection_update_fields_invalid")
        return await self.cas_put_data(data_id=connection_id, expected_version=expected_version, data=values)


__all__ = ["AIAPIConnectionDal"]
