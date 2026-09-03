from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.pet_info import PetInfo


class PetInfoDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=PetInfo)

    async def search_catalog(
        self, *, species: str, query_key: str | None
    ) -> list[PetInfo]:
        where = [
            self.model.species == species,
            self.model.status == "active",
        ]
        if query_key is not None:
            keyword = f"%{query_key}%"
            where.append(
                or_(
                    self.model.full_name.like(keyword),
                    self.model.name.like(keyword),
                    self.model.english_name.like(keyword),
                    self.model.alias.like(keyword),
                )
            )
        start = select(self.model).order_by(
            self.model.first_letter, self.model.full_name, self.model.id
        )
        return await self.get_datas(
            limit=0,
            v_start_sql=start,
            v_where=where,
            v_return_objs=True,
        )


__all__ = ["PetInfoDal"]
