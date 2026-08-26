"""DalBase accessors for physical AI Provider attempts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.crud import DalBase
from apps.backend.models.ai_call_attempt import AICallAttempt


class AICallAttemptDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=AICallAttempt)

    async def create_idempotent(self, values: dict[str, Any]) -> AICallAttempt | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_ai_call_attempt_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, attempt_id: str) -> AICallAttempt | None:
        return await self.get_data(data_id=attempt_id, v_return_none=True)

    async def get_by_id_for_update(self, attempt_id: str) -> AICallAttempt | None:
        return await self.get_data(
            data_id=attempt_id,
            v_start_sql=select(self.model).with_for_update(),
            v_return_none=True,
            v_expire_all=True,
        )

    async def get_by_call_attempt_no(
        self, *, ai_call_id: str, attempt_no: int
    ) -> AICallAttempt | None:
        return await self.get_data(
            ai_call_id=ai_call_id,
            attempt_no=attempt_no,
            v_return_none=True,
        )

    async def get_by_call_attempt_no_for_update(
        self, *, ai_call_id: str, attempt_no: int
    ) -> AICallAttempt | None:
        return await self.get_data(
            ai_call_id=ai_call_id,
            attempt_no=attempt_no,
            v_start_sql=select(self.model).with_for_update(),
            v_return_none=True,
            v_expire_all=True,
        )

    async def get_by_physical_attempt_key(
        self, physical_attempt_key: str
    ) -> AICallAttempt | None:
        return await self.get_data(
            physical_attempt_key=physical_attempt_key,
            v_return_none=True,
        )

    async def cas_update(
        self, *, attempt_id: str, expected_version: int, values: dict[str, Any]
    ) -> AICallAttempt | None:
        allowed = {
            "actual_model",
            "sent_image_manifest_sha256",
            "image_count_sent",
            "image_receipt_json",
            "provider_request_id",
            "usage_json",
            "response_object_ref_json",
            "response_sha256",
            "parsed_result_json",
            "error_code",
            "status",
            "sent_at",
            "finished_at",
            "next_reconcile_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("ai_call_attempt_update_fields_invalid")
        return await self.cas_put_data(
            data_id=attempt_id,
            expected_version=expected_version,
            data=values,
        )

    async def page_reconcile_candidates(
        self, *, now: datetime, limit: int
    ) -> list[AICallAttempt]:
        if limit < 1:
            raise ValueError("ai_call_attempt_reconcile_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "unknown",
                self.model.next_reconcile_at.is_not(None),
                self.model.next_reconcile_at <= now,
            ],
            v_order_field="next_reconcile_at",
            v_return_objs=True,
        )

    async def claim_reconcile_candidate(
        self,
        *,
        attempt_id: str,
        expected_version: int,
        now: datetime,
        lease_expires_at: datetime,
    ) -> AICallAttempt | None:
        if lease_expires_at <= now:
            raise ValueError("ai_call_attempt_reconcile_lease_invalid")
        return await self.cas_put_data(
            data_id=attempt_id,
            expected_version=expected_version,
            data={"next_reconcile_at": lease_expires_at},
            v_where=[
                self.model.status == "unknown",
                self.model.next_reconcile_at.is_not(None),
                self.model.next_reconcile_at <= now,
            ],
        )


__all__ = ["AICallAttemptDal"]
