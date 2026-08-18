import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.outbox import Outbox
from app.schemas.outbox import ValidateImageMessage


class OutboxDal(DalBase):
    IMAGE_MESSAGE_VERSION = "image-validation.v1"
    IMAGE_DESTINATION_KEY = "imaging.image.validate"

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Outbox)

    @staticmethod
    def message_sha256(message: dict[str, Any]) -> str:
        canonical = json.dumps(
            message, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def create_idempotent(self, values: dict[str, Any]) -> Outbox | None:
        self._validate_event(values)
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_outbox_record_event_key" not in detail and "duplicate" not in detail:
                raise
            return None

    def validate_image_event(self, event: Outbox) -> ValidateImageMessage:
        values = {
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "aggregate_version": event.aggregate_version,
            "event_key": event.event_key,
            "event_type": event.event_type,
            "destination_key": event.destination_key,
            "trace_id": event.trace_id,
            "message_version": event.message_version,
            "message_json": event.message_json,
            "message_sha256": event.message_sha256,
        }
        return self._validate_event(values)

    async def get_by_id(self, event_id: str) -> Outbox | None:
        return await self.get_data(data_id=event_id, v_return_none=True)

    async def get_by_event_key(self, event_key: str) -> Outbox | None:
        return await self.get_data(event_key=event_key, v_return_none=True)

    async def list_publishable_global(
        self, *, now: datetime, limit: int = 100
    ) -> list[Outbox]:
        if limit <= 0:
            raise ValueError("outbox_publish_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                or_(
                    and_(
                        self.model.publish_status == "pending",
                        self.model.next_retry_at.is_(None),
                    ),
                    and_(
                        self.model.publish_status == "retry_wait",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def claim_publish(
        self,
        *,
        event_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> Outbox | None:
        if not owner_id.strip() or lease_expires_at <= now:
            raise ValueError("outbox_publish_lease_invalid")
        row = await self.get_by_id(event_id)
        if row is None:
            return None
        changed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status.in_(["pending", "retry_wait"]),
                self.model.publish_attempt_count == row.publish_attempt_count,
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            data={
                "publish_status": "publishing",
                "relay_owner_id": owner_id,
                "relay_lease_expires_at": lease_expires_at,
                "publish_attempt_count": row.publish_attempt_count + 1,
                "next_retry_at": None,
                "error_code": None,
                "error_message": None,
            },
        )
        return await self.get_by_id(event_id) if changed else None

    async def mark_published(
        self,
        *,
        event_id: str,
        owner_id: str,
        broker_message_id: str,
        published_at: datetime,
    ) -> bool:
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > published_at,
            ],
            data={
                "publish_status": "published",
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "broker_message_id": broker_message_id,
                "published_at": published_at,
            },
        )

    async def mark_retry(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        next_retry_at: datetime,
        error_code: str,
        error_message: str,
    ) -> bool:
        return await self._mark_failure(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            publish_status="retry_wait",
            next_retry_at=next_retry_at,
            error_code=error_code,
            error_message=error_message,
        )

    async def mark_dead_letter(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        error_code: str,
        error_message: str,
    ) -> bool:
        return await self._mark_failure(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            publish_status="dead_letter",
            next_retry_at=None,
            error_code=error_code,
            error_message=error_message,
        )

    async def reconcile_expired_publish_leases(self, *, now: datetime) -> int:
        changed = 0
        rows = await self.get_datas(
            limit=100,
            v_where=[
                self.model.publish_status == "publishing",
                self.model.relay_lease_expires_at <= now,
            ],
            v_return_objs=True,
        )
        for row in rows:
            recovered = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.publish_status == "publishing",
                    self.model.relay_owner_id == row.relay_owner_id,
                    self.model.relay_lease_expires_at == row.relay_lease_expires_at,
                ],
                data={
                    "publish_status": "retry_wait",
                    "relay_owner_id": None,
                    "relay_lease_expires_at": None,
                    "next_retry_at": now,
                    "error_code": "relay_lease_expired",
                    "error_message": "relay lease expired before confirmation",
                },
            )
            changed += int(recovered)
        return changed

    async def _mark_failure(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        publish_status: str,
        next_retry_at: datetime | None,
        error_code: str,
        error_message: str,
    ) -> bool:
        if not error_code.strip() or len(error_code) > 80:
            raise ValueError("outbox_error_code_invalid")
        safe_message = error_message.strip()[:500]
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > failed_at,
            ],
            data={
                "publish_status": publish_status,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "next_retry_at": next_retry_at,
                "error_code": error_code,
                "error_message": safe_message,
            },
        )

    def _validate_event(self, values: dict[str, Any]) -> ValidateImageMessage:
        if values.get("aggregate_type") != "image" or values.get("event_type") != "validate_image":
            raise ValueError("outbox_image_event_invalid")
        if values.get("destination_key") != self.IMAGE_DESTINATION_KEY:
            raise ValueError("outbox_destination_invalid")
        if values.get("message_version") != self.IMAGE_MESSAGE_VERSION:
            raise ValueError("outbox_message_version_invalid")
        message = ValidateImageMessage.model_validate(values.get("message_json"))
        if message.image_id != values.get("aggregate_id"):
            raise ValueError("outbox_aggregate_identity_mismatch")
        if message.expected_state_version != values.get("aggregate_version"):
            raise ValueError("outbox_aggregate_version_mismatch")
        expected_event_key = (
            f"image:{message.image_id}:validate:{message.expected_state_version}"
        )
        if values.get("event_key") != expected_event_key:
            raise ValueError("outbox_event_key_mismatch")
        if message.trace_id != values.get("trace_id"):
            raise ValueError("outbox_trace_mismatch")
        if self.message_sha256(message.model_dump()) != values.get("message_sha256"):
            raise ValueError("outbox_message_sha256_mismatch")
        return message


__all__ = ["OutboxDal"]
