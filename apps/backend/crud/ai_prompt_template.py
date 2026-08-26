from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_prompt_template import AIPromptTemplate


class AIPromptTemplateDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AIPromptTemplate)

    async def create_idempotent(self, values: dict[str, Any]) -> AIPromptTemplate | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            if "duplicate" not in str(getattr(exc, "orig", exc)).casefold():
                raise
            return None

    async def get_by_id(self, prompt_id: str) -> AIPromptTemplate | None:
        return await self.get_data(data_id=prompt_id, v_return_none=True)

    async def get_by_key_version(self, prompt_key: str, version: str) -> AIPromptTemplate | None:
        return await self.get_data(prompt_key=prompt_key, version=version, v_return_none=True)

    async def page(self, *, page: int, limit: int, prompt_key: str | None, status: str | None) -> tuple[list[AIPromptTemplate], int]:
        return await self.get_datas(page=page, limit=limit, prompt_key=prompt_key, status=status, v_order="desc", v_order_field="created_at", v_return_objs=True, v_return_count=True)

    async def cas_update(self, *, prompt_id: str, expected_version: int, values: dict[str, Any]) -> AIPromptTemplate | None:
        allowed = {"name", "description", "language", "content", "variables_json", "content_sha256", "message_contract_json", "source_receipt_json", "source_receipt_sha256", "status", "validated_at", "retired_at", "updated_by_id"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_prompt_template_update_fields_invalid")
        return await self.cas_put_data(data_id=prompt_id, expected_version=expected_version, data=values)


__all__ = ["AIPromptTemplateDal"]
