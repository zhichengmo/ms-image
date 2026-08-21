"""Trusted online contexts and offline-only legacy import contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CallerContext:
    subject_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class ControlPlaneContext:
    subject_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class ExternalBusinessReference:
    source_system: str
    opaque_id: str


class LegacyMigrationAdapter(Protocol):
    """Offline import-only source.  It must never be an online owner."""

    async def read_provenance(self, external_ref: ExternalBusinessReference) -> dict: ...


__all__ = [
    "CallerContext",
    "ControlPlaneContext",
    "ExternalBusinessReference",
    "LegacyMigrationAdapter",
]
