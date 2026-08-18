"""Minimal image-resolution seam for the validation-only AI path."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.ai.contracts import ProviderImageInput


ALLOWED_IMAGE_RESOLVER_ERROR_CLASSES = frozenset(
    {
        "image_resolver_not_configured",
        "image_source_unavailable",
        "image_fetch_timeout",
        "image_source_forbidden",
        "image_manifest_invalid",
        "image_content_invalid",
        "image_hash_mismatch",
    }
)


class ImageResolverError(ValueError):
    """Stable, non-sensitive image-resolution failure."""

    def __init__(self, error_class: str):
        normalized = (
            error_class
            if error_class in ALLOWED_IMAGE_RESOLVER_ERROR_CLASSES
            else "image_content_invalid"
        )
        self.error_class = normalized
        super().__init__(normalized)


class ImageResolver(Protocol):
    async def resolve(
        self,
        *,
        tenant_id: str,
        run_id: str,
        manifest: list[dict[str, Any]],
    ) -> tuple[ProviderImageInput, ...]:
        """Resolve a frozen manifest to worker-memory image inputs."""


class FailClosedImageResolver:
    """Default until an approved storage adapter is configured."""

    async def resolve(
        self,
        *,
        tenant_id: str,
        run_id: str,
        manifest: list[dict[str, Any]],
    ) -> tuple[ProviderImageInput, ...]:
        del tenant_id, run_id, manifest
        raise ImageResolverError("image_resolver_not_configured")


__all__ = [
    "ALLOWED_IMAGE_RESOLVER_ERROR_CLASSES",
    "FailClosedImageResolver",
    "ImageResolver",
    "ImageResolverError",
]
