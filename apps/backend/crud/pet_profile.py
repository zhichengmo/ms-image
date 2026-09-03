from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.pet_profile import PetProfile


class PetProfileDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=PetProfile)

    async def create_idempotent(self, values: dict[str, Any]) -> PetProfile | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_pet_profile_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, pet_profile_id: str) -> PetProfile | None:
        return await self.get_data(data_id=pet_profile_id, v_return_none=True)

    async def get_by_id_for_update(self, pet_profile_id: str) -> PetProfile | None:
        return await self.get_data(
            data_id=pet_profile_id,
            v_start_sql=select(self.model)
            .with_for_update()
            .execution_options(populate_existing=True),
            v_return_none=True,
        )

    async def get_by_request_id(self, request_id: str) -> PetProfile | None:
        return await self.get_data(request_id=request_id, v_return_none=True)

    async def get_by_source(
        self, *, source_system: str, source_pet_id: str
    ) -> PetProfile | None:
        return await self.get_data(
            source_system=source_system,
            source_pet_id=source_pet_id,
            v_return_none=True,
        )

    async def page_for_owner(
        self,
        *,
        owner_id: str,
        status: str | None,
        species: str | None,
        query_key: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[PetProfile], int]:
        if page < 1 or limit < 1 or limit > 100:
            raise ValueError("pet_profile_page_invalid")
        where = [self.model.owner_id == owner_id]
        if status is not None:
            where.append(self.model.status == status)
        if species is not None:
            where.append(self.model.species == species)
        if query_key is not None:
            keyword = f"%{query_key}%"
            where.append(
                or_(
                    self.model.name.like(keyword),
                    self.model.breed_name.like(keyword),
                )
            )
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

    async def cas_update(
        self,
        *,
        pet_profile_id: str,
        expected_version: int,
        values: dict[str, Any],
    ) -> PetProfile | None:
        allowed = {
            "name",
            "species",
            "breed_name",
            "sex",
            "neuter_status",
            "vaccination_status",
            "birthday",
            "avatar_object_key",
            "weight_kg",
            "weight_measured_at",
            "last_vaccinated_at",
            "last_examined_at",
            "diet_notes",
            "disease_history",
            "allergy_history",
            "family_history",
            "care_notes",
            "health_notes",
            "medical_history",
            "status",
            "archived_at",
            "archived_by_id",
            "archive_reason",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("pet_profile_update_fields_invalid")
        return await self.cas_put_data(
            data_id=pet_profile_id,
            expected_version=expected_version,
            data=values,
        )


__all__ = ["PetProfileDal"]
