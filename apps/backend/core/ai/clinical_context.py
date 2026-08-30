"""Versioned technical contract for frozen XRay clinical context.

The caller owns the clinical facts.  This module only normalizes and verifies
the small allowlist, provenance, snapshot hash and replay boundary; it must not
infer diagnoses or extract medical facts from free text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from apps.backend.core.ai.prompting.contracts import canonical_json, sha256_json

CLINICAL_CONTEXT_V1 = "xray-clinical-context.v1"
CLINICAL_CONTEXT_LEGACY_NONE = "legacy-none"
CLINICAL_CONTEXT_TEMPORAL_SCOPE = "available_at_request"
CLINICAL_CONTEXT_MAX_BYTES = 4096
CLINICAL_CONTEXT_MAX_SOURCE_SYSTEM_CHARS = 64
CLINICAL_CONTEXT_MAX_TEXT_CHARS = 2000
EMPTY_CLINICAL_CONTEXT_SHA256 = sha256_json({})

_SNAPSHOT_CONTEXT_KEY = "clinical_context_allowlist"
_SNAPSHOT_POLICY_KEY = "clinical_context_policy_version"
_SNAPSHOT_SHA_KEY = "clinical_context_sha256"
_PAYLOAD_KEYS = frozenset(
    {"contract_version", "source", "chief_complaint", "study_reason"}
)
_SOURCE_KEYS = frozenset({"system", "recorded_at", "temporal_scope"})


class ClinicalContextContractError(ValueError):
    """Raised when an ingress or frozen clinical-context contract is invalid."""


@dataclass(frozen=True)
class FrozenClinicalContext:
    policy_version: str
    payload_sha256: str
    payload: dict[str, Any]
    legacy_absent: bool = False

    def snapshot_fields(self) -> dict[str, Any]:
        return {
            _SNAPSHOT_POLICY_KEY: self.policy_version,
            _SNAPSHOT_SHA_KEY: self.payload_sha256,
            _SNAPSHOT_CONTEXT_KEY: self.payload,
        }


def normalize_clinical_context_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical v1 allowlist without adding clinical content."""

    if not isinstance(value, Mapping) or set(value) - _PAYLOAD_KEYS:
        raise ClinicalContextContractError("task_clinical_context_fields_invalid")
    if value.get("contract_version") != CLINICAL_CONTEXT_V1:
        raise ClinicalContextContractError("task_clinical_context_version_invalid")

    source = value.get("source")
    if not isinstance(source, Mapping) or set(source) != _SOURCE_KEYS:
        raise ClinicalContextContractError("task_clinical_context_source_invalid")
    system = source.get("system")
    recorded_at = source.get("recorded_at")
    temporal_scope = source.get("temporal_scope")
    if (
        not isinstance(system, str)
        or not system
        or system != system.strip()
        or len(system) > CLINICAL_CONTEXT_MAX_SOURCE_SYSTEM_CHARS
    ):
        raise ClinicalContextContractError("task_clinical_context_source_invalid")
    if not isinstance(recorded_at, str) or not recorded_at:
        raise ClinicalContextContractError("task_clinical_context_recorded_at_invalid")
    try:
        parsed_recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClinicalContextContractError(
            "task_clinical_context_recorded_at_invalid"
        ) from exc
    if parsed_recorded_at.tzinfo is None or parsed_recorded_at.utcoffset() is None:
        raise ClinicalContextContractError("task_clinical_context_recorded_at_invalid")
    if temporal_scope != CLINICAL_CONTEXT_TEMPORAL_SCOPE:
        raise ClinicalContextContractError(
            "task_clinical_context_temporal_scope_invalid"
        )

    normalized: dict[str, Any] = {
        "contract_version": CLINICAL_CONTEXT_V1,
        "source": {
            "system": system,
            "recorded_at": recorded_at,
            "temporal_scope": CLINICAL_CONTEXT_TEMPORAL_SCOPE,
        },
    }
    for key in ("chief_complaint", "study_reason"):
        item = value.get(key)
        if item is None:
            continue
        if (
            not isinstance(item, str)
            or not item
            or item != item.strip()
            or len(item) > CLINICAL_CONTEXT_MAX_TEXT_CHARS
        ):
            raise ClinicalContextContractError("task_clinical_context_text_invalid")
        normalized[key] = item
    if not any(key in normalized for key in ("chief_complaint", "study_reason")):
        raise ClinicalContextContractError("task_clinical_context_fact_required")
    if len(canonical_json(normalized).encode("utf-8")) > CLINICAL_CONTEXT_MAX_BYTES:
        raise ClinicalContextContractError("task_clinical_context_too_large")
    return normalized


def freeze_clinical_context(
    value: Mapping[str, Any] | None,
) -> FrozenClinicalContext:
    payload = normalize_clinical_context_payload(value) if value is not None else {}
    return FrozenClinicalContext(
        policy_version=CLINICAL_CONTEXT_V1,
        payload_sha256=sha256_json(payload),
        payload=payload,
    )


def read_frozen_clinical_context(
    snapshot: Mapping[str, Any],
) -> FrozenClinicalContext:
    """Read v1 facts or map a historical snapshot with no D2 keys to empty."""

    if not isinstance(snapshot, Mapping):
        raise ClinicalContextContractError("task_clinical_context_snapshot_invalid")
    present = {
        key
        for key in (_SNAPSHOT_CONTEXT_KEY, _SNAPSHOT_POLICY_KEY, _SNAPSHOT_SHA_KEY)
        if key in snapshot
    }
    if not present:
        payload: dict[str, Any] = {}
        return FrozenClinicalContext(
            policy_version=CLINICAL_CONTEXT_LEGACY_NONE,
            payload_sha256=EMPTY_CLINICAL_CONTEXT_SHA256,
            payload=payload,
            legacy_absent=True,
        )
    if present != {_SNAPSHOT_CONTEXT_KEY, _SNAPSHOT_POLICY_KEY, _SNAPSHOT_SHA_KEY}:
        raise ClinicalContextContractError("task_clinical_context_snapshot_invalid")
    if snapshot.get(_SNAPSHOT_POLICY_KEY) != CLINICAL_CONTEXT_V1:
        raise ClinicalContextContractError("task_clinical_context_snapshot_invalid")
    raw_payload = snapshot.get(_SNAPSHOT_CONTEXT_KEY)
    if not isinstance(raw_payload, Mapping):
        raise ClinicalContextContractError("task_clinical_context_snapshot_invalid")
    payload = normalize_clinical_context_payload(raw_payload) if raw_payload else {}
    payload_sha256 = snapshot.get(_SNAPSHOT_SHA_KEY)
    if not isinstance(payload_sha256, str) or payload_sha256 != sha256_json(payload):
        raise ClinicalContextContractError("task_clinical_context_snapshot_mismatch")
    return FrozenClinicalContext(
        policy_version=CLINICAL_CONTEXT_V1,
        payload_sha256=payload_sha256,
        payload=payload,
    )


__all__ = [
    "CLINICAL_CONTEXT_LEGACY_NONE",
    "CLINICAL_CONTEXT_MAX_BYTES",
    "CLINICAL_CONTEXT_MAX_SOURCE_SYSTEM_CHARS",
    "CLINICAL_CONTEXT_MAX_TEXT_CHARS",
    "CLINICAL_CONTEXT_TEMPORAL_SCOPE",
    "CLINICAL_CONTEXT_V1",
    "EMPTY_CLINICAL_CONTEXT_SHA256",
    "ClinicalContextContractError",
    "FrozenClinicalContext",
    "freeze_clinical_context",
    "normalize_clinical_context_payload",
    "read_frozen_clinical_context",
]
