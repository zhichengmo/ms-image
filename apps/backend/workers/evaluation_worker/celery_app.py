"""Celery runtime and task registration for the Evaluation control plane."""

from __future__ import annotations

import asyncio
from typing import Any

from celery.exceptions import MaxRetriesExceededError, Reject

from apps.backend.services.evaluation_control.config import settings
from apps.backend.core.async_db import evaluation_async_engine, evaluation_session_factory
from apps.backend.core.messaging.celery import create_celery_app
from apps.backend.core.messaging.config import runtime_config, topology_for

from .execution import EvaluationExecutionWorker


runtime = runtime_config(source=settings, prefix="EVALUATION")
topology = topology_for("evaluation", source=settings)
celery_app = create_celery_app(
    name="evaluation",
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
def execute_job(self: Any, message: dict[str, Any]) -> None:
    if not settings.BROKER_ENABLED:
        raise Reject("evaluation_broker_disabled", requeue=False)
    if not isinstance(message, dict):
        raise Reject("evaluation_message_invalid", requeue=False)
    event_id = str(self.request.id or "").strip()
    headers = self.request.headers or {}
    message_version = str(headers.get("message_version") or "").strip()
    trace_id = str(headers.get("trace_id") or "").strip()
    if not event_id or not message_version or not trace_id:
        raise Reject("evaluation_consumer_identity_missing", requeue=False)
    owner_id = f"celery:{self.request.hostname or 'worker'}:{event_id}"[:128]

    async def run() -> dict[str, Any]:
        try:
            return await EvaluationExecutionWorker(
                session_factory_=evaluation_session_factory
            ).execute(
                event_id=event_id,
                message=message,
                message_version=message_version,
                trace_id=trace_id,
                owner_id=owner_id,
                lease_seconds=runtime.worker_lease_seconds,
                max_attempts=runtime.max_attempts,
            )
        finally:
            await evaluation_async_engine.dispose()

    try:
        result = asyncio.run(run())
    except Reject:
        raise
    except Exception:
        raise Reject("evaluation_worker_error", requeue=False)
    if result.get("outcome") == "retry":
        try:
            raise self.retry(
                countdown=int(result["retry_after_seconds"]),
                max_retries=runtime.max_attempts,
            )
        except MaxRetriesExceededError:
            raise Reject("evaluation_attempts_exhausted", requeue=False)
    if result.get("outcome") in {"failed", "dead_letter"}:
        raise Reject(
            str(result.get("error_code") or "evaluation_execution_failed"),
            requeue=False,
        )


__all__ = ["celery_app", "execute_job", "runtime", "topology"]
