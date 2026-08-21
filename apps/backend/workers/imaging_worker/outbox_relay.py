"""Executable target imaging Outbox relay."""

from __future__ import annotations

import argparse
import asyncio

from apps.backend.core.async_db import async_engine, session_factory
from apps.backend.core.messaging.outbox_relay import (
    OutboxPublishEnvelope,
    OutboxRelay,
)
from apps.backend.core.config import settings
from apps.backend.core.messaging.lifecycle import install_shutdown_handlers, touch_heartbeat
from apps.backend.crud.outbox import OutboxDal

from .celery_app import celery_app, runtime, topology


def publish(envelope: OutboxPublishEnvelope) -> str:
    task_name = {
        OutboxDal.IMAGE_DESTINATION_KEY: topology.task_name,
        OutboxDal.STAGE_DESTINATION_KEY: "imaging.execute_stage",
    }.get(envelope.destination_key)
    if task_name is None:
        raise ValueError("outbox_destination_not_registered")
    result = celery_app.send_task(
        task_name,
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
    owner_prefix="relay:imaging",
    dal_factory=OutboxDal,
)


async def _main(once: bool) -> None:
    stop_event = asyncio.Event()
    if not once:
        install_shutdown_handlers(stop_event)
    try:
        if once:
            print(
                {
                    "reconcile": await relay.reconcile_once(),
                    "relay": await relay.relay_once(),
                }
            )
        else:
            await relay.run_forever(
                stop_event=stop_event,
                on_cycle=lambda: touch_heartbeat(settings.IMAGING_RELAY_HEARTBEAT_PATH),
            )
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.once))


__all__ = ["publish", "relay"]
