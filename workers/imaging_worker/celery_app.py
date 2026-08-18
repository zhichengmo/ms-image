"""Shared Celery runtime and task registration for target imaging work."""

from __future__ import annotations

import asyncio
from typing import Any

from celery.exceptions import MaxRetriesExceededError, Reject

from app.core.async_db import async_engine, session_factory
from app.core.config import settings
from app.core.messaging.celery import create_celery_app
from app.core.messaging.config import runtime_config, topology_for

from .image_validation import ImageValidationWorker


runtime = runtime_config(source=settings, prefix="IMAGING")
topology = topology_for("imaging", source=settings)
celery_app = create_celery_app(
    name="imaging",
    runtime=runtime,
    topology=topology,
)


@celery_app.task(
    name=topology.task_name,
    bind=True,
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def validate_image(self: Any, message: dict[str, Any]) -> None:
    if not settings.BROKER_ENABLED:
        raise Reject("imaging_broker_disabled", requeue=False)
    if not isinstance(message, dict):
        raise Reject("image_validation_message_invalid", requeue=False)
    event_id = str(self.request.id or "").strip()
    headers = self.request.headers or {}
    message_version = str(headers.get("message_version") or "").strip()
    trace_id = str(headers.get("trace_id") or "").strip()
    if not event_id or not message_version or not trace_id:
        raise Reject("image_validation_consumer_identity_missing", requeue=False)
    owner_id = f"celery:{self.request.hostname or 'worker'}:{event_id}"[:128]

    async def run() -> dict[str, Any]:
        try:
            return await ImageValidationWorker(
                session_factory_=session_factory,
            ).execute(
                event_id=event_id,
                message=message,
                message_version=message_version,
                header_trace_id=trace_id,
                owner_id=owner_id,
                lease_seconds=runtime.worker_lease_seconds,
                max_attempts=runtime.max_attempts,
            )
        finally:
            await async_engine.dispose()

    try:
        result = asyncio.run(run())
    except Reject:
        raise
    except Exception:
        raise Reject("image_validation_worker_error", requeue=False)
    if result.get("outcome") == "retry":
        try:
            raise self.retry(
                countdown=int(result["retry_after_seconds"]),
                max_retries=runtime.max_attempts,
            )
        except MaxRetriesExceededError:
            raise Reject("validation_attempts_exhausted", requeue=False)
    if result.get("outcome") == "dead_letter":
        raise Reject(str(result.get("error_code") or "image_validation_dead_letter"), requeue=False)


__all__ = ["celery_app", "runtime", "topology", "validate_image"]
