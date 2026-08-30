from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.study import Study


class StudyDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Study)

    async def create_idempotent(self, values: dict[str, Any]) -> Study | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_study_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, study_id: str) -> Study | None:
        return await self.get_data(data_id=study_id, v_return_none=True)

    async def get_by_id_for_update(self, study_id: str) -> Study | None:
        return await self.get_data(
            data_id=study_id,
            v_start_sql=select(self.model).with_for_update().execution_options(
                populate_existing=True
            ),
            v_return_none=True,
        )

    async def get_by_source(
        self, *, session_id: str, source_study_id: str
    ) -> Study | None:
        return await self.get_data(
            session_id=session_id,
            source_study_id=source_study_id,
            v_return_none=True,
        )

    async def list_for_session(self, session_id: str) -> list[Study]:
        return await self.get_datas(
            limit=0,
            session_id=session_id,
            v_order="desc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def cas_revision(
        self,
        *,
        study_id: str,
        expected_version: int,
        current_revision_id: str,
        values: dict[str, Any],
    ) -> Study | None:
        allowed = {
            "revision_no",
            "revision_id",
            "revision_reason",
            "revision_changed_at",
            "resolved_manifest_sha256",
            "completeness_status",
            "identity_status",
            "status",
            "ready_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("study_revision_fields_invalid")
        return await self.cas_put_data(
            data_id=study_id,
            expected_version=expected_version,
            data=values,
            v_where=[self.model.revision_id == current_revision_id],
        )

    async def cas_finalize(
        self,
        *,
        study_id: str,
        expected_version: int,
        current_revision_id: str,
        values: dict[str, Any],
    ) -> Study | None:
        allowed = {"completeness_status", "status", "ready_at"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("study_finalize_fields_invalid")
        return await self.cas_put_data(
            data_id=study_id,
            expected_version=expected_version,
            data=values,
            v_where=[self.model.revision_id == current_revision_id],
        )


__all__ = ["StudyDal"]
