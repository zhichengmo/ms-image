"""Dependency readiness checks for the Phase 0 service boundary.

Liveness remains dependency-free.  Readiness reports the real dependency
state and never converts an unavailable dependency into a healthy result.
"""

import asyncio
from typing import Any

from sqlalchemy import text
from app.core.ai.qualification import (
    qualification_artifact_is_current,
    transport_qualification_artifact_is_current,
)
from app.core.async_db import async_engine, evaluation_async_engine, session_factory
from app.core.config import settings
from app.core.messaging.config import BrokerTopology, broker_url, topology_for
from app.core.redis_manager import RedisManager
from app.service.ai_governance_service import AIGovernanceService
from app.service.xray_accuracy.prompt_service import XRayPromptRegistry
from app.service.xray_accuracy.prompt_service import sha256_text


async def _database_ready(engine: Any, *, error_code: str) -> tuple[bool, str | None]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, None
    except Exception:  # Do not expose driver/URL details through a probe.
        return False, error_code


async def _provider_ready() -> dict[str, Any]:
    """Expose transport and receipt gates independently."""
    if not settings.AI_CONFIG_VERSION.strip():
        return {
            "transport": {
                "state": "unconfigured",
                "ready": False,
                "error": "ai_config_version_missing",
            },
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    if not settings.AI_EGRESS_PROOF_SIGNING_KEY:
        return {
            "transport": {
                "state": "unconfigured",
                "ready": False,
                "error": "egress_proof_signing_key_missing",
            },
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    if not settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY:
        return {
            "transport": {
                "state": "unconfigured",
                "ready": False,
                "error": "qualification_artifact_signing_key_missing",
            },
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    try:
        registry = XRayPromptRegistry()
        manifest = registry.get_manifest("xray.request_gate.v1", language="en")
        _, schema_sha256 = registry.response_schema(manifest.schema_key)
    except (OSError, TypeError, ValueError):
        return {
            "transport": {
                "state": "unconfigured",
                "ready": False,
                "error": "prompt_or_schema_invalid",
            },
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    try:
        async with session_factory() as db:
            async with db.begin():
                bundle = await AIGovernanceService(db).resolve(
                    version=settings.AI_CONFIG_VERSION, language="en"
                )
        connection = bundle.connection_entries[0]
    except (ValueError, IndexError):
        return {
            "transport": {
                "state": "unconfigured",
                "ready": False,
                "error": "ai_governance_unresolved",
            },
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    governed_prompt_key = f"ai_prompt_template:{bundle.prompt.item_id}"
    governed_prompt_version = bundle.version
    governed_prompt_checksum = sha256_text(bundle.prompt.content.strip())
    transport_ready = transport_qualification_artifact_is_current(
        settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
        base_url=connection.base_url,
        model=connection.model,
        api_key=connection.api_key,
        api_keys=(connection.api_key,),
        prompt_key=governed_prompt_key,
        prompt_version=governed_prompt_version,
        prompt_checksum=governed_prompt_checksum,
        schema_key=manifest.schema_key,
        schema_checksum=schema_sha256,
        artifact_signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
        egress_signing_key=settings.AI_EGRESS_PROOF_SIGNING_KEY,
    )
    transport = {
        "state": "qualified" if transport_ready else "unqualified",
        "ready": transport_ready,
        "error": None if transport_ready else "transport_not_qualified",
    }
    receipt_ready = qualification_artifact_is_current(
        settings.AI_QUALIFICATION_ARTIFACT_PATH,
        base_url=connection.base_url,
        model=connection.model,
        api_key=connection.api_key,
        api_keys=(connection.api_key,),
        prompt_key=governed_prompt_key,
        prompt_version=governed_prompt_version,
        prompt_checksum=governed_prompt_checksum,
        schema_key=manifest.schema_key,
        schema_checksum=schema_sha256,
        signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
    )
    receipt = {
        "state": "qualified"
        if receipt_ready
        else "unsupported"
        if transport_ready
        else "blocked_by_transport",
        "ready": receipt_ready,
        "error": None if receipt_ready else "provider_receipt_not_qualified",
    }
    return {"transport": transport, "receipt": receipt}


async def _broker_domain_ready(
    topology: BrokerTopology,
) -> tuple[bool, str | None, str]:
    if not settings.BROKER_ENABLED:
        return True, None, "disabled"

    def ping() -> None:
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
            declaration = worker_queue.queue_declare()
            try:
                consumer_count = int(declaration[2])
            except (IndexError, TypeError, ValueError):
                consumer_count = int(getattr(declaration, "consumer_count", 0) or 0)
            if consumer_count < 1:
                raise RuntimeError("worker_consumer_unavailable")
            Queue(
                topology.dead_letter_queue,
                exchange=dead_exchange,
                routing_key=topology.dead_letter_queue,
                durable=True,
            ).maybe_bind(connection).declare()
        finally:
            connection.release()

    try:
        await asyncio.to_thread(ping)
        return True, None, "ready"
    except Exception:
        return (
            False,
            f"{topology.domain}_worker_consumer_unavailable",
            "worker_missing",
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
        ) = await asyncio.wait_for(
            _broker_domain_ready(imaging_topology), timeout=timeout
        )
    except asyncio.TimeoutError:
        imaging_broker_ready, imaging_broker_error, imaging_broker_state = (
            False,
            "imaging_broker_timeout",
            "timeout",
        )
    try:
        (
            evaluation_broker_ready,
            evaluation_broker_error,
            evaluation_broker_state,
        ) = await asyncio.wait_for(
            _broker_domain_ready(evaluation_topology), timeout=timeout
        )
    except asyncio.TimeoutError:
        evaluation_broker_ready, evaluation_broker_error, evaluation_broker_state = (
            False,
            "evaluation_broker_timeout",
            "timeout",
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
            },
            "evaluation_broker": {
                "ready": evaluation_broker_ready if settings.BROKER_ENABLED else None,
                "required": settings.BROKER_ENABLED,
                "state": evaluation_broker_state,
                "error": evaluation_broker_error,
            },
            "provider": {
                "required": bool(settings.AI_CONFIG_VERSION.strip()),
                **provider,
            },
        },
        "broker_enabled": settings.BROKER_ENABLED,
    }
