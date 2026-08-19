"""Executable Evaluation Outbox relay using the shared relay semantics."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app.core.async_db import async_engine, session_factory
from app.core.messaging.outbox_relay import OutboxPublishEnvelope, OutboxRelay
from app.crud.evaluation import EvaluationOutboxDal
from app.service.evaluation_execution_service import EvaluationExecutionService

from .celery_app import celery_app, runtime, topology


def publish(envelope: OutboxPublishEnvelope) -> str:
    if envelope.destination_key != EvaluationOutboxDal.DESTINATION_KEY:
        raise ValueError("evaluation_outbox_destination_not_registered")
    result = celery_app.send_task(
        topology.task_name,
        args=[envelope.message],
        task_id=envelope.event_id,
        queue=topology.queue,
        routing_key=topology.routing_key,
        exchange=topology.exchange,
        headers={
            "message_version": envelope.message_version,
            "trace_id": envelope.trace_id,
        },
    )
    return str(result.id or envelope.event_id)


relay = OutboxRelay(
    session_factory=session_factory,
    publish=publish,
    runtime=runtime,
    owner_prefix="relay:evaluation",
    dal_factory=EvaluationOutboxDal,
)


async def _reconcile_jobs() -> dict[str, int]:
    async with session_factory() as session:
        async with session.begin():
            return await EvaluationExecutionService(session).reconcile_expired(
                now=datetime.utcnow(),
                max_attempts=runtime.max_attempts,
            )


async def _main(once: bool) -> None:
    try:
        if once:
            print(
                {
                    "job_reconcile": await _reconcile_jobs(),
                    "outbox_reconcile": await relay.reconcile_once(),
                    "relay": await relay.relay_once(),
                }
            )
        else:
            while True:
                await _reconcile_jobs()
                await relay.reconcile_once()
                await relay.relay_once()
                await asyncio.sleep(max(0.1, runtime.relay_poll_seconds))
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.once))


__all__ = ["publish", "relay"]
