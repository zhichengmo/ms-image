"""Dependency readiness checks for the Phase 0 service boundary.

Liveness remains dependency-free.  Readiness reports the real dependency
state and never converts an unavailable dependency into a healthy result.
"""

import asyncio
from typing import Any

from sqlalchemy import text
from apps.backend.core.async_db import async_engine, evaluation_async_engine
from apps.backend.core.config import settings
from apps.backend.core.messaging.config import BrokerTopology, broker_url, topology_for
from apps.backend.core.redis_manager import RedisManager


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


def _broker_timeout_result(*, error_code: str) -> tuple[
    bool,
    str,
    str,
    dict[str, int | bool | None],
]:
    return (
        False,
        error_code,
        "timeout",
        {
            "consumer_count": None,
            "queue_message_count": None,
            "dead_letter_message_count": None,
            "oldest_message_age_seconds": None,
            "oldest_message_age_supported": False,
        },
    )


async def _redis_dependency_ready(
    redis_manager: RedisManager,
    *,
    timeout: float,
) -> tuple[bool, str | None]:
    try:
        ready = await asyncio.wait_for(
            redis_manager.check_readiness(), timeout=timeout
        )
        return ready, redis_manager.last_error
    except asyncio.TimeoutError:
        return False, "redis_timeout"


async def _database_dependency_ready(
    engine: Any,
    *,
    unavailable_error: str,
    timeout_error: str,
    timeout: float,
) -> tuple[bool, str | None]:
    try:
        return await asyncio.wait_for(
            _database_ready(engine, error_code=unavailable_error),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return False, timeout_error


async def _broker_dependency_ready(
    topology: BrokerTopology,
    *,
    timeout_error: str,
    timeout: float,
) -> tuple[bool, str | None, str, dict[str, int | bool | None]]:
    try:
        return await asyncio.wait_for(
            _broker_domain_ready(topology), timeout=timeout
        )
    except asyncio.TimeoutError:
        return _broker_timeout_result(error_code=timeout_error)


async def build_runtime_readiness(redis_manager: RedisManager) -> dict[str, Any]:
    """Return readiness for the online Runtime plane only.

    Evaluation has an isolated database and worker domain. Its availability
    must not remove the upload/diagnosis Runtime from service or add its
    connection timeout to the Runtime probe.
    """
    timeout = settings.READINESS_TIMEOUT_SECONDS
    redis_ready, redis_error = await _redis_dependency_ready(
        redis_manager,
        timeout=timeout,
    )
    database_ready, database_error = await _database_dependency_ready(
        async_engine,
        unavailable_error="database_unavailable",
        timeout_error="database_timeout",
        timeout=timeout,
    )
    imaging_topology = topology_for("imaging", source=settings)
    (
        imaging_broker_ready,
        imaging_broker_error,
        imaging_broker_state,
        imaging_broker_metrics,
    ) = await _broker_dependency_ready(
        imaging_topology,
        timeout_error="imaging_broker_timeout",
        timeout=timeout,
    )

    provider = await _provider_ready()
    transport_ready = provider["transport"]["ready"]
    receipt_ready = provider["receipt"]["ready"]
    imaging_worker_ready = imaging_broker_ready if settings.BROKER_ENABLED else False
    online_engineering_ready = database_ready and redis_ready and imaging_worker_ready
    medical_provider_ready = (
        online_engineering_ready and transport_ready and receipt_ready
    )
    return {
        "ready": online_engineering_ready,
        "readiness_scope": "online_runtime",
        "service_mode": "worker" if settings.BROKER_ENABLED else "api_only",
        "worker_ready": imaging_worker_ready,
        "online_engineering_ready": online_engineering_ready,
        "engineering_worker_ready": online_engineering_ready,
        "medical_provider_ready": medical_provider_ready,
        "components": {
            "database": {
                "ready": database_ready,
                "error": database_error,
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
            "provider": {
                "required": False,
                **provider,
            },
        },
        "broker_enabled": settings.BROKER_ENABLED,
    }


async def build_readiness(redis_manager: RedisManager) -> dict[str, Any]:
    """Return the legacy aggregate readiness used by Runtime Admin views."""
    timeout = settings.READINESS_TIMEOUT_SECONDS
    redis_ready, redis_error = await _redis_dependency_ready(
        redis_manager,
        timeout=timeout,
    )
    database_ready, database_error = await _database_dependency_ready(
        async_engine,
        unavailable_error="database_unavailable",
        timeout_error="database_timeout",
        timeout=timeout,
    )
    evaluation_database_ready, evaluation_database_error = (
        await _database_dependency_ready(
            evaluation_async_engine,
            unavailable_error="evaluation_database_unavailable",
            timeout_error="evaluation_database_timeout",
            timeout=timeout,
        )
    )

    imaging_topology = topology_for("imaging", source=settings)
    evaluation_topology = topology_for("evaluation", source=settings)
    (
        imaging_broker_ready,
        imaging_broker_error,
        imaging_broker_state,
        imaging_broker_metrics,
    ) = await _broker_dependency_ready(
        imaging_topology,
        timeout_error="imaging_broker_timeout",
        timeout=timeout,
    )
    (
        evaluation_broker_ready,
        evaluation_broker_error,
        evaluation_broker_state,
        evaluation_broker_metrics,
    ) = await _broker_dependency_ready(
        evaluation_topology,
        timeout_error="evaluation_broker_timeout",
        timeout=timeout,
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
