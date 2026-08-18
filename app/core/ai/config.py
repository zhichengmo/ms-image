"""Transport-only configuration DTOs.

Provider endpoint, model and credentials are resolved from the legacy AI
database chain.  This module intentionally has no environment-prefix parser.
"""

from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True)
class ProviderRuntimeConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    max_output_tokens: int


__all__ = ["ProviderRuntimeConfig"]
