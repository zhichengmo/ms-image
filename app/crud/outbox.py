import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.outbox import Outbox
from app.schemas.outbox import ExecuteStageMessage, ValidateImageMessage


class OutboxDal(DalBase):
    IMAGE_MESSAGE_VERSION = "image-validation.v1"
    IMAGE_DESTINATION_KEY = "imaging.image.validate"
    STAGE_MESSAGE_VERSION = "stage-execution.v1"
    STAGE_DESTINATION_KEY = "imaging.stage.execute"

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

    def validate_stage_event(self, event: Outbox) -> ExecuteStageMessage:
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

    def validate_publish_event(self, event: Outbox) -> dict[str, Any]:
        if event.aggregate_type == "image" and event.event_type == "validate_image":
            return self.validate_image_event(event).model_dump()
        if event.aggregate_type == "stage" and event.event_type == "execute_stage":
            return self.validate_stage_event(event).model_dump()
        raise ValueError("outbox_publish_event_not_registered")

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
        normalized_owner_id = owner_id.strip()
        if not normalized_owner_id or lease_expires_at <= now:
            raise ValueError("outbox_publish_lease_invalid")
        row = await self.get_by_id(event_id)
        if row is None:
            return None
        changed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
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
                self.model.publish_attempt_count == row.publish_attempt_count,
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            data={
                "publish_status": "publishing",
                "relay_owner_id": normalized_owner_id,
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
        normalized_owner_id = owner_id.strip()
        normalized_message_id = broker_message_id.strip()
        if not normalized_owner_id or not normalized_message_id:
            raise ValueError("outbox_publish_confirmation_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == normalized_owner_id,
                self.model.relay_lease_expires_at > published_at,
            ],
            data={
                "publish_status": "published",
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "broker_message_id": normalized_message_id[:128],
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

    async def reconcile_expired_publish_leases(
        self, *, now: datetime, max_attempts: int, limit: int = 100
    ) -> dict[str, int]:
        if max_attempts <= 0 or limit <= 0:
            raise ValueError("outbox_reconcile_contract_invalid")
        changed = {"retry_wait": 0, "dead_lettered": 0}
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.publish_status == "publishing",
                self.model.relay_lease_expires_at <= now,
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )
        for row in rows:
            exhausted = row.publish_attempt_count >= max_attempts
            recovered = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.publish_status == "publishing",
                    self.model.relay_owner_id == row.relay_owner_id,
                    self.model.relay_lease_expires_at == row.relay_lease_expires_at,
                ],
                data={
                    "publish_status": "dead_letter" if exhausted else "retry_wait",
                    "relay_owner_id": None,
                    "relay_lease_expires_at": None,
                    "next_retry_at": None if exhausted else now,
                    "error_code": "relay_lease_expired",
                    "error_message": "relay lease expired before confirmation",
                },
            )
            key = "dead_lettered" if exhausted else "retry_wait"
            changed[key] += int(recovered)
        return changed

    async def operational_snapshot(self, *, now: datetime) -> dict[str, Any]:
        counts = {
            status: await self.get_count(publish_status=status)
            for status in (
                "pending",
                "publishing",
                "published",
                "retry_wait",
                "dead_letter",
                "cancelled",
            )
        }
        expired_relay_leases = await self.get_count(
            v_where=[
                self.model.publish_status == "publishing",
                self.model.relay_lease_expires_at.is_not(None),
                self.model.relay_lease_expires_at <= now,
            ]
        )
        oldest = await self.get_datas(
            page=1,
            limit=1,
            v_where=[
                self.model.publish_status.in_(("pending", "publishing", "retry_wait"))
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )
        return {
            "counts": counts,
            "expired_relay_leases": expired_relay_leases,
            "oldest_active_created_at": oldest[0].created_at if oldest else None,
        }

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
        normalized_owner_id = owner_id.strip()
        normalized_error_code = error_code.strip()
        if not normalized_owner_id:
            raise ValueError("outbox_publish_owner_invalid")
        if not normalized_error_code or len(normalized_error_code) > 80:
            raise ValueError("outbox_error_code_invalid")
        if publish_status == "retry_wait":
            if next_retry_at is None or next_retry_at <= failed_at:
                raise ValueError("outbox_retry_time_invalid")
        elif publish_status == "dead_letter":
            if next_retry_at is not None:
                raise ValueError("outbox_dead_letter_retry_invalid")
        else:
            raise ValueError("outbox_failure_status_invalid")
        safe_message = error_message.strip()[:500]
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == normalized_owner_id,
                self.model.relay_lease_expires_at > failed_at,
            ],
            data={
                "publish_status": publish_status,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "next_retry_at": next_retry_at,
                "error_code": normalized_error_code,
                "error_message": safe_message,
            },
        )

    def _validate_event(self, values: dict[str, Any]) -> ValidateImageMessage | ExecuteStageMessage:
        aggregate_type = values.get("aggregate_type")
        event_type = values.get("event_type")
        if aggregate_type == "image" and event_type == "validate_image":
            if values.get("destination_key") != self.IMAGE_DESTINATION_KEY:
                raise ValueError("outbox_destination_invalid")
            if values.get("message_version") != self.IMAGE_MESSAGE_VERSION:
                raise ValueError("outbox_message_version_invalid")
            message = ValidateImageMessage.model_validate(values.get("message_json"))
            if message.image_id != values.get("aggregate_id"):
                raise ValueError("outbox_aggregate_identity_mismatch")
            expected_event_key = f"image:{message.image_id}:validate:{message.expected_state_version}"
        elif aggregate_type == "stage" and event_type == "execute_stage":
            if values.get("destination_key") != self.STAGE_DESTINATION_KEY:
                raise ValueError("outbox_destination_invalid")
            if values.get("message_version") != self.STAGE_MESSAGE_VERSION:
                raise ValueError("outbox_message_version_invalid")
            message = ExecuteStageMessage.model_validate(values.get("message_json"))
            if message.stage_checkpoint_id != values.get("aggregate_id"):
                raise ValueError("outbox_aggregate_identity_mismatch")
            expected_event_key = f"stage:{message.stage_checkpoint_id}:execute:{message.expected_state_version}"
        else:
            raise ValueError("outbox_event_not_registered")
        if message.expected_state_version != values.get("aggregate_version"):
            raise ValueError("outbox_aggregate_version_mismatch")
        if values.get("event_key") != expected_event_key:
            raise ValueError("outbox_event_key_mismatch")
        if message.trace_id != values.get("trace_id"):
            raise ValueError("outbox_trace_mismatch")
        if self.message_sha256(message.model_dump()) != values.get("message_sha256"):
            raise ValueError("outbox_message_sha256_mismatch")
        return message


__all__ = ["OutboxDal"]
