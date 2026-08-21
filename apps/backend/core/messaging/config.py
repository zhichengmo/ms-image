"""Shared broker/runtime configuration used by every imaging modality.

Only the domain topology (exchange/queue/routing key/task name) belongs to a
modality adapter.  Connection, lease, retry and readiness semantics are
shared here so CT/MRI/ultrasound workers cannot drift independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.backend.core.config import settings


@dataclass(frozen=True)
class BrokerTopology:
    domain: str
    exchange: str
    queue: str
    routing_key: str
    dead_letter_queue: str
    task_name: str


@dataclass(frozen=True)
class BrokerRuntimeConfig:
    enabled: bool
    broker_url: str
    relay_poll_seconds: float
    relay_lease_seconds: int
    worker_lease_seconds: int
    max_attempts: int


def broker_url(*, source: Any = settings) -> str:
    if _read(source, "CELERY_BROKER_URL").strip():
        return _read(source, "CELERY_BROKER_URL").strip()
    vhost = _read(source, "RABBITMQ_VIRTUAL_HOST").lstrip("/")
    return (
        f"amqp://{_read(source, 'RABBITMQ_USERNAME')}:{_read(source, 'RABBITMQ_PASSWORD')}@"
        f"{_read(source, 'RABBITMQ_HOST')}:{_read(source, 'RABBITMQ_PORT')}/{vhost}"
    )


def _read(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source[name]
    return getattr(source, name)


def runtime_config(*, source: Any = settings, prefix: str = "IMAGING") -> BrokerRuntimeConfig:
    """Build broker runtime settings from an injected domain prefix."""
    def value(suffix: str) -> Any:
        return _read(source, f"{prefix}_{suffix}")

    return BrokerRuntimeConfig(
        enabled=_read(source, "BROKER_ENABLED"),
        broker_url=broker_url(source=source),
        relay_poll_seconds=value("RELAY_POLL_SECONDS"),
        relay_lease_seconds=value("RELAY_LEASE_SECONDS"),
        worker_lease_seconds=value("WORKER_LEASE_SECONDS"),
        max_attempts=value("WORKER_MAX_ATTEMPTS"),
    )


def topology_for(
    domain: str,
    *,
    source: Any = settings,
    exchange: str | None = None,
    queue: str | None = None,
    routing_key: str | None = None,
    dead_letter_queue: str | None = None,
    task_name: str | None = None,
) -> BrokerTopology:
    """Return a domain-isolated topology without duplicating broker logic."""
    normalized = domain.strip().lower().replace("_", "-")
    if normalized == "imaging":
        return BrokerTopology(
            domain="imaging",
            exchange=exchange or _read(source, "IMAGING_BROKER_EXCHANGE"),
            queue=queue or _read(source, "IMAGING_BROKER_QUEUE"),
            routing_key=routing_key or _read(source, "IMAGING_BROKER_ROUTING_KEY"),
            dead_letter_queue=dead_letter_queue or _read(source, "IMAGING_BROKER_DLQ"),
            task_name=task_name or "imaging.validate_image",
        )
    if normalized == "evaluation":
        return BrokerTopology(
            domain="evaluation",
            exchange=exchange or _read(source, "EVALUATION_BROKER_EXCHANGE"),
            queue=queue or _read(source, "EVALUATION_BROKER_QUEUE"),
            routing_key=routing_key or _read(source, "EVALUATION_BROKER_ROUTING_KEY"),
            dead_letter_queue=dead_letter_queue or _read(source, "EVALUATION_BROKER_DLQ"),
            task_name=task_name or "evaluation.execute_job",
        )
    # Future modalities get isolated names while reusing this same runtime.
    return BrokerTopology(
        domain=normalized,
        exchange=exchange or f"{normalized}.v1",
        queue=queue or f"{normalized}.stage.requested",
        routing_key=routing_key or f"{normalized}.run.stage.requested",
        dead_letter_queue=dead_letter_queue or f"{normalized}.stage.dlq",
        task_name=task_name or f"{normalized}.execute_outbox",
    )


__all__ = ["BrokerTopology", "BrokerRuntimeConfig", "broker_url", "runtime_config", "topology_for"]
