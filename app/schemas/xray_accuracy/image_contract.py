"""Shared request-boundary rules for source image metadata."""

from __future__ import annotations

from typing import Final


SUPPORTED_SOURCE_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/dicom",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


def normalize_source_mime_type(value: str | None) -> str | None:
    """Normalize an optional declared source MIME and reject unsupported types."""

    if value is None:
        return None
    normalized = value.casefold().strip()
    if normalized == "image/jpg":
        normalized = "image/jpeg"
    if normalized not in SUPPORTED_SOURCE_MIME_TYPES:
        raise ValueError("image_mime_type_not_allowed")
    return normalized


__all__ = ["SUPPORTED_SOURCE_MIME_TYPES", "normalize_source_mime_type"]
