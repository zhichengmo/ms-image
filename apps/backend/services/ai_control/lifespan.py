"""Lifecycle for the AI configuration control-plane API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.backend.core.async_db import async_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Release the AI Control database pool during application shutdown."""

    try:
        yield
    finally:
        await async_engine.dispose()


__all__ = ["lifespan"]
