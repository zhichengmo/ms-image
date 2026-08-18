import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.outbox import XRayOutbox


class XRayOutboxDal(DalBase):
    MESSAGE_FIELDS = frozenset(
        {
            "run_id",
            "task_id",
            "stage_key",
            "release_fingerprint",
            "expected_version",
            "trace_namespace",
        }
    )
    EVENT_TYPES = frozenset({"execute", "reconcile", "review", "delivery"})
    PUBLISH_STATUSES = frozenset({"pending", "publishing", "published", "retry", "dead_letter"})
    CONSUMER_STATUSES = frozenset({"pending", "running", "completed", "retry_wait", "dead_letter", "cancelled"})
    MESSAGE_WHITELIST_VERSION = "xray-message.v1"

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayOutbox)

    async def create_event(self, values: dict) -> XRayOutbox:
        self._validate_event(values)
        return await self.create_data(values, v_return_obj=True)

    async def get_by_event_id(
        self,
        *,
        event_id: str,
        tenant_id: str,
    ) -> XRayOutbox | None:
        return await self.get_data(
            data_id=event_id,
            v_where=[
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
            ],
            v_return_none=True,
        )

    async def get_by_task_id(
        self,
        *,
        task_id: str,
        tenant_id: str,
    ) -> XRayOutbox | None:
        """Resolve one relay-safe task without trusting a caller tenant."""
        return await self.get_data(
            v_where=[
                self.model.task_id == task_id,
                self.model.tenant_id == tenant_id,
            ],
            v_order="desc",
            v_order_field="created_at",
            v_return_none=True,
        )

    async def list_for_tenant_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        limit: int = 100,
    ) -> list[XRayOutbox]:
        """Return publish state without exposing the message payload."""
        if limit <= 0:
            raise ValueError("outbox_list_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.run_id == run_id,
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def cancel_pending_for_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        cancelled_at: datetime,
    ) -> int:
        """Prevent queued events from running after cancel.

        Broker publication and consumer execution are independent.  Pending
        relay rows are dead-lettered, while already published but unclaimed
        consumer rows are cancelled.  A currently running consumer is left
        leased so it can observe the Run cancellation and record a late trace;
        it must never be force-marked completed here.
        """
        cancelled = 0
        while True:
            rows = await self.get_datas(
                page=1,
                limit=100,
                v_where=[
                    self.model.tenant_id == tenant_id,
                    self.model.run_id == run_id,
                    self.model.stage_key != "cancel",
                    or_(
                        self.model.publish_status.in_(["pending", "retry"]),
                        and_(
                            self.model.publish_status == "publishing",
                            or_(
                                self.model.relay_owner_id.is_(None),
                                self.model.relay_lease_expires_at <= cancelled_at,
                            ),
                        ),
                        and_(
                            self.model.publish_status == "published",
                            self.model.consumer_status.in_(["pending", "retry_wait"]),
                        ),
                    ),
                ],
                v_order="asc",
                v_order_field="created_at",
                v_return_objs=True,
            )
            if not rows:
                break
            batch_changed = 0
            for row in rows:
                changed = await self.conditional_update(
                    v_where=[
                        self.model.id == row.id,
                        self.model.event_id == row.event_id,
                        self.model.tenant_id == tenant_id,
                        self.model.run_id == run_id,
                        self.model.stage_key != "cancel",
                        or_(
                            self.model.publish_status.in_(["pending", "retry"]),
                            and_(
                                self.model.publish_status == "publishing",
                                or_(
                                    self.model.relay_owner_id.is_(None),
                                    self.model.relay_lease_expires_at <= cancelled_at,
                                ),
                            ),
                            and_(
                                self.model.publish_status == "published",
                                self.model.consumer_status.in_(["pending", "retry_wait"]),
                            ),
                        ),
                    ],
                    data={
                        "publish_status": "dead_letter" if row.publish_status != "published" else row.publish_status,
                        "consumer_status": "cancelled" if row.publish_status == "published" else row.consumer_status,
                        "next_retry_at": None,
                        "consumer_next_retry_at": None,
                        "consumer_finished_at": cancelled_at if row.publish_status == "published" else None,
                        "consumer_last_error": "run_cancelled" if row.publish_status == "published" else None,
                        "last_error": "run_cancelled",
                        "relay_owner_id": None,
                        "relay_lease_expires_at": None,
                        # A published row retains its broker confirmation
                        # timestamp even when its consumer is cancelled.
                        "published_at": (
                            None
                            if row.publish_status != "published"
                            else row.published_at
                        ),
                    },
                )
                batch_changed += int(changed)
            cancelled += batch_changed
            if batch_changed == 0:
                break
        return cancelled

    async def list_publishable(
        self,
        *,
        tenant_id: str,
        now: datetime,
        limit: int = 100,
    ) -> list[XRayOutbox]:
        """Return tenant-scoped rows whose retry time and relay lease allow claim."""
        if limit <= 0:
            raise ValueError("outbox_publish_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                or_(
                    and_(
                        self.model.publish_status == "pending",
                        self.model.next_retry_at.is_(None),
                    ),
                    and_(
                        self.model.publish_status == "retry",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def list_publishable_global(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[XRayOutbox]:
        """List relay candidates across tenants for the trusted relay process.

        The relay is an internal process, not an HTTP caller.  Tenant scope is
        still carried in the immutable Outbox row and is passed unchanged to
        the consumer; no tenant value is accepted from a broker message.
        """
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
                        self.model.publish_status == "retry",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def list_consumer_retryable_global(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[XRayOutbox]:
        """List published events whose consumer retry is due.

        A consumer retry is a second delivery of the same immutable message,
        not a new Outbox fact. Keeping the row in ``published`` preserves the
        broker-publish audit while this dispatcher re-delivers the payload.
        """
        if limit <= 0:
            raise ValueError("outbox_consumer_retry_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.publish_status == "published",
                self.model.consumer_status == "retry_wait",
                self.model.consumer_next_retry_at.is_not(None),
                self.model.consumer_next_retry_at <= now,
                or_(
                    self.model.consumer_owner_id.is_(None),
                    self.model.consumer_lease_expires_at <= now,
                ),
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def claim_consumer_retry_dispatch(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> XRayOutbox | None:
        """Lease one due retry while the relay republishes its same message.

        The existing consumer lease columns are reused for this short
        dispatch lease so the current schema stays compatible. The status is
        ``running`` only during the dispatch window and is returned to
        ``pending`` after publisher confirmation.
        """
        if not owner_id.strip() or lease_expires_at <= now:
            raise ValueError("outbox_consumer_retry_lease_invalid")
        claimed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "retry_wait",
                self.model.consumer_next_retry_at.is_not(None),
                self.model.consumer_next_retry_at <= now,
                or_(
                    self.model.consumer_owner_id.is_(None),
                    self.model.consumer_lease_expires_at <= now,
                ),
            ],
            data={
                "consumer_status": "running",
                "consumer_owner_id": owner_id,
                "consumer_lease_expires_at": lease_expires_at,
                "consumer_started_at": now,
                "consumer_last_error": None,
            },
        )
        if not claimed:
            return None
        return await self.get_by_event_id(event_id=event_id, tenant_id=tenant_id)

    async def mark_consumer_retry_dispatched(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        dispatched_at: datetime,
    ) -> bool:
        """Make a confirmed retry delivery claimable by the worker."""
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > dispatched_at,
            ],
            data={
                "consumer_status": "pending",
                "consumer_owner_id": None,
                "consumer_lease_expires_at": None,
                "consumer_started_at": None,
                "consumer_next_retry_at": None,
                "consumer_last_error": None,
            },
        )

    async def mark_consumer_retry_dispatch_failed(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        failed_at: datetime,
        next_retry_at: datetime,
        error_class: str,
    ) -> bool:
        """Return a failed retry dispatch to the due-time state."""
        self._validate_error_class(error_class)
        if next_retry_at <= failed_at:
            raise ValueError("outbox_consumer_retry_time_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > failed_at,
            ],
            data={
                "consumer_status": "retry_wait",
                "consumer_owner_id": None,
                "consumer_lease_expires_at": None,
                "consumer_started_at": None,
                "consumer_next_retry_at": next_retry_at,
                "consumer_last_error": error_class,
            },
        )

    async def claim_publish(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> XRayOutbox | None:
        if not owner_id.strip() or lease_expires_at <= now:
            raise ValueError("outbox_relay_lease_invalid")
        claimed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                or_(
                    and_(
                        self.model.publish_status == "pending",
                        self.model.next_retry_at.is_(None),
                    ),
                    and_(
                        self.model.publish_status == "retry",
                        self.model.next_retry_at.is_not(None),
                        self.model.next_retry_at <= now,
                    ),
                ),
                or_(
                    self.model.relay_owner_id.is_(None),
                    self.model.relay_lease_expires_at <= now,
                ),
            ],
            data={
                "publish_status": "publishing",
                "relay_owner_id": owner_id,
                "relay_lease_expires_at": lease_expires_at,
                "attempt_count": self.model.attempt_count + 1,
                "next_retry_at": None,
                "last_error": None,
            },
        )
        if not claimed:
            return None
        return await self.get_by_event_id(event_id=event_id, tenant_id=tenant_id)

    async def claim_for_consumer(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> XRayOutbox | None:
        """Claim a broker-confirmed event for one idempotent consumer."""
        if not owner_id.strip() or lease_expires_at <= now:
            raise ValueError("outbox_consumer_lease_invalid")
        claimed = await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                or_(
                    self.model.consumer_status == "pending",
                    and_(
                        self.model.consumer_status == "retry_wait",
                        self.model.consumer_next_retry_at.is_not(None),
                        self.model.consumer_next_retry_at <= now,
                    ),
                    and_(
                        self.model.consumer_status == "running",
                        self.model.consumer_lease_expires_at <= now,
                    ),
                ),
                or_(
                    self.model.consumer_owner_id.is_(None),
                    self.model.consumer_lease_expires_at <= now,
                ),
            ],
            data={
                "consumer_status": "running",
                "consumer_owner_id": owner_id,
                "consumer_lease_expires_at": lease_expires_at,
                "consumer_attempt_count": self.model.consumer_attempt_count + 1,
                "consumer_started_at": now,
                "consumer_finished_at": None,
                "consumer_next_retry_at": None,
                "consumer_last_error": None,
            },
        )
        if not claimed:
            return None
        return await self.get_by_event_id(event_id=event_id, tenant_id=tenant_id)

    async def mark_broker_published(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        published_at: datetime,
    ) -> bool:
        """Commit broker confirmation without pretending the stage completed."""
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > published_at,
            ],
            data={
                "publish_status": "published",
                "published_at": published_at,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
                "next_retry_at": None,
                "last_error": None,
            },
        )

    async def mark_manual_broker_published(
        self, *, event_id: str, tenant_id: str, published_at: datetime
    ) -> bool:
        """Allow the admin qualification trigger to bypass RabbitMQ explicitly."""
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status.in_(["pending", "retry"]),
                or_(self.model.next_retry_at.is_(None), self.model.next_retry_at <= published_at),
            ],
            data={
                "publish_status": "published",
                "published_at": published_at,
                "next_retry_at": None,
                "last_error": None,
            },
        )

    async def mark_consumer_completed(
        self, *, event_id: str, tenant_id: str, owner_id: str, finished_at: datetime
    ) -> bool:
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > finished_at,
            ],
            data={
                "consumer_status": "completed",
                "consumer_owner_id": None,
                "consumer_lease_expires_at": None,
                "consumer_finished_at": finished_at,
                "consumer_next_retry_at": None,
                "consumer_last_error": None,
            },
        )

    async def mark_consumer_retry(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        failed_at: datetime,
        next_retry_at: datetime,
        error_class: str,
    ) -> bool:
        self._validate_error_class(error_class)
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > failed_at,
            ],
            data={
                "consumer_status": "retry_wait",
                "consumer_owner_id": None,
                "consumer_lease_expires_at": None,
                "consumer_finished_at": None,
                "consumer_next_retry_at": next_retry_at,
                "consumer_last_error": error_class,
            },
        )

    async def mark_consumer_dead_letter(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        failed_at: datetime,
        error_class: str,
    ) -> bool:
        self._validate_error_class(error_class)
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > failed_at,
            ],
            data={
                "consumer_status": "dead_letter",
                "consumer_owner_id": None,
                "consumer_lease_expires_at": None,
                "consumer_finished_at": failed_at,
                "consumer_next_retry_at": None,
                "consumer_last_error": error_class,
            },
        )

    async def heartbeat_consumer(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        """Extend an active worker lease without changing execution state."""
        if lease_expires_at <= heartbeat_at:
            raise ValueError("outbox_consumer_lease_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "published",
                self.model.consumer_status == "running",
                self.model.consumer_owner_id == owner_id,
                self.model.consumer_lease_expires_at > heartbeat_at,
            ],
            data={"consumer_lease_expires_at": lease_expires_at},
        )

    async def heartbeat_publish(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        if lease_expires_at <= heartbeat_at:
            raise ValueError("outbox_relay_lease_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > heartbeat_at,
            ],
            data={"relay_lease_expires_at": lease_expires_at},
        )

    async def mark_published(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        published_at: datetime,
    ) -> bool:
        # Compatibility alias; this method now means broker confirmation only.
        return await self.mark_broker_published(
            event_id=event_id,
            tenant_id=tenant_id,
            owner_id=owner_id,
            published_at=published_at,
        )

    async def mark_retry(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        failed_at: datetime,
        next_retry_at: datetime,
        error_class: str,
    ) -> bool:
        self._validate_error_class(error_class)
        if next_retry_at <= failed_at:
            raise ValueError("outbox_retry_time_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > failed_at,
            ],
            data={
                "publish_status": "retry",
                "next_retry_at": next_retry_at,
                "last_error": error_class,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
            },
        )

    async def mark_dead_letter(
        self,
        *,
        event_id: str,
        tenant_id: str,
        owner_id: str,
        failed_at: datetime,
        error_class: str,
    ) -> bool:
        self._validate_error_class(error_class)
        return await self.conditional_update(
            v_where=[
                self.model.id == event_id,
                self.model.event_id == event_id,
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id == owner_id,
                self.model.relay_lease_expires_at > failed_at,
            ],
            data={
                "publish_status": "dead_letter",
                "next_retry_at": None,
                "last_error": error_class,
                "relay_owner_id": None,
                "relay_lease_expires_at": None,
            },
        )

    async def recover_expired(
        self,
        *,
        tenant_id: str,
        now: datetime,
        max_attempts: int,
        limit: int = 100,
    ) -> dict[str, int]:
        if max_attempts <= 0 or limit <= 0:
            raise ValueError("outbox_recovery_limits_invalid")
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.publish_status == "publishing",
                self.model.relay_owner_id.is_not(None),
                self.model.relay_lease_expires_at <= now,
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )
        recovered = {"retry": 0, "dead_letter": 0}
        for row in rows:
            next_status = "dead_letter" if row.attempt_count >= max_attempts else "retry"
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.event_id == row.event_id,
                    self.model.tenant_id == tenant_id,
                    self.model.publish_status == "publishing",
                    self.model.relay_owner_id == row.relay_owner_id,
                    self.model.relay_lease_expires_at <= now,
                ],
                data={
                    "publish_status": next_status,
                    "next_retry_at": None if next_status == "dead_letter" else now,
                    "last_error": "relay_lease_expired",
                    "relay_owner_id": None,
                    "relay_lease_expires_at": None,
                },
            )
            if changed:
                recovered[next_status] += 1
        return recovered

    async def recover_expired_global(
        self,
        *,
        now: datetime,
        max_attempts: int,
        limit: int = 100,
    ) -> dict[str, int]:
        """Recover relay/consumer leases without requiring a tenant list."""
        if max_attempts <= 0 or limit <= 0:
            raise ValueError("outbox_recovery_limits_invalid")
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                or_(
                    and_(
                        self.model.publish_status == "publishing",
                        self.model.relay_owner_id.is_not(None),
                        self.model.relay_lease_expires_at <= now,
                    ),
                    and_(
                        self.model.publish_status == "published",
                        self.model.consumer_status == "running",
                        self.model.consumer_owner_id.is_not(None),
                        self.model.consumer_lease_expires_at <= now,
                    ),
                ),
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )
        recovered = {"retry": 0, "dead_letter": 0, "consumer_retry": 0, "consumer_dead_letter": 0}
        for row in rows:
            if row.publish_status == "published" and row.consumer_status == "running":
                next_consumer = "dead_letter" if row.consumer_attempt_count >= max_attempts else "retry_wait"
                changed = await self.conditional_update(
                    v_where=[
                        self.model.id == row.id,
                        self.model.event_id == row.event_id,
                        self.model.tenant_id == row.tenant_id,
                        self.model.publish_status == "published",
                        self.model.consumer_status == "running",
                        self.model.consumer_owner_id == row.consumer_owner_id,
                        self.model.consumer_lease_expires_at <= now,
                    ],
                    data={
                        "consumer_status": next_consumer,
                        "consumer_owner_id": None,
                        "consumer_lease_expires_at": None,
                        "consumer_next_retry_at": None if next_consumer == "dead_letter" else now,
                        "consumer_finished_at": now if next_consumer == "dead_letter" else None,
                        "consumer_last_error": "consumer_lease_expired",
                    },
                )
                if changed:
                    recovered[f"consumer_{'dead_letter' if next_consumer == 'dead_letter' else 'retry'}"] += 1
                continue
            next_status = "dead_letter" if row.attempt_count >= max_attempts else "retry"
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.event_id == row.event_id,
                    self.model.tenant_id == row.tenant_id,
                    self.model.publish_status == "publishing",
                    self.model.relay_owner_id == row.relay_owner_id,
                    self.model.relay_lease_expires_at <= now,
                ],
                data={
                    "publish_status": next_status,
                    "next_retry_at": None if next_status == "dead_letter" else now,
                    "last_error": "relay_lease_expired",
                    "relay_owner_id": None,
                    "relay_lease_expires_at": None,
                },
            )
            if changed:
                recovered[next_status] += 1
        return recovered

    @staticmethod
    def _validate_error_class(error_class: str) -> None:
        if (
            not isinstance(error_class, str)
            or not error_class.strip()
            or len(error_class) > 255
        ):
            raise ValueError("outbox_error_class_invalid")

    @classmethod
    def _validate_event(cls, values: dict[str, Any]) -> None:
        message = values.get("message_json")
        if not isinstance(message, dict) or set(message) != cls.MESSAGE_FIELDS:
            raise ValueError("outbox_message_fields_invalid")
        if type(message["expected_version"]) is not int or message["expected_version"] < 0:
            raise ValueError("outbox_message_version_invalid")
        for key, value in message.items():
            if key == "expected_version":
                continue
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"outbox_message_{key}_invalid")
        payload = json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if values.get("message_payload_hash") != expected_hash:
            raise ValueError("outbox_message_hash_mismatch")
        if values.get("message_whitelist_version") != cls.MESSAGE_WHITELIST_VERSION:
            raise ValueError("outbox_message_whitelist_version_invalid")
        if values.get("event_type") not in cls.EVENT_TYPES:
            raise ValueError("outbox_event_type_invalid")
        if values.get("publish_status") not in cls.PUBLISH_STATUSES:
            raise ValueError("outbox_publish_status_invalid")
        if not values.get("tenant_id"):
            raise ValueError("outbox_tenant_required")
        if values.get("run_id") != message["run_id"]:
            raise ValueError("outbox_run_id_mismatch")
        if values.get("task_id") != message["task_id"]:
            raise ValueError("outbox_task_id_mismatch")
        if values.get("release_fingerprint") != message["release_fingerprint"]:
            raise ValueError("outbox_release_mismatch")
        if values.get("expected_version") != message["expected_version"]:
            raise ValueError("outbox_expected_version_mismatch")
        if values.get("trace_namespace") != message["trace_namespace"]:
            raise ValueError("outbox_trace_mismatch")
        if values.get("id") == values.get("task_id"):
            raise ValueError("outbox_event_task_id_must_differ")
