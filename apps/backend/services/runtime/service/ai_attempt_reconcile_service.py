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


PROVIDER_RESULT_UNRESOLVED = "provider_result_unresolved"


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
        max_reconcile_count: int,
        max_unknown_age_seconds: int,
    ) -> dict[str, Any] | None:
        if lease_seconds < 30 or lease_seconds > 900:
            raise AIAttemptReconcileError("ai_attempt_reconcile_lease_invalid")
        self._validate_bounds(
            max_reconcile_count=max_reconcile_count,
            max_unknown_age_seconds=max_unknown_age_seconds,
        )
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        unknown_cutoff = now - timedelta(seconds=max_unknown_age_seconds)
        claimed = await self.attempt_dal.claim_reconcile_candidate(
            attempt_id=attempt_id,
            expected_version=expected_version,
            now=now,
            lease_expires_at=lease_expires_at,
            unknown_cutoff=unknown_cutoff,
            max_reconcile_count=max_reconcile_count,
        )
        lookup_authorized = claimed is not None
        if claimed is None:
            claimed = await self.attempt_dal.claim_exhausted_reconcile_candidate(
                attempt_id=attempt_id,
                expected_version=expected_version,
                now=now,
                lease_expires_at=lease_expires_at,
                unknown_cutoff=unknown_cutoff,
                max_reconcile_count=max_reconcile_count,
            )
            if claimed is None:
                return None
        limit_reasons = self.limit_reasons(
            first_unknown_at=claimed.first_unknown_at,
            reconcile_count=claimed.reconcile_count,
            now=now,
            max_reconcile_count=max_reconcile_count,
            max_unknown_age_seconds=max_unknown_age_seconds,
        )
        if not lookup_authorized and not limit_reasons:
            raise AIAttemptReconcileError("ai_attempt_reconcile_limit_state_invalid")
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
            "first_unknown_at": claimed.first_unknown_at,
            "reconcile_count": claimed.reconcile_count,
            "lookup_authorized": lookup_authorized,
            "limit_reasons": limit_reasons if not lookup_authorized else (),
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
        max_reconcile_count: int,
        max_unknown_age_seconds: int,
    ) -> bool:
        self._validate_bounds(
            max_reconcile_count=max_reconcile_count,
            max_unknown_age_seconds=max_unknown_age_seconds,
        )
        retry_seconds = max(30, min(86_400, int(retry_after_seconds)))
        updated = await self.attempt_dal.reschedule_reconcile_candidate(
            attempt_id=attempt_id,
            expected_version=expected_version,
            next_reconcile_at=now + timedelta(seconds=retry_seconds),
            unknown_cutoff=now - timedelta(seconds=max_unknown_age_seconds),
            max_reconcile_count=max_reconcile_count,
            error_code=self._safe_error_code(error_code),
        )
        return updated is not None

    async def finalize_unresolved(
        self,
        *,
        attempt_id: str,
        now: datetime,
    ) -> dict[str, str]:
        """Close a bounded-out unknown without issuing another Provider request."""

        call_result = await self.ai_request_service.finalize_attempt_failure(
            attempt_id=attempt_id,
            error_code=PROVIDER_RESULT_UNRESOLVED,
            unknown=False,
        )
        disposition = (
            "terminal_unresolved"
            if call_result.get("attempt_status") == "failed"
            and call_result.get("status") == "failed"
            and call_result.get("error_code") == PROVIDER_RESULT_UNRESOLVED
            else "terminal_preserved"
        )
        return {
            "disposition": disposition,
            "stage_outcome": await self._apply_call_result_to_stage(
                attempt_id=attempt_id,
                call_result=call_result,
                now=now,
            ),
        }

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

        return await self._apply_call_result_to_stage(
            attempt_id=attempt_id,
            call_result=call_result,
            now=now,
        )

    async def _apply_call_result_to_stage(
        self,
        *,
        attempt_id: str,
        call_result: dict[str, Any],
        now: datetime,
    ) -> str:
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
    def _validate_bounds(
        *,
        max_reconcile_count: int,
        max_unknown_age_seconds: int,
    ) -> None:
        if (
            not isinstance(max_reconcile_count, int)
            or isinstance(max_reconcile_count, bool)
            or max_reconcile_count < 1
            or max_reconcile_count > 100
        ):
            raise AIAttemptReconcileError("ai_attempt_reconcile_max_count_invalid")
        if (
            not isinstance(max_unknown_age_seconds, int)
            or isinstance(max_unknown_age_seconds, bool)
            or max_unknown_age_seconds < 300
            or max_unknown_age_seconds > 604_800
        ):
            raise AIAttemptReconcileError("ai_attempt_reconcile_max_age_invalid")

    @classmethod
    def limit_reasons(
        cls,
        *,
        first_unknown_at: datetime | None,
        reconcile_count: int,
        now: datetime,
        max_reconcile_count: int,
        max_unknown_age_seconds: int,
    ) -> tuple[str, ...]:
        cls._validate_bounds(
            max_reconcile_count=max_reconcile_count,
            max_unknown_age_seconds=max_unknown_age_seconds,
        )
        if (
            not isinstance(reconcile_count, int)
            or isinstance(reconcile_count, bool)
            or reconcile_count < 0
        ):
            raise AIAttemptReconcileError("ai_attempt_reconcile_count_invalid")
        reasons: list[str] = []
        if reconcile_count >= max_reconcile_count:
            reasons.append("count")
        if (
            first_unknown_at is not None
            and first_unknown_at + timedelta(seconds=max_unknown_age_seconds) <= now
        ):
            reasons.append("age")
        return tuple(reasons)

    @staticmethod
    def _safe_error_code(value: str) -> str:
        code = str(value or "").strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "provider_reconcile_unknown"
        return code


__all__ = [
    "AIAttemptReconcileError",
    "AIAttemptReconcileService",
    "PROVIDER_RESULT_UNRESOLVED",
]
