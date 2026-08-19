from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.report import Report


class ReportDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Report)

    async def create_idempotent(self, values: dict[str, Any]) -> Report | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_report_record_task_revision" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, report_id: str) -> Report | None:
        return await self.get_data(data_id=report_id, v_return_none=True)

    async def list_for_task(self, task_id: str) -> list[Report]:
        return await self.get_datas(limit=0, task_id=task_id, v_order="desc", v_order_field="revision_no", v_return_objs=True)

    async def cas_update(self, *, report_id: str, expected_version: int, values: dict[str, Any]) -> Report | None:
        allowed = {"status", "render_manifest_json", "published_at", "voided_at", "error_code"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("report_update_fields_invalid")
        return await self.cas_put_data(data_id=report_id, expected_version=expected_version, data=values)


__all__ = ["ReportDal"]
