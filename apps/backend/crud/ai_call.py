from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_call import AICall


class AICallDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AICall)

    async def create_idempotent(self, values: dict[str, Any]) -> AICall | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_ai_call_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, call_id: str) -> AICall | None:
        return await self.get_data(data_id=call_id, v_return_none=True)

    async def get_by_logical_key(self, logical_call_key: str) -> AICall | None:
        return await self.get_data(logical_call_key=logical_call_key, v_return_none=True)

    async def get_by_logical_key_for_update(
        self, logical_call_key: str
    ) -> AICall | None:
        """Use a current, locking read before a budget reservation/create pair."""
        return await self.get_data(
            logical_call_key=logical_call_key,
            v_start_sql=select(self.model).with_for_update(),
            v_return_none=True,
            v_expire_all=True,
        )

    async def operational_snapshot(self) -> dict[str, Any]:
        counts = {
            status: await self.get_count(status=status)
            for status in ("prepared", "sent", "succeeded", "failed", "unknown")
        }
        oldest_unknown = await self.get_datas(
            page=1,
            limit=1,
            status="unknown",
            v_order_field="created_at",
            v_return_objs=True,
        )
        return {
            "counts": counts,
            "oldest_unknown_created_at": (
                oldest_unknown[0].created_at if oldest_unknown else None
            ),
        }

    async def cas_update(self, *, call_id: str, expected_version: int, values: dict[str, Any]) -> AICall | None:
        allowed = {"provider_request_id", "actual_model", "sent_image_manifest_sha256", "image_count_sent", "image_receipt_json", "attempt_count", "winner_attempt_id", "status", "result_disposition", "response_object_ref_json", "parsed_result_json", "response_sha256", "error_code", "next_reconcile_at", "started_at", "sent_at", "finished_at"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_call_update_fields_invalid")
        return await self.cas_put_data(data_id=call_id, expected_version=expected_version, data=values)


__all__ = ["AICallDal"]
