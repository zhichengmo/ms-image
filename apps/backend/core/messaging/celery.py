"""Shared Celery application factory.

Domain packages register their own tasks on the returned app; no domain
specific task or database import is placed in this common module.
"""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from .config import BrokerTopology, BrokerRuntimeConfig


def create_celery_app(
    *,
    name: str,
    runtime: BrokerRuntimeConfig,
    topology: BrokerTopology,
) -> Celery:
    app = Celery(name, broker=runtime.broker_url, backend=None)
    exchange = Exchange(topology.exchange, type="direct", durable=True)
    dead_exchange = Exchange(f"{topology.exchange}.dlx", type="direct", durable=True)
    app.conf.update(
        task_default_exchange=topology.exchange,
        task_default_exchange_type="direct",
        task_default_queue=topology.queue,
        task_default_routing_key=topology.routing_key,
        task_queues=(
            Queue(
                topology.queue,
                exchange=exchange,
                routing_key=topology.routing_key,
                durable=True,
                queue_arguments={
                    "x-dead-letter-exchange": dead_exchange.name,
                    "x-dead-letter-routing-key": topology.dead_letter_queue,
                },
            ),
            Queue(
                topology.dead_letter_queue,
                exchange=dead_exchange,
                routing_key=topology.dead_letter_queue,
                durable=True,
            ),
        ),
        task_ignore_result=True,
        result_backend=None,
        task_acks_late=True,
        task_acks_on_failure_or_timeout=False,
        task_reject_on_worker_lost=True,
        # The deployment contract uses one active task per worker process and
        # one reserved task per process.  Add throughput by scaling replicas,
        # not by silently increasing the unfinished work per worker.
        worker_concurrency=runtime.worker_concurrency,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        # RabbitMQ's AMQP channel must enter confirm mode before the relay
        # records publish_status=published.  Without this, send_task returning
        # only proves that the client accepted the bytes, not that the broker
        # durably accepted the delivery.
        broker_transport_options={"confirm_publish": True},
        task_serializer="json",
        accept_content=["json"],
        event_serializer="json",
        task_time_limit=max(30, runtime.worker_lease_seconds),
        task_soft_time_limit=max(15, runtime.worker_lease_seconds - 5),
    )
    return app


__all__ = ["create_celery_app"]
