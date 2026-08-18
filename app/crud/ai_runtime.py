"""DALs for the legacy AI configuration chain.

Every method delegates to DalBase; the Service layer owns the multi-table
resolution and secret lookup policy.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.ai_runtime import AiApiConnection, AiConfig, AiModelPool, AiPromptTemplate, GptConfigItem


class AiConfigDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AiConfig)

    async def get_active_by_version(self, version: str) -> AiConfig | None:
        return await self.get_data(v_where=[self.model.version == version, self.model.is_del == 0], v_return_none=True)


class AiPromptTemplateDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AiPromptTemplate)

    async def get_active_by_id(self, template_id: str) -> AiPromptTemplate | None:
        return await self.get_data(
            data_id=template_id,
            v_where=[self.model.is_del == 0],
            v_return_none=True,
        )

    async def list_active_by_ids(self, template_ids: list[str]) -> list[AiPromptTemplate]:
        if not template_ids:
            return []
        rows = await self.get_datas(
            limit=0,
            v_where=[self.model.id.in_(template_ids), self.model.is_del == 0],
            v_return_objs=True,
        )
        by_id = {str(row.id): row for row in rows}
        return [by_id[item] for item in template_ids if item in by_id]


class GptConfigItemDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=GptConfigItem)

    async def list_active_by_ids(self, item_ids: list[str]) -> list[GptConfigItem]:
        if not item_ids:
            return []
        rows = await self.get_datas(
            limit=0,
            v_where=[self.model.id.in_(item_ids), self.model.is_del == 0],
            v_return_objs=True,
        )
        by_id = {str(row.id): row for row in rows}
        return [by_id[item] for item in item_ids if item in by_id]


class AiModelPoolDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AiModelPool)

    async def get_by_id(self, pool_id: str) -> AiModelPool | None:
        return await self.get_data(data_id=pool_id, v_where=[self.model.id == pool_id], v_return_none=True)


class AiApiConnectionDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AiApiConnection)

    async def list_active_by_ids(self, connection_ids: list[str]) -> list[AiApiConnection]:
        if not connection_ids:
            return []
        rows = await self.get_datas(
            limit=0,
            v_where=[self.model.id.in_(connection_ids), self.model.is_del == 0],
            v_return_objs=True,
        )
        by_id = {str(row.id): row for row in rows}
        return [by_id[item] for item in connection_ids if item in by_id]


__all__ = ["AiConfigDal", "AiPromptTemplateDal", "GptConfigItemDal", "AiModelPoolDal", "AiApiConnectionDal"]
