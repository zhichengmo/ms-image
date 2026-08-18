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
from app.core.async_db import async_engine, session_factory
from app.core.config import settings
from app.core.redis_manager import RedisManager
from app.service.ai_governance_service import AIGovernanceService
from app.service.xray_accuracy.prompt_service import XRayPromptRegistry
from app.service.xray_accuracy.prompt_service import sha256_text


async def _database_ready() -> tuple[bool, str | None]:
    try:
        async with async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, None
    except Exception:  # Do not expose driver/URL details through a probe.
        return False, "database_unavailable"


async def _provider_ready() -> dict[str, Any]:
    """Expose transport and receipt gates independently."""
    if not settings.AI_CONFIG_VERSION.strip():
        return {
            "transport": {"state": "unconfigured", "ready": False, "error": "ai_config_version_missing"},
            "receipt": {"state": "blocked_by_transport", "ready": False, "error": None},
        }
    if not settings.AI_EGRESS_PROOF_SIGNING_KEY:
        return {"transport": {"state": "unconfigured", "ready": False, "error": "egress_proof_signing_key_missing"}, "receipt": {"state": "blocked_by_transport", "ready": False, "error": None}}
    if not settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY:
        return {"transport": {"state": "unconfigured", "ready": False, "error": "qualification_artifact_signing_key_missing"}, "receipt": {"state": "blocked_by_transport", "ready": False, "error": None}}
    try:
        registry = XRayPromptRegistry()
        manifest = registry.get_manifest("xray.request_gate.v1", language="en")
        _, schema_sha256 = registry.response_schema(manifest.schema_key)
    except (OSError, TypeError, ValueError):
        return {"transport": {"state": "unconfigured", "ready": False, "error": "prompt_or_schema_invalid"}, "receipt": {"state": "blocked_by_transport", "ready": False, "error": None}}
    try:
        async with session_factory() as db:
            async with db.begin():
                bundle = await AIGovernanceService(db).resolve(version=settings.AI_CONFIG_VERSION, language="en")
        connection = bundle.connection_entries[0]
    except (ValueError, IndexError):
        return {"transport": {"state": "unconfigured", "ready": False, "error": "ai_governance_unresolved"}, "receipt": {"state": "blocked_by_transport", "ready": False, "error": None}}
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
        "state": "qualified" if receipt_ready else "unsupported" if transport_ready else "blocked_by_transport",
        "ready": receipt_ready,
        "error": None if receipt_ready else "provider_receipt_not_qualified",
    }
    return {"transport": transport, "receipt": receipt}


async def _broker_ready() -> tuple[bool, str | None, str]:
    if not settings.BROKER_ENABLED:
        # Disabled is an explicit deployment mode, not proof that RabbitMQ is
        # reachable.  The top-level probe may still be ready for the current
        # non-worker scaffold, but consumers must inspect this state.
        return True, None, "disabled"
    def ping() -> None:
        from kombu import Connection, Exchange, Queue

        from app.core.messaging.config import broker_url

        connection = Connection(
            broker_url(), connect_timeout=settings.READINESS_TIMEOUT_SECONDS
        )
        connection.connect()
        try:
            exchange = Exchange(settings.XRAY_BROKER_EXCHANGE, type="direct", durable=True)
            dead_exchange = Exchange(
                f"{settings.XRAY_BROKER_EXCHANGE}.dlx", type="direct", durable=True
            )
            dead_exchange.maybe_bind(connection).declare()
            stage_queue = Queue(
                settings.XRAY_BROKER_QUEUE,
                exchange=exchange,
                routing_key=settings.XRAY_BROKER_ROUTING_KEY,
                durable=True,
                queue_arguments={
                    "x-dead-letter-exchange": dead_exchange.name,
                    "x-dead-letter-routing-key": settings.XRAY_BROKER_DLQ,
                },
            )
            stage_queue.maybe_bind(connection)
            # ``Queue.declare()`` returns only the queue name in Kombu.  The
            # lower-level declaration result carries the broker's live
            # consumer count and is what readiness must inspect.
            declaration = stage_queue.queue_declare()
            try:
                consumer_count = int(declaration[2])
            except (IndexError, TypeError, ValueError):
                consumer_count = int(getattr(declaration, "consumer_count", 0) or 0)
            if consumer_count < 1:
                raise RuntimeError("worker_consumer_unavailable")
            Queue(
                settings.XRAY_BROKER_DLQ,
                exchange=dead_exchange,
                routing_key=settings.XRAY_BROKER_DLQ,
                durable=True,
            ).maybe_bind(connection).declare()
        finally:
            connection.release()

    try:
        await asyncio.to_thread(ping)
        return True, None, "ready"
    except Exception:
        # Keep a stable distinction between broker topology and a missing
        # worker consumer without exposing connection details.
        return False, "worker_consumer_unavailable", "worker_missing"


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
            _database_ready(), timeout=timeout
        )
    except asyncio.TimeoutError:
        database_ready, database_error = False, "database_timeout"
    try:
        broker_ready, broker_error, broker_state = await asyncio.wait_for(
            _broker_ready(), timeout=timeout
        )
    except asyncio.TimeoutError:
        broker_ready, broker_error, broker_state = False, "broker_timeout", "timeout"
    provider = await _provider_ready()
    transport_ready = provider["transport"]["ready"]
    receipt_ready = provider["receipt"]["ready"]
    broker_worker_ready = broker_ready if settings.BROKER_ENABLED else False
    engineering_worker_ready = database_ready and redis_ready and broker_worker_ready and transport_ready
    medical_provider_ready = engineering_worker_ready and receipt_ready
    # Top-level readiness is deliberately the deployed engineering worker
    # contract. In API-only mode a manual qualification run must not make the
    # service look worker-ready to callers that only inspect `ready`.
    ready = engineering_worker_ready
    return {
        "ready": ready,
        # ``ready`` describes the currently deployed API process.  A disabled
        # broker is an explicit API-only mode and must never be mistaken for
        # a worker-qualified deployment.
        "service_mode": "worker" if settings.BROKER_ENABLED else "api_only",
        "worker_ready": broker_worker_ready,
        "engineering_worker_ready": engineering_worker_ready,
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
            "broker": {
                "ready": broker_ready if settings.BROKER_ENABLED else None,
                "required": settings.BROKER_ENABLED,
                "state": broker_state,
                "error": broker_error,
            },
            "provider": {
                "required": bool(settings.AI_CONFIG_VERSION.strip()),
                **provider,
            },
        },
        "broker_enabled": settings.BROKER_ENABLED,
    }
