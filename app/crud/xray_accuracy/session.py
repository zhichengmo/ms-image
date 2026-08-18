from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.crud import DalBase
from app.models.xray_accuracy.session import XRaySession


class XRaySessionDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRaySession)

    async def create_session(self, values: dict[str, Any]) -> XRaySession:
        return await self.create_data(values, v_return_obj=True)

    async def get_by_request(
        self, *, tenant_id: str, request_id: str
    ) -> XRaySession | None:
        return await self.get_data(
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.request_id == request_id,
            ],
            v_return_none=True,
        )

    async def create_idempotent(self, values: dict[str, Any]) -> XRaySession | None:
        try:
            async with self.db.begin_nested():
                obj = self.model(**values)
                await self.flush(obj)
            return obj
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_xray_session_tenant_request" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, *, tenant_id: str, session_id: str) -> XRaySession | None:
        return await self.get_data(
            data_id=session_id,
            v_where=[self.model.tenant_id == tenant_id],
            v_return_none=True,
        )

    async def list_for_tenant(
        self, *, tenant_id: str, page: int, limit: int
    ) -> tuple[list[XRaySession], int]:
        return await self.get_datas(
            page=page,
            limit=limit,
            v_where=[self.model.tenant_id == tenant_id],
            v_order="desc",
            v_order_field="created_at",
            v_return_count=True,
            v_return_objs=True,
        )

    async def update_status(
        self,
        *,
        tenant_id: str,
        session_id: str,
        expected_status: str,
        values: dict[str, Any],
    ) -> XRaySession | None:
        allowed = {"session_status", "closed_at"}
        if not set(values).issubset(allowed):
            raise ValueError("session_update_field_invalid")
        changed = await self.conditional_update(
            v_where=[
                self.model.id == session_id,
                self.model.tenant_id == tenant_id,
                self.model.session_status == expected_status,
            ],
            data=values,
        )
        if not changed:
            return None
        return await self.get_by_id(tenant_id=tenant_id, session_id=session_id)
