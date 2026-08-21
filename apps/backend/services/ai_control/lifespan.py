"""Lifecycle for the AI configuration control-plane API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reserve a service-local lifecycle boundary without opening unused pools."""
    yield


__all__ = ["lifespan"]
