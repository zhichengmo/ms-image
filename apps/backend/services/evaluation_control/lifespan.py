"""Lifecycle for the offline Evaluation Control API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Keep a service-local lifecycle without allocating unused Runtime Redis."""
    yield


__all__ = ["lifespan"]
