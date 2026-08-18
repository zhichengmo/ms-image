"""Admin-scoped orchestration for the two Provider qualification gates."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ai.qualification import artifact_signature_is_valid


_QUALIFICATION_LOCK = asyncio.Lock()


class XRayProviderQualificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_transport_qualification(self) -> dict[str, Any]:
        if _QUALIFICATION_LOCK.locked():
            raise ValueError("provider_qualification_already_running")
        async with _QUALIFICATION_LOCK:
            from workers.xray_accuracy_worker.provider_qualification import qualify

            return await qualify()

    async def get_qualification(self, qualification_id: str) -> dict[str, Any]:
        if not qualification_id.strip():
            raise ValueError("qualification_id_invalid")
        candidates = (
            settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
            settings.AI_QUALIFICATION_ARTIFACT_PATH,
        )
        for candidate in candidates:
            try:
                artifact = json.loads(Path(candidate).read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(artifact, dict):
                continue
            signature_valid = artifact_signature_is_valid(
                artifact,
                signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
            )
            identifiers = {
                str(artifact.get("run_id") or ""),
                str(artifact.get("qualification_fingerprint") or ""),
            }
            if qualification_id in identifiers:
                if artifact.get("status") == "qualified" and not signature_valid:
                    raise ValueError("provider_qualification_signature_invalid")
                # Return an allowlisted operational projection. The raw proof
                # remains an on-disk audit artifact and is never exposed by a
                # query API, even to an administrator.
                provider = artifact.get("provider") or {}
                return {
                    "qualification_id": qualification_id,
                    "schema": artifact.get("schema"),
                    "status": artifact.get("status"),
                    "reason": artifact.get("reason"),
                    "retryable": artifact.get("retryable"),
                    "transport_status": artifact.get("transport_status"),
                    "receipt_status": artifact.get("receipt_status"),
                    "coverage_status": artifact.get("coverage_status"),
                    "medical_verdict_produced": artifact.get(
                        "medical_verdict_produced"
                    ),
                    "provider": {
                        "kind": provider.get("kind"),
                        "model": provider.get("model"),
                        "actual_model": provider.get("actual_model"),
                        "endpoint_sha256": provider.get("endpoint_sha256"),
                        "key_fingerprint": provider.get("key_fingerprint"),
                    },
                    "artifact_signature": {
                        "algorithm": (artifact.get("artifact_signature") or {}).get(
                            "algorithm"
                        ),
                        "present": bool(artifact.get("artifact_signature")),
                        "verified": signature_valid,
                    },
                    "artifact_path": candidate,
                }
        raise ValueError("provider_qualification_not_found")


__all__ = ["XRayProviderQualificationService"]
