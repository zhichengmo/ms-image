from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.pet_profile_history import PetProfileHistory


class PetProfileHistoryDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=PetProfileHistory)

    async def create_history(self, values: dict[str, Any]) -> PetProfileHistory:
        return await self.create_data(values, v_return_obj=True)

    async def page_for_profile(
        self,
        *,
        pet_profile_id: str,
        operation_type: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[PetProfileHistory], int]:
        if page < 1 or limit < 1 or limit > 100:
            raise ValueError("pet_profile_history_page_invalid")
        where = [self.model.pet_profile_id == pet_profile_id]
        if operation_type is not None:
            where.append(self.model.operation_type == operation_type)
        start = select(self.model).order_by(
            self.model.created_at.desc(), self.model.id.desc()
        )
        return await self.get_datas(
            page=page,
            limit=limit,
            v_start_sql=start,
            v_where=where,
            v_return_count=True,
            v_return_objs=True,
        )


__all__ = ["PetProfileHistoryDal"]
