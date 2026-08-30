"""Shared immutable AI Config contract helpers.

The helpers in this module are intentionally side-effect free so control-plane
and runtime resolve exactly the same activation slot and canonical hashes.
"""

from __future__ import annotations

from typing import Any

from apps.backend.core.ai.prompting.contracts import sha256_json


AI_CONFIG_V2 = "ai-config.v2"
TASK_REQUEST_SNAPSHOT_V2 = "task-request-snapshot.v2"
TASK_REQUEST_SNAPSHOT_V3 = "task-request-snapshot.v3"


def activation_scope_payload(
    *,
    config_key: str,
    modality_type: str,
    task_type: str,
    activation_scope: str,
    scope_key: str,
) -> dict[str, str]:
    """Return the complete, unambiguous active-slot identity payload."""
    return {
        "activation_scope": activation_scope,
        "config_key": config_key,
        "modality_type": modality_type,
        "scope_key": scope_key,
        "task_type": task_type,
    }


def activation_slot_sha256(
    *,
    config_key: str,
    modality_type: str,
    task_type: str,
    activation_scope: str = "global",
    scope_key: str = "global",
) -> str:
    """Derive the fixed-width activation slot for a Config scope."""
    return sha256_json(
        activation_scope_payload(
            config_key=config_key,
            modality_type=modality_type,
            task_type=task_type,
            activation_scope=activation_scope,
            scope_key=scope_key,
        )
    )


def legacy_activation_slot(
    *,
    config_key: str,
    modality_type: str,
    task_type: str,
    activation_scope: str = "global",
    scope_key: str = "global",
) -> str:
    """Return the historical v1 slot only for read compatibility.

    New Config records never write this representation.  Keeping the fallback
    here lets v1 active records remain readable until the compatibility window
    closes without allowing colon-concatenated slots back into v2 writes.
    """
    return (
        f"{config_key}:{activation_scope}:{scope_key}:"
        f"{modality_type}:{task_type}"
    )


def is_v2_config(value: Any) -> bool:
    return getattr(value, "config_contract_version", None) == AI_CONFIG_V2


__all__ = [
    "AI_CONFIG_V2",
    "TASK_REQUEST_SNAPSHOT_V2",
    "TASK_REQUEST_SNAPSHOT_V3",
    "activation_scope_payload",
    "activation_slot_sha256",
    "is_v2_config",
    "legacy_activation_slot",
]
