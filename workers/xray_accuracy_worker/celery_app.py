"""XRay task registration on the shared Celery runtime."""

from __future__ import annotations

import asyncio
from typing import Any

from celery.exceptions import Reject

from app.core.async_db import async_engine, session_factory
from app.core.config import settings
from app.core.messaging.celery import create_celery_app
from app.core.messaging.config import broker_url, runtime_config, topology_for
from .technical_worker import XRayTechnicalWorker


_runtime = runtime_config(source=settings, prefix="XRAY")
_topology = topology_for("xray", source=settings)
celery_app = create_celery_app(
    name="xray_accuracy",
    runtime=_runtime,
    topology=_topology,
)


@celery_app.task(
    name=_topology.task_name,
    bind=True,
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_outbox(self: Any, message: dict[str, Any]) -> None:
    """Consume one whitelist message and commit its technical state."""
    if not settings.BROKER_ENABLED:
        raise Reject("xray_broker_disabled", requeue=False)
    if not isinstance(message, dict):
        raise Reject("xray_message_invalid", requeue=False)
    tenant_id = ((self.request.headers or {}).get("tenant_id") or "").strip()
    event_id = str(self.request.id or "").strip()
    if not tenant_id or not event_id:
        raise Reject("xray_consumer_identity_missing", requeue=False)

    async def run() -> dict[str, Any]:
        try:
            return await XRayTechnicalWorker(
                session_factory_=session_factory,
            ).execute_outbox_event(
                event_id=event_id,
                tenant_id=tenant_id,
                owner_id=f"celery:{self.request.hostname or 'worker'}:{event_id}"[:128],
                lease_seconds=_runtime.worker_lease_seconds,
            )
        finally:
            # asyncio.run creates a fresh loop for every task.  Dispose the
            # pooled engine before that loop closes so aiomysql connections are
            # never reused by a later task on a different loop.
            await async_engine.dispose()

    try:
        result = asyncio.run(run())
    except Reject:
        raise
    except Exception as exc:  # noqa: BLE001 - convert to a stable transport class
        del exc
        # Unknown application failures must be auditable in Rabbit's DLQ and
        # must not be ACKed with a traceback that could contain provider or
        # database connection details.
        raise Reject("worker_error", requeue=False)
    if isinstance(result, dict) and result.get("outcome") == "dead_letter":
        # The DB consumer state is the domain fact source; Rabbit's DLQ is the
        # transport audit copy for operators.  Never requeue an immutable
        # message already classified as dead_letter.
        raise Reject(str(result.get("error_class") or "xray_consumer_dead_letter"), requeue=False)


__all__ = ["celery_app", "execute_outbox", "broker_url"]
