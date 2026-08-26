"""Database-side state transitions for unknown AI Attempt reconciliation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
from apps.backend.crud.ai_call import AICallDal
from apps.backend.crud.ai_call_attempt import AICallAttemptDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.service.imaging_execution_service import (
    ImagingExecutionService,
)


class AIAttemptReconcileError(ValueError):
    """An unknown Attempt cannot be safely claimed or converged."""


class AIAttemptReconcileService:
    """Use DalBase-backed CAS operations; Provider lookup stays outside this service."""

    def __init__(self, db: AsyncSession):
        self.attempt_dal = AICallAttemptDal(db)
        self.call_dal = AICallDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.ai_request_service = AIRequestService(db)
        self.imaging_execution_service = ImagingExecutionService(db)

    async def list_due(self, *, now: datetime, limit: int) -> list[Any]:
        return await self.attempt_dal.page_reconcile_candidates(now=now, limit=limit)

    async def claim(
        self,
        *,
        attempt_id: str,
        expected_version: int,
        now: datetime,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        if lease_seconds < 30 or lease_seconds > 900:
            raise AIAttemptReconcileError("ai_attempt_reconcile_lease_invalid")
        claimed = await self.attempt_dal.claim_reconcile_candidate(
            attempt_id=attempt_id,
            expected_version=expected_version,
            now=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        if claimed is None:
            return None
        call = await self.call_dal.get_by_id(claimed.ai_call_id)
        if call is None:
            raise AIAttemptReconcileError("ai_call_not_found")
        stage = await self.stage_dal.get_by_id(call.stage_checkpoint_id)
        if (
            stage is not None
            and stage.status == "running"
            and stage.lease_owner_id
            and stage.lease_expires_at is not None
            and stage.lease_expires_at > now
        ):
            await self.stage_dal.heartbeat(
                checkpoint_id=stage.id,
                owner_id=stage.lease_owner_id,
                lease_generation=stage.lease_generation,
                now=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        return {
            "attempt_id": claimed.id,
            "attempt_state_version": claimed.state_version,
            "logical_call_id": call.id,
            "stage_checkpoint_id": call.stage_checkpoint_id,
            "provider_idempotency_key": claimed.provider_idempotency_key,
            "provider_request_id": claimed.provider_request_id,
            "connection_id": claimed.connection_id,
            "connection_sha256": claimed.connection_sha256,
            "provider_type": claimed.provider_type,
            "api_format": claimed.api_format,
            "requested_model": claimed.requested_model,
            "trace_id": claimed.trace_id,
            "request_id": claimed.request_id,
        }

    async def reschedule_unknown(
        self,
        *,
        attempt_id: str,
        expected_version: int,
        now: datetime,
        retry_after_seconds: int,
        error_code: str,
    ) -> bool:
        retry_seconds = max(30, min(86_400, int(retry_after_seconds)))
        updated = await self.attempt_dal.cas_update(
            attempt_id=attempt_id,
            expected_version=expected_version,
            values={
                "status": "unknown",
                "error_code": self._safe_error_code(error_code),
                "next_reconcile_at": now + timedelta(seconds=retry_seconds),
            },
        )
        return updated is not None

    async def apply_lookup_result(
        self,
        *,
        attempt_id: str,
        result: AttemptLookupResult,
        now: datetime,
    ) -> str:
        if result.status == "succeeded":
            network_result = dict(result.network_result or {})
            required = {
                "execution",
                "image_receipt",
                "image_manifest_sha256",
                "image_count_sent",
            }
            if not required.issubset(network_result):
                raise AIAttemptReconcileError("ai_attempt_lookup_result_invalid")
            call_result = await self.ai_request_service.finalize_attempt(
                attempt_id=attempt_id,
                execution=network_result["execution"],
                image_receipt=network_result["image_receipt"],
                image_manifest_sha256=network_result["image_manifest_sha256"],
                image_count_sent=network_result["image_count_sent"],
            )
        elif result.status == "failed":
            call_result = await self.ai_request_service.finalize_attempt_failure(
                attempt_id=attempt_id,
                error_code=self._safe_error_code(result.error_code or "provider_failed"),
                unknown=False,
            )
        else:
            raise AIAttemptReconcileError("ai_attempt_lookup_result_not_terminal")

        attempt = await self.attempt_dal.get_by_id(attempt_id)
        if attempt is None:
            raise AIAttemptReconcileError("ai_call_attempt_not_found")
        call = await self.call_dal.get_by_id(attempt.ai_call_id)
        if call is None:
            raise AIAttemptReconcileError("ai_call_not_found")
        stage = await self.stage_dal.get_by_id(call.stage_checkpoint_id)
        if (
            stage is None
            or stage.status != "running"
            or not stage.lease_owner_id
            or stage.lease_expires_at is None
            or stage.lease_expires_at <= now
        ):
            return "attempt_finalized_stage_pending"
        await self.imaging_execution_service.finalize_ai_stage(
            stage_checkpoint_id=stage.id,
            owner_id=stage.lease_owner_id,
            call_result=call_result,
        )
        return "stage_restored"

    @staticmethod
    def _safe_error_code(value: str) -> str:
        code = str(value or "").strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "provider_reconcile_unknown"
        return code


__all__ = ["AIAttemptReconcileError", "AIAttemptReconcileService"]
