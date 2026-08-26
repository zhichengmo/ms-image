"""Bounded worker orchestration for unknown AI Provider Attempt reconciliation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.backend.core.ai.gateway.attempt_lookup import (
    AttemptLookupError,
    AttemptLookupResult,
    ProviderAttemptLookup,
    UnsupportedProviderAttemptLookup,
)
from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
    AIAttemptReconcileError,
    AIAttemptReconcileService,
)
from apps.backend.services.runtime.service.ai_request_service import AIRequestStateConflict
from apps.backend.services.runtime.service.imaging_execution_service import (
    StageExecutionStateConflict,
)


class AIAttemptReconcileWorker:
    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession],
        attempt_lookup: ProviderAttemptLookup | None = None,
    ) -> None:
        self.session_factory = session_factory_
        self.attempt_lookup = attempt_lookup or UnsupportedProviderAttemptLookup()

    async def run_once(
        self,
        *,
        limit: int,
        lease_seconds: int,
        retry_seconds: int,
    ) -> dict[str, int]:
        now = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                candidates = await AIAttemptReconcileService(session).list_due(
                    now=now,
                    limit=limit,
                )
        outcomes: dict[str, int] = {
            "claimed": 0,
            "succeeded": 0,
            "failed": 0,
            "unknown": 0,
            "unsupported": 0,
            "conflicted": 0,
            "stage_pending": 0,
        }
        for candidate in candidates:
            claim_now = datetime.utcnow()
            async with self.session_factory() as session:
                async with session.begin():
                    plan = await AIAttemptReconcileService(session).claim(
                        attempt_id=candidate.id,
                        expected_version=candidate.state_version,
                        now=claim_now,
                        lease_seconds=lease_seconds,
                    )
            if plan is None:
                outcomes["conflicted"] += 1
                continue
            outcomes["claimed"] += 1
            try:
                lookup_result = await self.attempt_lookup.lookup(attempt_plan=plan)
            except AttemptLookupError as exc:
                lookup_result = AttemptLookupResult(
                    status="unknown",
                    error_code=self._safe_error_code(exc),
                    retry_after_seconds=retry_seconds,
                )
            if lookup_result.status in {"unknown", "unsupported"}:
                async with self.session_factory() as session:
                    async with session.begin():
                        changed = await AIAttemptReconcileService(
                            session
                        ).reschedule_unknown(
                            attempt_id=plan["attempt_id"],
                            expected_version=plan["attempt_state_version"],
                            now=datetime.utcnow(),
                            retry_after_seconds=lookup_result.retry_after_seconds,
                            error_code=lookup_result.error_code
                            or f"provider_attempt_{lookup_result.status}",
                        )
                outcomes[lookup_result.status if changed else "conflicted"] += 1
                continue
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        applied = await AIAttemptReconcileService(
                            session
                        ).apply_lookup_result(
                            attempt_id=plan["attempt_id"],
                            result=lookup_result,
                            now=datetime.utcnow(),
                        )
            except (
                AIAttemptReconcileError,
                AIRequestStateConflict,
                StageExecutionStateConflict,
            ):
                outcomes["conflicted"] += 1
                continue
            outcomes[lookup_result.status] += 1
            if applied == "attempt_finalized_stage_pending":
                outcomes["stage_pending"] += 1
        return outcomes

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        code = str(exc).strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "provider_attempt_lookup_error"
        return code


__all__ = ["AIAttemptReconcileWorker"]
