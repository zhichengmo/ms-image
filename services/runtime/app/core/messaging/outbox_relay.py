"""Reusable transactional-outbox relay with lease/retry/reconcile semantics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import inspect
import socket
from typing import Any, Callable
from uuid import uuid4

from .config import BrokerRuntimeConfig
from .lifecycle import wait_for_shutdown


def safe_error(exc: BaseException) -> str:
    candidate = getattr(exc, "error_class", None)
    stable = {
        "provider_auth", "endpoint_timeout", "network_unreachable", "tls_failure",
        "model_invalid", "model_mismatch", "schema_invalid", "rate_limited",
        "provider_unavailable", "provider_receipt_missing", "provider_receipt_unsupported",
        "provider_output_contract",
        "provider_configuration_incomplete", "provider_disabled", "provider_not_qualified",
    }
    if isinstance(candidate, str) and candidate in stable:
        return candidate
    name = type(exc).__name__.casefold()
    if "timeout" in name:
        return "endpoint_timeout"
    if "connection" in name or "connect" in name:
        return "network_unreachable"
    return "broker_publish_failed"


@dataclass(frozen=True)
class OutboxPublishEnvelope:
    event_id: str
    destination_key: str
    message_version: str
    trace_id: str
    message: dict[str, Any]


class OutboxRelay:
    """Relay target outbox events without owning consumer execution state."""

    def __init__(
        self,
        *,
        session_factory: Any,
        publish: Callable[[OutboxPublishEnvelope], Any],
        runtime: BrokerRuntimeConfig,
        owner_prefix: str,
        dal_factory: Callable[[Any], Any],
    ):
        if runtime.relay_lease_seconds <= 0 or runtime.max_attempts <= 0:
            raise ValueError("outbox_relay_runtime_invalid")
        self.session_factory = session_factory
        self.publish = publish
        self.runtime = runtime
        self.dal_factory = dal_factory
        self.owner_id = f"{owner_prefix}:{socket.gethostname()}:{uuid4().hex[:12]}"[:128]

    async def _claim_one(self, event_id: str) -> dict[str, Any] | None:
        now = datetime.utcnow()
        async with self.session_factory() as db:
            async with db.begin():
                dal = self.dal_factory(db)
                claimed = await dal.claim_publish(
                    event_id=event_id,
                    owner_id=self.owner_id,
                    now=now,
                    lease_expires_at=now
                    + timedelta(seconds=self.runtime.relay_lease_seconds),
                )
                if claimed is None:
                    return None
                try:
                    message = dal.validate_publish_event(claimed)
                except ValueError:
                    marked = await dal.mark_dead_letter(
                        event_id=claimed.id,
                        owner_id=self.owner_id,
                        failed_at=datetime.utcnow(),
                        error_code="outbox_message_contract_invalid",
                        error_message="outbox message contract invalid",
                    )
                    if not marked:
                        raise RuntimeError("outbox_invalid_message_state_conflict")
                    return {"invalid": True, "event_id": claimed.id}
                return {
                    "invalid": False,
                    "attempt_count": claimed.publish_attempt_count,
                    "envelope": OutboxPublishEnvelope(
                        event_id=claimed.id,
                        destination_key=claimed.destination_key,
                        message_version=claimed.message_version,
                        trace_id=claimed.trace_id,
                        message=message,
                    ),
                }

    async def _mark_publish_failure(
        self, *, event_id: str, attempt_count: int, exc: BaseException
    ) -> str:
        failed_at = datetime.utcnow()
        error_code = safe_error(exc)
        async with self.session_factory() as db:
            async with db.begin():
                dal = self.dal_factory(db)
                if attempt_count >= self.runtime.max_attempts:
                    marked = await dal.mark_dead_letter(
                        event_id=event_id,
                        owner_id=self.owner_id,
                        failed_at=failed_at,
                        error_code=error_code,
                        error_message=error_code,
                    )
                    outcome = "dead_lettered"
                else:
                    delay_seconds = min(300, 2 ** max(0, attempt_count - 1))
                    marked = await dal.mark_retry(
                        event_id=event_id,
                        owner_id=self.owner_id,
                        failed_at=failed_at,
                        next_retry_at=failed_at + timedelta(seconds=delay_seconds),
                        error_code=error_code,
                        error_message=error_code,
                    )
                    outcome = "retry_wait"
                return outcome if marked else "conflicted"

    async def relay_once(self, *, limit: int = 100) -> dict[str, int]:
        result = {
            "disabled": 0,
            "claimed": 0,
            "published": 0,
            "retry_wait": 0,
            "dead_lettered": 0,
            "conflicted": 0,
        }
        if not self.runtime.enabled:
            result["disabled"] = 1
            return result
        async with self.session_factory() as db:
            async with db.begin():
                rows = await self.dal_factory(db).list_publishable_global(
                    now=datetime.utcnow(), limit=limit
                )
                candidates = [row.id for row in rows]
        for event_id in candidates:
            claimed = await self._claim_one(event_id)
            if claimed is None:
                continue
            result["claimed"] += 1
            if claimed["invalid"]:
                result["dead_lettered"] += 1
                continue
            envelope: OutboxPublishEnvelope = claimed["envelope"]
            broker_accepted = False
            try:
                broker_message_id = self.publish(envelope)
                if inspect.isawaitable(broker_message_id):
                    broker_message_id = await broker_message_id
                broker_accepted = True
                confirmed_at = datetime.utcnow()
                async with self.session_factory() as db:
                    async with db.begin():
                        marked = await self.dal_factory(db).mark_published(
                            event_id=envelope.event_id,
                            owner_id=self.owner_id,
                            broker_message_id=str(broker_message_id or envelope.event_id),
                            published_at=confirmed_at,
                        )
                        if not marked:
                            raise RuntimeError("outbox_publish_confirmation_conflict")
                result["published"] += 1
            except Exception as exc:
                if broker_accepted:
                    result["conflicted"] += 1
                    continue
                outcome = await self._mark_publish_failure(
                    event_id=envelope.event_id,
                    attempt_count=claimed["attempt_count"],
                    exc=exc,
                )
                result[outcome] += 1
        return result

    async def reconcile_once(self, *, limit: int = 100) -> dict[str, int]:
        if not self.runtime.enabled:
            return {"disabled": 1, "retry_wait": 0, "dead_lettered": 0}
        async with self.session_factory() as db:
            async with db.begin():
                result = await self.dal_factory(db).reconcile_expired_publish_leases(
                    now=datetime.utcnow(),
                    max_attempts=self.runtime.max_attempts,
                    limit=limit,
                )
                return {"disabled": 0, **result}

    async def run_forever(self, *, stop_event: asyncio.Event | None = None) -> None:
        if not self.runtime.enabled:
            raise RuntimeError("broker_disabled")
        shutdown = stop_event or asyncio.Event()
        while not shutdown.is_set():
            await self.reconcile_once()
            await self.relay_once()
            await wait_for_shutdown(shutdown, self.runtime.relay_poll_seconds)


class TransactionalOutboxRelay:
    """Domain-neutral relay; the domain supplies its DAL and publisher."""

    def __init__(
        self,
        *,
        session_factory: Any,
        dal_factory: Callable[[Any], Any],
        publish: Callable[[str, str, dict[str, Any]], Any],
        runtime: BrokerRuntimeConfig,
        owner_prefix: str,
        reconcile_extra: Callable[[Any, datetime, int], Any] | None = None,
    ):
        self.session_factory = session_factory
        self.dal_factory = dal_factory
        self.publish = publish
        self.runtime = runtime
        self.reconcile_extra = reconcile_extra
        self.owner_id = f"{owner_prefix}:{socket.gethostname()}:{uuid4().hex[:12]}"[:128]

    async def _claim_one(self, *, event_id: str, tenant_id: str) -> dict[str, Any] | None:
        now = datetime.utcnow()
        async with self.session_factory() as db:
            async with db.begin():
                claimed = await self.dal_factory(db).claim_publish(
                    event_id=event_id,
                    tenant_id=tenant_id,
                    owner_id=self.owner_id,
                    now=now,
                    lease_expires_at=now + timedelta(seconds=self.runtime.relay_lease_seconds),
                )
                if claimed is None:
                    return None
                return {
                    "event_id": claimed.event_id,
                    "tenant_id": claimed.tenant_id,
                    "message": dict(claimed.message_json),
                    "attempt_count": claimed.attempt_count,
                }

    async def _publish_failed(self, claimed: dict[str, Any], exc: BaseException) -> None:
        failed_at = datetime.utcnow()
        async with self.session_factory() as db:
            async with db.begin():
                dal = self.dal_factory(db)
                if claimed["attempt_count"] >= self.runtime.max_attempts:
                    await dal.mark_dead_letter(
                        event_id=claimed["event_id"], tenant_id=claimed["tenant_id"],
                        owner_id=self.owner_id, failed_at=failed_at,
                        error_class=safe_error(exc),
                    )
                else:
                    await dal.mark_retry(
                        event_id=claimed["event_id"], tenant_id=claimed["tenant_id"],
                        owner_id=self.owner_id, failed_at=failed_at,
                        next_retry_at=failed_at + timedelta(seconds=2 ** max(0, claimed["attempt_count"] - 1)),
                        error_class=safe_error(exc),
                    )

    async def relay_once(self, *, limit: int = 100) -> dict[str, int]:
        if not self.runtime.enabled:
            return {"disabled": 1, "claimed": 0, "published": 0, "failed": 0}
        async with self.session_factory() as db:
            async with db.begin():
                rows = await self.dal_factory(db).list_publishable_global(
                    now=datetime.utcnow(), limit=limit
                )
                # Snapshot identity values before the transaction/session
                # closes; AsyncSession expires ORM attributes on commit.
                candidates = [(row.event_id, row.tenant_id) for row in rows]
        result = {"disabled": 0, "claimed": 0, "published": 0, "failed": 0}
        for event_id, tenant_id in candidates:
            claimed = await self._claim_one(event_id=event_id, tenant_id=tenant_id)
            if claimed is None:
                continue
            result["claimed"] += 1
            broker_accepted = False
            try:
                published = self.publish(
                    claimed["event_id"], claimed["tenant_id"], claimed["message"]
                )
                if inspect.isawaitable(published):
                    await published
                broker_accepted = True
                confirmed_at = datetime.utcnow()
                async with self.session_factory() as db:
                    async with db.begin():
                        marked = await self.dal_factory(db).mark_broker_published(
                            event_id=claimed["event_id"],
                            tenant_id=claimed["tenant_id"],
                            owner_id=self.owner_id,
                            published_at=confirmed_at,
                        )
                        if not marked:
                            raise RuntimeError("outbox_broker_publish_state_conflict")
                result["published"] += 1
            except Exception as exc:
                result["failed"] += 1
                if not broker_accepted:
                    await self._publish_failed(claimed, exc)
                # The broker accepted the message but the DB confirmation
                # lease was lost.  Do not run relay failure mutation against
                # an expired lease; reconciliation will recover the row and
                # consumer idempotency will absorb any duplicate delivery.
        return result

    async def consumer_retry_once(self, *, limit: int = 100) -> dict[str, int]:
        """Republish due consumer retries without creating a second Outbox row.

        The first delivery is already broker-confirmed.  A retryable worker
        failure therefore leaves the immutable event in ``published`` and
        schedules this dispatcher to send the exact same message again.  The
        consumer lease columns provide a short CAS-protected dispatch lease;
        the row becomes ``pending`` only after the publisher returns.
        """
        if not self.runtime.enabled:
            return {"disabled": 1, "claimed": 0, "published": 0, "failed": 0}
        async with self.session_factory() as db:
            async with db.begin():
                rows = await self.dal_factory(db).list_consumer_retryable_global(
                    now=datetime.utcnow(), limit=limit
                )
                candidates = [(row.event_id, row.tenant_id) for row in rows]
        result = {"disabled": 0, "claimed": 0, "published": 0, "failed": 0}
        dispatch_owner = f"{self.owner_id}:consumer-retry"[:128]
        for event_id, tenant_id in candidates:
            now = datetime.utcnow()
            async with self.session_factory() as db:
                async with db.begin():
                    claimed = await self.dal_factory(db).claim_consumer_retry_dispatch(
                        event_id=event_id,
                        tenant_id=tenant_id,
                        owner_id=dispatch_owner,
                        now=now,
                        lease_expires_at=now + timedelta(
                            seconds=self.runtime.relay_lease_seconds
                        ),
                    )
                    if claimed is None:
                        continue
                    payload = dict(claimed.message_json)
                    attempt_count = claimed.consumer_attempt_count
            result["claimed"] += 1
            try:
                published = self.publish(event_id, tenant_id, payload)
                if inspect.isawaitable(published):
                    await published
                dispatched_at = datetime.utcnow()
                async with self.session_factory() as db:
                    async with db.begin():
                        marked = await self.dal_factory(db).mark_consumer_retry_dispatched(
                            event_id=event_id,
                            tenant_id=tenant_id,
                            owner_id=dispatch_owner,
                            dispatched_at=dispatched_at,
                        )
                        if not marked:
                            raise RuntimeError("outbox_consumer_retry_state_conflict")
                result["published"] += 1
            except Exception as exc:
                result["failed"] += 1
                failed_at = datetime.utcnow()
                async with self.session_factory() as db:
                    async with db.begin():
                        marked = await self.dal_factory(db).mark_consumer_retry_dispatch_failed(
                            event_id=event_id,
                            tenant_id=tenant_id,
                            owner_id=dispatch_owner,
                            failed_at=failed_at,
                            next_retry_at=failed_at + timedelta(
                                seconds=2 ** max(0, attempt_count - 1)
                            ),
                            error_class=safe_error(exc),
                        )
                        if not marked:
                            raise RuntimeError("outbox_consumer_retry_state_conflict")
        return result

    async def reconcile_once(self, *, limit: int = 100) -> dict[str, int]:
        if not self.runtime.enabled:
            return {"disabled": 1, "recovered": 0}
        async with self.session_factory() as db:
            async with db.begin():
                result = await self.dal_factory(db).recover_expired_global(
                    now=datetime.utcnow(), max_attempts=self.runtime.max_attempts, limit=limit
                )
                if self.reconcile_extra is not None:
                    extra = self.reconcile_extra(db, datetime.utcnow(), limit)
                    if inspect.isawaitable(extra):
                        extra = await extra
                    if isinstance(extra, dict):
                        for key, value in extra.items():
                            result[f"checkpoint_{key}"] = int(value)
                return result

    async def run_forever(self, *, stop_event: asyncio.Event | None = None) -> None:
        if not self.runtime.enabled:
            raise RuntimeError("broker_disabled")
        shutdown = stop_event or asyncio.Event()
        while not shutdown.is_set():
            await self.reconcile_once()
            await self.relay_once()
            await self.consumer_retry_once()
            await wait_for_shutdown(shutdown, self.runtime.relay_poll_seconds)


__all__ = [
    "OutboxPublishEnvelope",
    "OutboxRelay",
    "TransactionalOutboxRelay",
    "safe_error",
]
