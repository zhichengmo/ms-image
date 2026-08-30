"""Dependency readiness for the independent AI Control application."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from apps.backend.core.async_db import async_engine
from apps.backend.core.config import settings
from apps.backend.core.dependencies import control_plane_jwt_readiness
from apps.backend.schemas.ai_control import (
    AIControlReadinessComponent,
    AIControlReadinessComponents,
    AIControlReadinessResponse,
)
from apps.backend.services.ai_control.service.prompt_source import (
    NacosPromptSourceClient,
    PromptSourceError,
)


async def _database_ready() -> tuple[bool, str | None]:
    try:
        async with async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, None
    except Exception:
        return False, "database_unavailable"


async def _nacos_ready() -> AIControlReadinessComponent:
    server_addr = settings.NACOS_SERVER_ADDR.strip()
    if not server_addr:
        return AIControlReadinessComponent(
            required=False,
            ready=None,
            state="disabled",
            error=None,
        )

    namespace_id = (
        settings.NACOS_PROMPT_NAMESPACE_ID.strip()
        or settings.NACOS_NAMESPACE_ID.strip()
        or "public"
    )
    client: NacosPromptSourceClient | None = None
    outcome: AIControlReadinessComponent | None = None
    try:
        client = NacosPromptSourceClient(
            server_addr=server_addr,
            namespace_id=namespace_id,
            context_path=settings.NACOS_CONTEXT_PATH,
            username=settings.NACOS_USERNAME,
            password=settings.NACOS_PASSWORD,
            timeout_seconds=settings.NACOS_PROMPT_TIMEOUT_SECONDS,
            caller_service=settings.PROMPT_RUNTIME_CALLER_SERVICE,
        )
        await asyncio.wait_for(
            client.check_prompt_api_readiness(),
            timeout=settings.READINESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        outcome = AIControlReadinessComponent(
            required=True,
            ready=False,
            state="timeout",
            error="nacos_timeout",
        )
    except PromptSourceError:
        outcome = AIControlReadinessComponent(
            required=True,
            ready=False,
            state="unavailable",
            error="nacos_unavailable",
        )
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                outcome = AIControlReadinessComponent(
                    required=True,
                    ready=False,
                    state="unavailable",
                    error="nacos_unavailable",
                )
    if outcome is not None:
        return outcome
    return AIControlReadinessComponent(
        required=True,
        ready=True,
        state="ready",
        error=None,
    )


async def build_ai_control_readiness() -> AIControlReadinessResponse:
    timeout = settings.READINESS_TIMEOUT_SECONDS
    try:
        database_ready, database_error = await asyncio.wait_for(
            _database_ready(), timeout=timeout
        )
    except asyncio.TimeoutError:
        database_ready, database_error = False, "database_timeout"

    jwt_ready, jwt_error = control_plane_jwt_readiness()
    nacos = await _nacos_ready()
    ready = database_ready and jwt_ready and (
        not nacos.required or nacos.ready is True
    )
    return AIControlReadinessResponse(
        ready=ready,
        readiness_scope="ai_control",
        components=AIControlReadinessComponents(
            database=AIControlReadinessComponent(
                required=True,
                ready=database_ready,
                state="ready" if database_ready else "unavailable",
                error=database_error,
            ),
            control_plane_jwt=AIControlReadinessComponent(
                required=True,
                ready=jwt_ready,
                state="ready" if jwt_ready else "misconfigured",
                error=jwt_error,
            ),
            nacos=nacos,
        ),
    )


__all__ = ["build_ai_control_readiness"]
