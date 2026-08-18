"""XRay binding for the shared transactional-outbox relay."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.core.async_db import async_engine, session_factory
from app.core.config import settings
from app.core.messaging.config import runtime_config, topology_for
from app.core.messaging.outbox_relay import TransactionalOutboxRelay
from app.crud.xray_accuracy import XRayOutboxDal
from app.crud.xray_accuracy.stage_checkpoint import XRayStageCheckpointDal
from .celery_app import celery_app


_runtime = runtime_config(source=settings, prefix="XRAY")
_topology = topology_for("xray", source=settings)


def publish(event_id: str, tenant_id: str, message: dict[str, Any]) -> None:
    """Publish only the validated XRay message body over the shared broker."""
    celery_app.send_task(
        _topology.task_name,
        args=[message],
        task_id=event_id,
        queue=_topology.queue,
        routing_key=_topology.routing_key,
        exchange=_topology.exchange,
        headers={"tenant_id": tenant_id},
    )


relay = TransactionalOutboxRelay(
    session_factory=session_factory,
    dal_factory=XRayOutboxDal,
    publish=publish,
    runtime=_runtime,
    owner_prefix="relay:xray",
    reconcile_extra=lambda db, now, limit: XRayStageCheckpointDal(db).recover_expired_global(
        now=now, limit=limit
    ),
)


async def _main(once: bool) -> None:
    try:
        if once:
            print(
                {
                    "reconcile": await relay.reconcile_once(),
                    "relay": await relay.relay_once(),
                    "consumer_retry": await relay.consumer_retry_once(),
                }
            )
        else:
            await relay.run_forever()
    finally:
        # aiomysql owns callbacks on the active loop; dispose before
        # asyncio.run closes it so one-shot relay/reconcile exits cleanly.
        await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.once))


__all__ = ["relay", "publish"]
