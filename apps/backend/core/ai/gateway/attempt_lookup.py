"""Original Provider-attempt lookup boundary used by unknown reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

LookupStatus = Literal["succeeded", "failed", "unknown", "unsupported"]


class AttemptLookupError(RuntimeError):
    """The original Provider request could not be queried safely."""


@dataclass(frozen=True)
class AttemptLookupResult:
    """Normalized lookup outcome without ever authorizing a replacement request."""

    status: LookupStatus
    network_result: Mapping[str, Any] | None = None
    error_code: str | None = None
    retry_after_seconds: int = 300

    def __post_init__(self) -> None:
        if self.status not in {"succeeded", "failed", "unknown", "unsupported"}:
            raise AttemptLookupError("ai_attempt_lookup_status_invalid")
        if self.status == "succeeded" and not isinstance(self.network_result, Mapping):
            raise AttemptLookupError("ai_attempt_lookup_result_missing")
        if self.status != "succeeded" and self.network_result is not None:
            raise AttemptLookupError("ai_attempt_lookup_result_unexpected")
        if (
            not isinstance(self.retry_after_seconds, int)
            or isinstance(self.retry_after_seconds, bool)
            or self.retry_after_seconds < 30
            or self.retry_after_seconds > 86_400
        ):
            raise AttemptLookupError("ai_attempt_lookup_retry_invalid")


class ProviderAttemptLookup(Protocol):
    async def lookup(
        self, *, attempt_plan: Mapping[str, Any]
    ) -> AttemptLookupResult:
        """Query the original Provider request; never issue a replacement request."""


class UnsupportedProviderAttemptLookup:
    """Safe OpenAI-compatible default because no portable lookup API exists."""

    async def lookup(
        self, *, attempt_plan: Mapping[str, Any]
    ) -> AttemptLookupResult:
        del attempt_plan
        return AttemptLookupResult(
            status="unsupported",
            error_code="provider_attempt_lookup_unsupported",
            retry_after_seconds=3600,
        )


__all__ = [
    "AttemptLookupError",
    "AttemptLookupResult",
    "LookupStatus",
    "ProviderAttemptLookup",
    "UnsupportedProviderAttemptLookup",
]
