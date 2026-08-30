"""Bounded worker orchestration for unknown AI Provider Attempt reconciliation."""

from __future__ import annotations

from datetime import datetime
from time import monotonic

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
        max_reconcile_count: int,
        max_unknown_age_seconds: int,
    ) -> dict[str, int]:
        started_at = monotonic()
        now = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                due_attempts = await AIAttemptReconcileService(session).list_due(
                    now=now,
                    limit=limit + 1,
                )
                candidates = [
                    {
                        "attempt_id": attempt.id,
                        "attempt_state_version": attempt.state_version,
                    }
                    for attempt in due_attempts[:limit]
                ]
        outcomes: dict[str, int] = {
            "due_scanned": len(candidates),
            # list_due reads one extra row, so a non-zero value is a safe
            # lower-bound signal that the configured batch was saturated.
            "due_remaining_estimate": max(0, len(due_attempts) - limit),
            "claimed": 0,
            "lookup_authorized": 0,
            "succeeded": 0,
            "failed": 0,
            "unknown": 0,
            "unsupported": 0,
            "conflicted": 0,
            "stage_pending": 0,
            "terminal_unresolved": 0,
            "terminal_preserved": 0,
            "count_limit_reached": 0,
            "age_limit_reached": 0,
        }
        for candidate in candidates:
            claim_now = datetime.utcnow()
            async with self.session_factory() as session:
                async with session.begin():
                    plan = await AIAttemptReconcileService(session).claim(
                        attempt_id=candidate["attempt_id"],
                        expected_version=candidate["attempt_state_version"],
                        now=claim_now,
                        lease_seconds=lease_seconds,
                        max_reconcile_count=max_reconcile_count,
                        max_unknown_age_seconds=max_unknown_age_seconds,
                    )
            if plan is None:
                outcomes["conflicted"] += 1
                continue
            outcomes["claimed"] += 1
            if not plan["lookup_authorized"]:
                self._record_limit_reasons(
                    outcomes=outcomes,
                    reasons=plan["limit_reasons"],
                )
                await self._finalize_unresolved(
                    plan=plan,
                    outcomes=outcomes,
                )
                continue
            outcomes["lookup_authorized"] += 1
            try:
                lookup_result = await self.attempt_lookup.lookup(attempt_plan=plan)
            except AttemptLookupError as exc:
                lookup_result = AttemptLookupResult(
                    status="unknown",
                    error_code=self._safe_error_code(exc),
                    retry_after_seconds=retry_seconds,
                )
            if lookup_result.status in {"unknown", "unsupported"}:
                resolved_at = datetime.utcnow()
                limit_reasons = AIAttemptReconcileService.limit_reasons(
                    first_unknown_at=plan["first_unknown_at"],
                    reconcile_count=plan["reconcile_count"],
                    now=resolved_at,
                    max_reconcile_count=max_reconcile_count,
                    max_unknown_age_seconds=max_unknown_age_seconds,
                )
                if limit_reasons:
                    outcomes[lookup_result.status] += 1
                    self._record_limit_reasons(
                        outcomes=outcomes,
                        reasons=limit_reasons,
                    )
                    await self._finalize_unresolved(
                        plan=plan,
                        outcomes=outcomes,
                        now=resolved_at,
                    )
                    continue
                async with self.session_factory() as session:
                    async with session.begin():
                        changed = await AIAttemptReconcileService(
                            session
                        ).reschedule_unknown(
                            attempt_id=plan["attempt_id"],
                            expected_version=plan["attempt_state_version"],
                            now=resolved_at,
                            retry_after_seconds=lookup_result.retry_after_seconds,
                            error_code=lookup_result.error_code
                            or f"provider_attempt_{lookup_result.status}",
                            max_reconcile_count=max_reconcile_count,
                            max_unknown_age_seconds=max_unknown_age_seconds,
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
        outcomes["duration_ms"] = max(0, int((monotonic() - started_at) * 1000))
        return outcomes

    async def _finalize_unresolved(
        self,
        *,
        plan: dict[str, object],
        outcomes: dict[str, int],
        now: datetime | None = None,
    ) -> None:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    finalized = await AIAttemptReconcileService(
                        session
                    ).finalize_unresolved(
                        attempt_id=str(plan["attempt_id"]),
                        now=now or datetime.utcnow(),
                    )
        except (
            AIAttemptReconcileError,
            AIRequestStateConflict,
            StageExecutionStateConflict,
        ):
            outcomes["conflicted"] += 1
            return
        outcomes[finalized["disposition"]] += 1
        if finalized["stage_outcome"] == "attempt_finalized_stage_pending":
            outcomes["stage_pending"] += 1

    @staticmethod
    def _record_limit_reasons(
        *,
        outcomes: dict[str, int],
        reasons: tuple[str, ...] | object,
    ) -> None:
        normalized = tuple(reasons) if isinstance(reasons, (list, tuple)) else ()
        if "count" in normalized:
            outcomes["count_limit_reached"] += 1
        if "age" in normalized:
            outcomes["age_limit_reached"] += 1

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        code = str(exc).strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "provider_attempt_lookup_error"
        return code


__all__ = ["AIAttemptReconcileWorker"]
