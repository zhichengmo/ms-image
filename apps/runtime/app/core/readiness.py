"""Dependency readiness checks for the Phase 0 service boundary.

Liveness remains dependency-free.  Readiness reports the real dependency
state and never converts an unavailable dependency into a healthy result.
"""

import asyncio
from typing import Any

from sqlalchemy import text
from app.core.async_db import async_engine, evaluation_async_engine
from app.core.config import settings
from app.core.messaging.config import BrokerTopology, broker_url, topology_for
from app.core.redis_manager import RedisManager


async def _database_ready(engine: Any, *, error_code: str) -> tuple[bool, str | None]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, None
    except Exception:  # Do not expose driver/URL details through a probe.
        return False, error_code


async def _provider_ready() -> dict[str, Any]:
    """Target Provider gate while real Provider runtime remains unimplemented.

    The legacy XRay prompt/config tables must not make target readiness appear
    qualified.  P4.4 replaces this static gate with a contribution sourced
    from the frozen target AI Config release and Provider qualification facts.
    """
    return {
        "transport": {
            "state": "not_implemented",
            "ready": False,
            "error": "target_provider_not_qualified",
        },
        "receipt": {
            "state": "blocked_by_transport",
            "ready": False,
            "error": None,
        },
    }


async def _broker_domain_ready(
    topology: BrokerTopology,
) -> tuple[bool, str | None, str, dict[str, int | bool | None]]:
    unavailable_metrics = {
        "consumer_count": None,
        "queue_message_count": None,
        "dead_letter_message_count": None,
        # AMQP queue.declare exposes depth but not per-message timestamps.
        "oldest_message_age_seconds": None,
        "oldest_message_age_supported": False,
    }
    if not settings.BROKER_ENABLED:
        return True, None, "disabled", unavailable_metrics

    def _declaration_counts(declaration: Any) -> tuple[int, int]:
        try:
            return int(declaration[1]), int(declaration[2])
        except (IndexError, TypeError, ValueError):
            return (
                int(getattr(declaration, "message_count", 0) or 0),
                int(getattr(declaration, "consumer_count", 0) or 0),
            )

    def ping() -> dict[str, int | bool | None]:
        from kombu import Connection, Exchange, Queue

        connection = Connection(
            broker_url(), connect_timeout=settings.READINESS_TIMEOUT_SECONDS
        )
        connection.connect()
        try:
            exchange = Exchange(topology.exchange, type="direct", durable=True)
            dead_exchange = Exchange(
                f"{topology.exchange}.dlx", type="direct", durable=True
            )
            dead_exchange.maybe_bind(connection).declare()
            worker_queue = Queue(
                topology.queue,
                exchange=exchange,
                routing_key=topology.routing_key,
                durable=True,
                queue_arguments={
                    "x-dead-letter-exchange": dead_exchange.name,
                    "x-dead-letter-routing-key": topology.dead_letter_queue,
                },
            )
            worker_queue.maybe_bind(connection)
            message_count, consumer_count = _declaration_counts(
                worker_queue.queue_declare()
            )
            if consumer_count < 1:
                raise RuntimeError("worker_consumer_unavailable")
            dead_letter_queue = Queue(
                topology.dead_letter_queue,
                exchange=dead_exchange,
                routing_key=topology.dead_letter_queue,
                durable=True,
            )
            dead_letter_queue.maybe_bind(connection)
            dead_letter_message_count, _ = _declaration_counts(
                dead_letter_queue.queue_declare()
            )
            return {
                "consumer_count": consumer_count,
                "queue_message_count": message_count,
                "dead_letter_message_count": dead_letter_message_count,
                "oldest_message_age_seconds": None,
                "oldest_message_age_supported": False,
            }
        finally:
            connection.release()

    try:
        metrics = await asyncio.to_thread(ping)
        return True, None, "ready", metrics
    except Exception:
        return (
            False,
            f"{topology.domain}_worker_consumer_unavailable",
            "worker_missing",
            unavailable_metrics,
        )


