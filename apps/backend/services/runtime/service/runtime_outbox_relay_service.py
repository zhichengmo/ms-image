"""Runtime outbox persistence boundary for the shared relay workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.outbox import OutboxDal


class RuntimeOutboxRelayService:
    """Expose Runtime outbox relay operations without leaking its DAL to Workers."""

    IMAGE_DESTINATION_KEY = OutboxDal.IMAGE_DESTINATION_KEY
    STAGE_DESTINATION_KEY = OutboxDal.STAGE_DESTINATION_KEY

    def __init__(self, db: AsyncSession):
        self.outbox_dal = OutboxDal(db)

    async def claim_publish(
        self,
        *,
        event_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> Any:
        return await self.outbox_dal.claim_publish(
            event_id=event_id,
            owner_id=owner_id,
            now=now,
            lease_expires_at=lease_expires_at,
        )

    def validate_publish_event(self, event: Any) -> dict[str, Any]:
        return self.outbox_dal.validate_publish_event(event)

    async def mark_dead_letter(
        self,
        *,
        event_id: str,
        owner_id: str,
        failed_at: datetime,
        error_code: str,
        error_message: str,
    ) -> bool:
        return await self.outbox_dal.mark_dead_letter(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            error_code=error_code,
            error_message=error_message,
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
        return await self.outbox_dal.mark_retry(
            event_id=event_id,
            owner_id=owner_id,
            failed_at=failed_at,
            next_retry_at=next_retry_at,
            error_code=error_code,
            error_message=error_message,
        )

    async def list_publishable_global(
        self, *, now: datetime, limit: int = 100
    ) -> list[Any]:
        return await self.outbox_dal.list_publishable_global(now=now, limit=limit)

    async def mark_published(
        self,
        *,
        event_id: str,
        owner_id: str,
        broker_message_id: str,
        published_at: datetime,
    ) -> bool:
        return await self.outbox_dal.mark_published(
            event_id=event_id,
            owner_id=owner_id,
            broker_message_id=broker_message_id,
            published_at=published_at,
        )

    async def reconcile_expired_publish_leases(
        self, *, now: datetime, max_attempts: int, limit: int = 100
    ) -> dict[str, int]:
        return await self.outbox_dal.reconcile_expired_publish_leases(
            now=now,
            max_attempts=max_attempts,
            limit=limit,
        )


__all__ = ["RuntimeOutboxRelayService"]
