"""Read a small, allow-listed projection of the legacy runtime environment.

The legacy ``vet-platform`` repository remains outside this service's runtime
dependency graph.  This module is intentionally limited to local qualification
and development bootstrap: values are read into process memory only and are
never copied into the repository, a database row, a message, or a log record.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values


DEFAULT_REFERENCE_ENV_PATH = Path(
    "/Users/mozhicheng/workspace/code/py-project-v2/"
    "vet-platform-system/vet-platform/.env"
)


def reference_env_path() -> Path:
    configured = os.getenv("MS_IMAGE_REFERENCE_ENV_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_REFERENCE_ENV_PATH


def read_reference_env(
    *,
    path: Path | None = None,
    keys: set[str] | frozenset[str] | None = None,
) -> dict[str, str]:
    """Return only non-empty, explicitly requested legacy variables."""

    source = path or reference_env_path()
    if not source.is_file():
        return {}
    requested = set(keys or ())
    values = dotenv_values(source)
    return {
        key: value
        for key, value in values.items()
        if key in requested and isinstance(value, str) and value.strip()
    }


def parse_secret_list(value: str | None) -> tuple[str, ...]:
    """Parse legacy key lists without exposing their contents."""

    if not isinstance(value, str) or not value.strip():
        return ()
    raw = value.strip()
    candidates: list[str]
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        decoded = None
    if isinstance(decoded, list):
        candidates = [item for item in decoded if isinstance(item, str)]
    else:
        candidates = raw.split(",")
    return tuple(item.strip().strip("'\"") for item in candidates if item.strip().strip("'\""))


__all__ = [
    "DEFAULT_REFERENCE_ENV_PATH",
    "parse_secret_list",
    "read_reference_env",
    "reference_env_path",
]