async def build_readiness(redis_manager: RedisManager) -> dict[str, Any]:
    timeout = settings.READINESS_TIMEOUT_SECONDS
    try:
        redis_ready = await asyncio.wait_for(
            redis_manager.check_readiness(), timeout=timeout
        )
        redis_error = redis_manager.last_error
    except asyncio.TimeoutError:
        redis_ready = False
        redis_error = "redis_timeout"

    try:
        database_ready, database_error = await asyncio.wait_for(
            _database_ready(async_engine, error_code="database_unavailable"),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        database_ready, database_error = False, "database_timeout"
    try:
        evaluation_database_ready, evaluation_database_error = await asyncio.wait_for(
            _database_ready(
                evaluation_async_engine,
                error_code="evaluation_database_unavailable",
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        evaluation_database_ready, evaluation_database_error = (
            False,
            "evaluation_database_timeout",
        )

    imaging_topology = topology_for("imaging", source=settings)
    evaluation_topology = topology_for("evaluation", source=settings)
    try:
        (
            imaging_broker_ready,
            imaging_broker_error,
            imaging_broker_state,
            imaging_broker_metrics,
        ) = await asyncio.wait_for(
            _broker_domain_ready(imaging_topology), timeout=timeout
        )
    except asyncio.TimeoutError:
        (
            imaging_broker_ready,
            imaging_broker_error,
            imaging_broker_state,
            imaging_broker_metrics,
        ) = (
            False,
            "imaging_broker_timeout",
            "timeout",
            {
                "consumer_count": None,
                "queue_message_count": None,
                "dead_letter_message_count": None,
                "oldest_message_age_seconds": None,
                "oldest_message_age_supported": False,
            },
        )
    try:
        (
            evaluation_broker_ready,
            evaluation_broker_error,
            evaluation_broker_state,
            evaluation_broker_metrics,
        ) = await asyncio.wait_for(
            _broker_domain_ready(evaluation_topology), timeout=timeout
        )
    except asyncio.TimeoutError:
        (
            evaluation_broker_ready,
            evaluation_broker_error,
            evaluation_broker_state,
            evaluation_broker_metrics,
        ) = (
            False,
            "evaluation_broker_timeout",
            "timeout",
            {
                "consumer_count": None,
                "queue_message_count": None,
                "dead_letter_message_count": None,
                "oldest_message_age_seconds": None,
                "oldest_message_age_supported": False,
            },
        )

    provider = await _provider_ready()
    transport_ready = provider["transport"]["ready"]
    receipt_ready = provider["receipt"]["ready"]
    imaging_worker_ready = imaging_broker_ready if settings.BROKER_ENABLED else False
    evaluation_worker_ready = (
        evaluation_broker_ready if settings.BROKER_ENABLED else False
    )
    online_engineering_ready = database_ready and redis_ready and imaging_worker_ready
    evaluation_engineering_ready = evaluation_database_ready and evaluation_worker_ready
    engineering_worker_ready = online_engineering_ready and evaluation_engineering_ready
    medical_provider_ready = (
        engineering_worker_ready and transport_ready and receipt_ready
    )
    return {
        "ready": engineering_worker_ready,
        "service_mode": "worker" if settings.BROKER_ENABLED else "api_only",
        "worker_ready": imaging_worker_ready and evaluation_worker_ready,
        "online_engineering_ready": online_engineering_ready,
        "evaluation_engineering_ready": evaluation_engineering_ready,
        "engineering_worker_ready": engineering_worker_ready,
        "medical_provider_ready": medical_provider_ready,
        "components": {
            "database": {
                "ready": database_ready,
                "error": database_error,
            },
            "evaluation_database": {
                "ready": evaluation_database_ready,
                "error": evaluation_database_error,
            },
            "redis": {
                "ready": redis_ready,
                "error": redis_error,
            },
            "imaging_broker": {
                "ready": imaging_broker_ready if settings.BROKER_ENABLED else None,
                "required": settings.BROKER_ENABLED,
                "state": imaging_broker_state,
                "error": imaging_broker_error,
                **imaging_broker_metrics,
            },
            "evaluation_broker": {
                "ready": evaluation_broker_ready if settings.BROKER_ENABLED else None,
                "required": settings.BROKER_ENABLED,
                "state": evaluation_broker_state,
                "error": evaluation_broker_error,
                **evaluation_broker_metrics,
            },
            "provider": {
                "required": False,
                **provider,
            },
        },
        "broker_enabled": settings.BROKER_ENABLED,
    }
