"""Pure contracts for non-sensitive AI Platform connection metadata.

The Worker authenticates to ``ms-ai-platform`` exclusively through its
``AI_PLATFORM_OPENAI_BASE_URL`` and ``AI_PLATFORM_API_KEY`` process settings.
Connection rows therefore describe only non-sensitive routing and capability
metadata; this module never resolves credentials or contacts a Provider.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from apps.backend.core.ai.prompting.contracts import sha256_json


class ConnectionContractError(ValueError):
    """Raised when a non-sensitive connection metadata contract is invalid."""


def canonicalize_connection_base_url(base_url: str) -> str:
    """Return the sole persisted representation of an HTTP(S) Provider base URL.

    The OpenAI-compatible Platform used by ``ms-ai-fast`` is deployed behind
    both plain HTTP and HTTPS endpoints, so ``ms-image`` must preserve either
    transport scheme instead of silently rewriting or rejecting HTTP.  The
    canonical form lower-cases the scheme and host, removes the matching
    default port, removes a non-root trailing slash, and never contains
    userinfo, query parameters, or fragments.  It performs no DNS or network
    I/O and never carries a credential in the URL itself.
    """
    if not isinstance(base_url, str) or not base_url:
        raise ConnectionContractError("ai_connection_base_url_invalid")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise ConnectionContractError("ai_connection_base_url_invalid") from exc
    scheme = parsed.scheme.casefold()
    if (
        scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ConnectionContractError("ai_connection_base_url_invalid")

    host = parsed.hostname.casefold()
    # urlsplit().hostname intentionally drops IPv6 brackets; add them back when
    # reconstructing a legal URL authority.
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = 80 if scheme == "http" else 443
    authority = host if port in (None, default_port) else f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((scheme, authority, path, "", ""))


def canonical_connection_metadata_sha256(values: Mapping[str, Any]) -> str:
    """Hash canonical, non-sensitive Platform connection metadata."""
    try:
        base_url = canonicalize_connection_base_url(values["base_url"])
        payload = {
            "connection_key": values["connection_key"],
            "version": values["version"],
            "provider_type": values["provider_type"],
            "api_format": values["api_format"],
            "base_url": base_url,
            "region": values.get("region"),
            "capability_json": values["capability_json"],
        }
    except (KeyError, TypeError) as exc:
        raise ConnectionContractError("ai_connection_metadata_invalid") from exc
    return sha256_json(payload)


__all__ = [
    "ConnectionContractError",
    "canonical_connection_metadata_sha256",
    "canonicalize_connection_base_url",
]
