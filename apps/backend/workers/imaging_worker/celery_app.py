"""Shared Celery runtime and task registration for target imaging work."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from celery.exceptions import MaxRetriesExceededError, Reject
from celery.utils.log import get_task_logger

from apps.backend.core.async_db import async_engine, session_factory
from apps.backend.core.config import settings
from apps.backend.core.messaging.celery import create_celery_app
from apps.backend.core.messaging.config import runtime_config, topology_for

from .ai_attempt_reconcile import AIAttemptReconcileWorker
from .image_validation import ImageValidationWorker
from .stage_execution import StageExecutionWorker


AI_ATTEMPT_RECONCILE_TASK_NAME = "imaging.reconcile_ai_attempts"
AI_ATTEMPT_RECONCILE_SCHEDULE_KEY = "imaging-ai-attempt-reconcile"

runtime = runtime_config(source=settings, prefix="IMAGING")
topology = topology_for("imaging", source=settings)
celery_app = create_celery_app(
    name="imaging",
    runtime=runtime,
    topology=topology,
)
logger = get_task_logger(__name__)


def build_ai_attempt_reconcile_schedule(
    *,
    enabled: bool,
    interval_seconds: int,
    batch_limit: int,
) -> dict[str, dict[str, Any]]:
    """Build the single-owner Beat entry with an explicit imaging route."""

    if not enabled:
        return {}
    if interval_seconds < 30 or interval_seconds > 3600:
        raise ValueError("ai_attempt_reconcile_interval_invalid")
    if batch_limit < 1 or batch_limit > 500:
        raise ValueError("ai_attempt_reconcile_batch_limit_invalid")
    return {
        AI_ATTEMPT_RECONCILE_SCHEDULE_KEY: {
            "task": AI_ATTEMPT_RECONCILE_TASK_NAME,
            "schedule": float(interval_seconds),
            "args": (batch_limit,),
            "options": {
                "queue": topology.queue,
                "exchange": topology.exchange,
                "routing_key": topology.routing_key,
            },
        }
    }


celery_app.conf.beat_schedule = build_ai_attempt_reconcile_schedule(
    enabled=settings.AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED,
    interval_seconds=settings.AI_ATTEMPT_RECONCILE_INTERVAL_SECONDS,
    batch_limit=settings.AI_ATTEMPT_RECONCILE_BATCH_LIMIT,
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


@celery_app.task(
    name="imaging.execute_stage",
    bind=True,
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_stage(self: Any, message: dict[str, Any]) -> None:
    if not settings.BROKER_ENABLED:
        raise Reject("imaging_broker_disabled", requeue=False)
    if not isinstance(message, dict):
        raise Reject("stage_execution_message_invalid", requeue=False)
    event_id = str(self.request.id or "").strip()
    headers = self.request.headers or {}
    message_version = str(headers.get("message_version") or "").strip()
    trace_id = str(headers.get("trace_id") or "").strip()
    if not event_id or not message_version or not trace_id:
        raise Reject("stage_execution_consumer_identity_missing", requeue=False)

    async def run() -> dict[str, Any]:
        try:
            return await StageExecutionWorker(
                session_factory_=session_factory,
            ).execute(
                event_id=event_id,
                message=message,
                message_version=message_version,
                trace_id=trace_id,
                owner_id=f"celery:{self.request.hostname or 'worker'}:{event_id}"[:128],
                lease_seconds=runtime.worker_lease_seconds,
            )
        finally:
            await async_engine.dispose()

    try:
        result = asyncio.run(run())
    except Exception:
        raise Reject("stage_execution_worker_error", requeue=False)
    if result.get("outcome") == "conflict":
        raise Reject(str(result.get("error_code") or "stage_execution_conflict"), requeue=False)


@celery_app.task(
    name=AI_ATTEMPT_RECONCILE_TASK_NAME,
    bind=True,
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_ai_attempts(self: Any, limit: int = 50) -> None:
    if not settings.BROKER_ENABLED:
        raise Reject("imaging_broker_disabled", requeue=False)

    async def run() -> dict[str, int]:
        try:
            return await AIAttemptReconcileWorker(
                session_factory_=session_factory,
            ).run_once(
                limit=max(1, min(500, int(limit))),
                lease_seconds=settings.AI_ATTEMPT_RECONCILE_LEASE_SECONDS,
                retry_seconds=settings.AI_ATTEMPT_RECONCILE_RETRY_SECONDS,
                max_reconcile_count=settings.AI_ATTEMPT_RECONCILE_MAX_COUNT,
                max_unknown_age_seconds=(
                    settings.AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS
                ),
            )
        finally:
            await async_engine.dispose()

    try:
        outcomes = asyncio.run(run())
    except Exception:
        raise Reject("ai_attempt_reconcile_worker_error", requeue=False)
    logger.info(
        "ai_attempt_reconcile_completed %s",
        json.dumps(outcomes, sort_keys=True, separators=(",", ":")),
    )


__all__ = [
    "AI_ATTEMPT_RECONCILE_SCHEDULE_KEY",
    "AI_ATTEMPT_RECONCILE_TASK_NAME",
    "build_ai_attempt_reconcile_schedule",
    "celery_app",
    "execute_stage",
    "reconcile_ai_attempts",
    "runtime",
    "topology",
    "validate_image",
]
