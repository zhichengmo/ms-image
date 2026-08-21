"""FastAPI lifecycle wiring for the Runtime user and admin applications."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.backend.core.redis_manager import RedisManager


redis_manager = RedisManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and close the shared Runtime Redis client."""

    app.state.redis_manager = redis_manager
    await redis_manager.init_redis_pool(app)
    try:
        yield
    finally:
        await redis_manager.close_redis_pool()


__all__ = ["lifespan", "redis_manager"]
