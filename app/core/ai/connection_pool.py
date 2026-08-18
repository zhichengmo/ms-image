"""Provider-neutral connection pool with bounded retry and cooldown."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
from dataclasses import dataclass
from time import monotonic
from typing import Any, Awaitable, Callable

from .contracts import (
    AIConnectionConfig,
    AIRequestPolicy,
    ProviderAdapter,
    ProviderNotQualifiedError,
    ProviderRequest,
    ProviderRequestError,
    ProviderResponse,
    classify_provider_error,
)


@dataclass
class _ConnectionHealth:
    failed_at: float | None = None
    cooldown_until: float = 0.0
    last_error_class: str | None = None


@dataclass
class _ConnectionStats:
    success_count: int = 0
    failure_count: int = 0
    last_latency_ms: int | None = None
    last_error_class: str | None = None


class AIConnectionPool:
    """Bounded connection pool; MySQL remains the state source outside it."""

    def __init__(
        self,
        connections: list[AIConnectionConfig],
        *,
        provider_factory: Callable[[AIConnectionConfig], ProviderAdapter],
        policy: AIRequestPolicy | None = None,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        trace_sink: Callable[[dict[str, Any]], Any] | None = None,
        allow_network: bool = False,
    ):
        if not connections:
            raise ValueError("ai_connection_pool_empty")
        connection_ids = [connection.connection_id for connection in connections]
        if len(connection_ids) != len(set(connection_ids)):
            raise ValueError("ai_connection_id_invalid")
        if not allow_network and any(
            not connection.base_url.startswith("replay://") for connection in connections
        ):
            raise ValueError("real_provider_connection_disabled")
        self.connections = connections
        self.allow_network = allow_network
        self.provider_factory = provider_factory
        self.policy = policy or AIRequestPolicy()
        self.clock = clock
        self.sleeper = sleeper
        self.trace_sink = trace_sink
        self._health = {
            connection.connection_id: _ConnectionHealth() for connection in connections
        }
        self._stats = {
            connection.connection_id: _ConnectionStats() for connection in connections
        }
        self._provider_cache: dict[tuple[str, str, str], ProviderAdapter] = {}
        self._semaphore = asyncio.Semaphore(max(1, self.policy.concurrency))

    async def _emit_trace(self, event: dict[str, Any]) -> None:
        if self.trace_sink is None:
            return
        try:
            result = self.trace_sink(dict(event))
            if inspect.isawaitable(result):
                await result
        except Exception:
            return

    def _available(self, attempted: set[str]) -> list[AIConnectionConfig]:
        now = self.clock()
        return [
            connection
            for connection in self.connections
            if connection.enabled
            and connection.connection_id not in attempted
            and self._health[connection.connection_id].cooldown_until <= now
        ]

    async def _request_with_timeout(
        self,
        provider: ProviderAdapter,
        request: ProviderRequest,
        *,
        timeout_seconds: float,
    ) -> ProviderResponse:
        task = asyncio.create_task(provider.request(request))
        try:
            return await asyncio.wait_for(
                asyncio.shield(task), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            task.cancel()
            if self.policy.grace_timeout_seconds > 0:
                try:
                    await asyncio.wait_for(task, timeout=self.policy.grace_timeout_seconds)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            raise

    async def request(
        self, request: ProviderRequest
    ) -> tuple[ProviderResponse, dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        attempted: set[str] = set()
        first_connection_id: str | None = None
        last_error: ProviderRequestError | None = None
        request_started = self.clock()
        async with self._semaphore:
            for attempt_index in range(max(1, self.policy.max_attempts)):
                available = self._available(attempted)
                if not available:
                    attempted.clear()
                    available = self._available(attempted)
                if not available and last_error is not None and last_error.retryable:
                    now = self.clock()
                    cooldowns = [
                        self._health[connection.connection_id].cooldown_until - now
                        for connection in self.connections
                        if connection.enabled
                        and self._health[connection.connection_id].cooldown_until > now
                    ]
                    if cooldowns:
                        wait_seconds = min(cooldowns)
                        if request.deadline_seconds is not None:
                            remaining = request.deadline_seconds - (now - request_started)
                            if remaining <= 0 or wait_seconds >= remaining:
                                last_error = ProviderRequestError(
                                    "endpoint_timeout", retryable=False
                                )
                                break
                        await self.sleeper(wait_seconds)
                        available = self._available(attempted)
                if not available:
                    break
                connection = available[0]
                if first_connection_id is None:
                    first_connection_id = connection.connection_id
                attempted.add(connection.connection_id)
                provider_attempt_id = hashlib.sha256(
                    f"{request.attempt_id}:{request.request_nonce or ''}:"
                    f"{attempt_index}:{connection.connection_id}".encode("utf-8")
                ).hexdigest()[:32]
                request_for_connection = ProviderRequest(
                    **{
                        **request.__dict__,
                        "attempt_id": provider_attempt_id,
                        "requested_model": connection.model,
                        "connection_id": connection.connection_id,
                    }
                )
                started = self.clock()
                timeout_seconds = self.policy.hard_timeout_seconds
                if request.deadline_seconds is not None:
                    remaining = request.deadline_seconds - (started - request_started)
                    if remaining <= 0:
                        last_error = ProviderRequestError(
                            "endpoint_timeout", retryable=False
                        )
                        break
                    timeout_seconds = min(timeout_seconds, remaining)
                provider: ProviderAdapter | None = None
                try:
                    provider_key = (
                        connection.base_url,
                        connection.api_key_ref,
                        connection.model,
                    )
                    provider = self._provider_cache.get(provider_key)
                    if provider is None:
                        provider = self.provider_factory(connection)
                        self._provider_cache[provider_key] = provider
                    if not self.allow_network and provider.provider_key != "stub/replay":
                        raise ProviderNotQualifiedError("real_provider_not_enabled")
                    response = await self._request_with_timeout(
                        provider,
                        request_for_connection,
                        timeout_seconds=timeout_seconds,
                    )
                    trace = {
                        "connection_id": connection.connection_id,
                        "provider_key": provider.provider_key,
                        "stage_attempt_id": request.attempt_id,
                        "provider_attempt_id": provider_attempt_id,
                        "attempt": attempt_index,
                        "timeout": False,
                        "hard_timeout_seconds": self.policy.hard_timeout_seconds,
                        "grace_timeout_seconds": self.policy.grace_timeout_seconds,
                        "latency_ms": max(0, int((self.clock() - started) * 1000)),
                        "error_class": None,
                        "module_key": request.prompt.manifest.module_key,
                        "prompt_key": request.prompt.manifest.prompt_key,
                        "prompt_version": request.prompt.manifest.version,
                        "prompt_checksum": request.prompt.manifest.prompt_sha256,
                        "rendered_sha256": request.prompt.rendered_sha256,
                        "image_count": request.image_count,
                        "full_sent": request.full_sent,
                        "image_ordered_sha256": request.image_ordered_sha256,
                        "model": response.actual_model,
                        "stage": request.node_key,
                        "fallback_used": (
                            "yes"
                            if first_connection_id is not None
                            and connection.connection_id != first_connection_id
                            else "no"
                        ),
                    }
                    stats = self._stats[connection.connection_id]
                    stats.success_count += 1
                    stats.last_latency_ms = trace["latency_ms"]
                    stats.last_error_class = None
                    attempts.append(trace)
                    await self._emit_trace(trace)
                    return response, {
                        "attempts": attempts,
                        "retry_index": attempt_index,
                        "fallback_used": trace["fallback_used"],
                        "connection_id": connection.connection_id,
                        "provider_attempt_id": provider_attempt_id,
                    }
                except Exception as exc:
                    failure = classify_provider_error(exc)
                    last_error = failure
                    health = self._health[connection.connection_id]
                    health.failed_at = self.clock()
                    health.last_error_class = failure.error_class
                    if failure.error_class in {
                        "network_unreachable",
                        "provider_unavailable",
                        "rate_limited",
                    }:
                        cooldown = (
                            failure.retry_after
                            if failure.retry_after is not None
                            else connection.cooldown_seconds
                        )
                        health.cooldown_until = self.clock() + max(0.0, cooldown)
                    trace = {
                        "connection_id": connection.connection_id,
                        "provider_key": getattr(provider, "provider_key", "unknown"),
                        "stage_attempt_id": request.attempt_id,
                        "provider_attempt_id": provider_attempt_id,
                        "attempt": attempt_index,
                        "timeout": failure.error_class == "endpoint_timeout",
                        "hard_timeout_seconds": self.policy.hard_timeout_seconds,
                        "grace_timeout_seconds": self.policy.grace_timeout_seconds,
                        "latency_ms": max(0, int((self.clock() - started) * 1000)),
                        "error_class": failure.error_class,
                        "module_key": request.prompt.manifest.module_key,
                        "prompt_key": request.prompt.manifest.prompt_key,
                        "prompt_version": request.prompt.manifest.version,
                        "prompt_checksum": request.prompt.manifest.prompt_sha256,
                        "rendered_sha256": request.prompt.rendered_sha256,
                        "image_count": request.image_count,
                        "full_sent": request.full_sent,
                        "image_ordered_sha256": request.image_ordered_sha256,
                        "model": connection.model,
                        "stage": request.node_key,
                        "fallback_used": (
                            "yes"
                            if first_connection_id is not None
                            and connection.connection_id != first_connection_id
                            else "no"
                        ),
                    }
                    safe_evidence = getattr(failure, "safe_evidence", None)
                    if isinstance(safe_evidence, dict):
                        # The adapter supplies a bounded, secret-free
                        # projection of the response. Never copy raw output.
                        trace["provider_evidence"] = {
                            key: safe_evidence[key]
                            for key in (
                                "actual_model",
                                "finish_reason",
                                "latency_ms",
                                "provider_request_id_present",
                                "provider_request_id_sha256",
                                "raw_output_sha256",
                                "parsed_output_sha256",
                                "image_count_received",
                                "image_receipt_count",
                                "receipt_capability_version",
                                "request_nonce_echo_present",
                                "received_at_present",
                                "receipt_signature_present",
                                "expected_image_count",
                                "expected_ordered_sha256",
                                "usage",
                                "adapter_egress_proof",
                            )
                            if key in safe_evidence
                        }
                        trace["model"] = (
                            safe_evidence.get("actual_model") or connection.model
                        )
                    stats = self._stats[connection.connection_id]
                    stats.failure_count += 1
                    stats.last_latency_ms = trace["latency_ms"]
                    stats.last_error_class = failure.error_class
                    attempts.append(trace)
                    await self._emit_trace(trace)
                    if not failure.retryable or attempt_index + 1 >= self.policy.max_attempts:
                        break
                    delay = (
                        failure.retry_after
                        if failure.retry_after is not None
                        else min(
                            self.policy.max_backoff_seconds,
                            self.policy.backoff_base_seconds * (2**attempt_index),
                        )
                    )
                    if delay > 0:
                        await self.sleeper(delay)
        failure = last_error or ProviderRequestError("provider_unavailable", retryable=False)
        failure.attempts = attempts
        raise failure

    def connection_stats(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for connection in self.connections:
            stats = self._stats[connection.connection_id]
            total = stats.success_count + stats.failure_count
            result[connection.connection_id] = {
                "family": connection.family,
                "model": connection.model,
                "enabled": connection.enabled,
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "success_rate": stats.success_count / total if total else None,
                "failure_rate": stats.failure_count / total if total else None,
                "last_latency_ms": stats.last_latency_ms,
                "last_error_class": stats.last_error_class,
                "cooldown_until": self._health[connection.connection_id].cooldown_until,
            }
        return result


__all__ = ["AIConnectionPool"]
