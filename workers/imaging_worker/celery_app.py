"""Shared Celery runtime for target imaging tasks."""

from app.core.config import settings
from app.core.messaging.celery import create_celery_app
from app.core.messaging.config import runtime_config, topology_for


runtime = runtime_config(source=settings, prefix="IMAGING")
topology = topology_for("imaging", source=settings)
celery_app = create_celery_app(
    name="imaging",
    runtime=runtime,
    topology=topology,
)


__all__ = ["celery_app", "runtime", "topology"]
