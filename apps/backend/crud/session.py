from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.session import Session


class SessionDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Session)

    async def create_idempotent(self, values: dict[str, Any]) -> Session | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_session_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, session_id: str) -> Session | None:
        return await self.get_data(data_id=session_id, v_return_none=True)

    async def get_by_request_id(self, request_id: str) -> Session | None:
        return await self.get_data(request_id=request_id, v_return_none=True)

    async def get_by_source(
        self, *, source_system: str, source_session_id: str
    ) -> Session | None:
        return await self.get_data(
            source_system=source_system,
            source_session_id=source_session_id,
            v_return_none=True,
        )

    async def cas_update(self, *, session_id: str, expected_version: int, values: dict[str, Any]) -> Session | None:
        allowed = {
            "status",
            "completed_at",
            "closed_at",
            "cancelled_by_id",
            "cancel_reason",
            "cancelled_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("session_update_fields_invalid")
        return await self.cas_put_data(
            data_id=session_id,
            expected_version=expected_version,
            data=values,
        )


__all__ = ["SessionDal"]
