from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.core.crud import DalBase
from apps.runtime.models.series import Series


class SeriesDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Series)

    async def create_idempotent(self, values: dict[str, Any]) -> Series | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_series_record_study_key" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, series_id: str) -> Series | None:
        return await self.get_data(data_id=series_id, v_return_none=True)

    async def get_by_key(self, *, study_id: str, series_key: str) -> Series | None:
        return await self.get_data(
            study_id=study_id, series_key=series_key, v_return_none=True
        )

    async def list_for_study(self, study_id: str) -> list[Series]:
        return await self.get_datas(
            limit=0,
            study_id=study_id,
            v_order_field="series_no",
            v_return_objs=True,
        )

    async def cas_update(
        self, *, series_id: str, expected_version: int, values: dict[str, Any]
    ) -> Series | None:
        allowed = {
            "actual_image_count",
            "manifest_sha256",
            "status",
            "ready_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("series_update_fields_invalid")
        return await self.cas_put_data(
            data_id=series_id, expected_version=expected_version, data=values
        )


__all__ = ["SeriesDal"]
