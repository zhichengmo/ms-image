"""Deterministic technical worker replay.

This module is a qualification-only state machine.  It deliberately has no
Celery, RabbitMQ, database, Provider, Prompt, or medical verdict dependency.
The production consumer must reproduce these transitions with MySQL CAS and
the StageCheckpoint lease fields; this in-memory implementation exists to
make the lifecycle contract executable before those external dependencies are
approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Callable

from .contract import InvalidWorkerMessage, validate_message
from app.core.ai.contracts import (
    ProviderNotQualifiedError,
    ProviderRequest,
    ProviderRequestError,
    classify_provider_error,
)
from app.service.xray_accuracy.ai_request_service import (
    StubAIProvider,
    validate_validation_response,
)
from app.service.xray_accuracy.prompt_service import XRayPromptRegistry


# Phase 1 replay intentionally has only technical stages.  Any future medical
# stage must be added through a reviewed contract, never accepted by a
# permissive catch-all branch.
ALLOWED_STAGE_KEYS = frozenset({"request_gate", "cancel"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "dead_letter"})


class ReplayStatus:
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    CAS_CONFLICT = "cas_conflict"
    CANCELLED = "cancelled"
    LATE_TRACE_ONLY = "late_trace_only"
    DEAD_LETTER = "dead_letter"
    LEASE_CONFLICT = "lease_conflict"
    LEASE_EXPIRED = "lease_expired"
    ORPHAN_RECOVERED = "orphan_recovered"
    RETRY_SCHEDULED = "retry_scheduled"


@dataclass
class ReplayRun:
    run_id: str
    # These bindings are populated by the trusted Run registration lookup,
    # never by an untrusted first broker message.
    tenant_id: str | None = None
    release_fingerprint: str | None = None
    trace_namespace: str | None = None
    state_version: int = 0
    execution_status: str = "queued"
    cancel_requested: bool = False
    final_count: int = 0
    trace_count: int = 0
    reconcile_count: int = 0
    lease_owner: str | None = None
    lease_expires_at: float | None = None
    heartbeat_at: float | None = None
    active_task_id: str | None = None


@dataclass
class ReplayCheckpoint:
    """Technical StageCheckpoint mirror used only by the in-memory replay."""

    run_id: str
    task_id: str
    tenant_id: str
    stage_key: str
    attempt_id: str
    expected_version: int
    status: str = "queued"
    owner_id: str | None = None
    lease_expires_at: float | None = None
    heartbeat_at: float | None = None
    late_flag: str = "no"
    error_class: str | None = None


@dataclass(frozen=True)
class ReplayModelCall:
    run_id: str
    task_id: str
    node_key: str
    prompt_key: str
    prompt_version: str
    prompt_sha256: str
    rendered_sha256: str
    schema_sha256: str
    provider_key: str
    actual_model: str
    response_sha256: str
    medical_verdict_produced: bool


@dataclass(frozen=True)
class ReplayDeadLetter:
    """Safe, structured DLQ evidence; never stores an arbitrary payload."""

    reason: str
    run_id: str | None
    task_id: str | None
    recorded_at: float


@dataclass
class ReplayState:
    """Deterministic in-memory lifecycle for stub/replay qualification only."""

    runs: dict[str, ReplayRun] = field(default_factory=dict)
    checkpoints: dict[tuple[str, str], ReplayCheckpoint] = field(default_factory=dict)
    model_calls: dict[tuple[str, str], ReplayModelCall] = field(default_factory=dict)
    prompt_registry: XRayPromptRegistry = field(default_factory=XRayPromptRegistry, repr=False)
    ai_provider: StubAIProvider = field(default_factory=StubAIProvider, repr=False)
    seen_tasks: set[tuple[str, str]] = field(default_factory=set)
    late_tasks: set[tuple[str, str]] = field(default_factory=set)
    dead_letters: list[ReplayDeadLetter] = field(default_factory=list)
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    default_lease_seconds: int = 30

    def _dead_letter(self, reason: str, event: dict[str, Any] | None = None) -> ReplayStatus:
        # Only opaque identifiers are retained.  Invalid messages may contain
        # a secret-bearing unknown field and must never be copied to the DLQ.
        run_id = event.get("run_id") if isinstance(event, dict) else None
        task_id = event.get("task_id") if isinstance(event, dict) else None
        self.dead_letters.append(
            ReplayDeadLetter(
                reason=reason,
                run_id=run_id if isinstance(run_id, str) else None,
                task_id=task_id if isinstance(task_id, str) else None,
                recorded_at=self.clock(),
            )
        )
        return ReplayStatus.DEAD_LETTER

    def register_run(
        self,
        run_id: str,
        *,
        tenant_id: str | None = None,
        release_fingerprint: str | None = None,
        trace_namespace: str | None = None,
    ) -> ReplayRun:
        """Register an immutable trusted Run binding for replay.

        The optional arguments preserve a small amount of backwards
        compatibility for local callers, but ``apply`` refuses an incomplete
        binding.  In a real consumer these values come from the tenant-scoped
        MySQL Run lookup, not from the broker payload.
        """
        run = self.runs.setdefault(run_id, ReplayRun(run_id=run_id))
        values = {
            "tenant_id": tenant_id,
            "release_fingerprint": release_fingerprint,
            "trace_namespace": trace_namespace,
        }
        for field_name, value in values.items():
            if value is None:
                continue
            existing = getattr(run, field_name)
            if existing is not None and existing != value:
                raise ValueError("run_binding_immutable")
            setattr(run, field_name, value)
        return run

    def _binding_matches(self, run: ReplayRun, event: dict[str, Any]) -> bool:
        return (
            run.tenant_id is not None
            and run.release_fingerprint == event["release_fingerprint"]
            and run.trace_namespace == event["trace_namespace"]
        )

    def _checkpoint_for(self, event: dict[str, Any]) -> ReplayCheckpoint:
        key = (event["run_id"], event["task_id"])
        checkpoint = self.checkpoints.get(key)
        if checkpoint is None:
            checkpoint = ReplayCheckpoint(
                run_id=event["run_id"],
                task_id=event["task_id"],
                tenant_id=self.runs[event["run_id"]].tenant_id or "",
                stage_key=event["stage_key"],
                attempt_id=event["task_id"],
                expected_version=event["expected_version"],
            )
            self.checkpoints[key] = checkpoint
        return checkpoint

    def _mark_late(self, event: dict[str, Any]) -> None:
        checkpoint = self._checkpoint_for(event)
        checkpoint.status = "late"
        checkpoint.late_flag = "yes"
        checkpoint.owner_id = None
        checkpoint.lease_expires_at = None
        checkpoint.heartbeat_at = None
        run = self.runs[event["run_id"]]
        run.trace_count += 1
        task_key = (event["run_id"], event["task_id"])
        self.seen_tasks.add(task_key)
        self.late_tasks.add(task_key)

    def _execute_validation_ai(self, event: dict[str, Any], run: ReplayRun) -> ReplayModelCall:
        rendered = self.prompt_registry.render(
            prompt_key="xray.request_gate.v1",
            context={
                "run_id": event["run_id"],
                "attempt_id": event["task_id"],
                "node_key": event["stage_key"],
                "release_fingerprint": event["release_fingerprint"],
                "trace_namespace": event["trace_namespace"],
                "image_count": 0,
            },
        )
        request = ProviderRequest(
            run_id=event["run_id"],
            attempt_id=event["task_id"],
            node_key=event["stage_key"],
            release_fingerprint=event["release_fingerprint"],
            prompt=rendered,
            response_schema_key=rendered.manifest.schema_key,
            requested_model=self.ai_provider.model_name,
            full_sent="not_applicable",
        )
        try:
            response = self.ai_provider.request_sync(request)
        except Exception as exc:
            raise classify_provider_error(exc) from exc
        response_schema, schema_sha256 = self.prompt_registry.response_schema(rendered.manifest.schema_key)
        validate_validation_response(
            response.output_json,
            rendered.manifest.schema_key,
            schema=response_schema,
        )
        response_json = json.dumps(
            response.output_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        call = ReplayModelCall(
            run_id=run.run_id,
            task_id=event["task_id"],
            node_key=event["stage_key"],
            prompt_key=rendered.manifest.prompt_key,
            prompt_version=rendered.manifest.version,
            prompt_sha256=rendered.manifest.prompt_sha256,
            rendered_sha256=rendered.rendered_sha256,
            schema_sha256=schema_sha256,
            provider_key=self.ai_provider.provider_key,
            actual_model=response.actual_model,
            response_sha256=hashlib.sha256(response_json.encode("utf-8")).hexdigest(),
            medical_verdict_produced=response.output_json.get("medical_verdict") is not None,
        )
        self.model_calls[(event["run_id"], event["task_id"])] = call
        return call

    def claim(
        self,
        message: dict[str, Any],
        *,
        owner_id: str,
        lease_seconds: int | None = None,
    ) -> ReplayStatus:
        """Claim one technical task without changing the Run CAS version."""
        try:
            event = validate_message(message)
        except InvalidWorkerMessage:
            return self._dead_letter("message_invalid")
        if event["stage_key"] not in ALLOWED_STAGE_KEYS:
            return self._dead_letter("stage_not_allowed", event)
        run = self.runs.get(event["run_id"])
        if run is None:
            return self._dead_letter("run_not_registered", event)
        if not self._binding_matches(run, event):
            return self._dead_letter("run_binding_mismatch", event)
        task_key = (event["run_id"], event["task_id"])
        if task_key in self.seen_tasks:
            return ReplayStatus.DUPLICATE
        checkpoint = self._checkpoint_for(event)
        if checkpoint.status in {"completed", "cancelled", "failed"}:
            return ReplayStatus.DUPLICATE
        if checkpoint.status == "late":
            return ReplayStatus.LATE_TRACE_ONLY
        if checkpoint.expected_version != event["expected_version"]:
            return ReplayStatus.CAS_CONFLICT
        now = self.clock()
        if run.lease_owner is not None:
            if run.lease_expires_at is not None and run.lease_expires_at <= now:
                return ReplayStatus.LEASE_EXPIRED
            if run.lease_owner != owner_id:
                return ReplayStatus.LEASE_CONFLICT
        # Classify terminal/cancelled work as a late observation before CAS.
        # Late results commonly carry the old expected_version; returning only
        # CAS_CONFLICT would lose the append-only trace evidence.
        if run.execution_status in TERMINAL_STATUSES or (
            run.cancel_requested and event["stage_key"] != "cancel"
        ):
            self._mark_late(event)
            return ReplayStatus.LATE_TRACE_ONLY
        if run.state_version != event["expected_version"]:
            return ReplayStatus.CAS_CONFLICT
        if run.execution_status in TERMINAL_STATUSES:
            return ReplayStatus.LATE_TRACE_ONLY
        if run.cancel_requested and event["stage_key"] != "cancel":
            return ReplayStatus.LATE_TRACE_ONLY
        run.lease_owner = owner_id
        run.active_task_id = event["task_id"]
        run.lease_expires_at = now + (lease_seconds or self.default_lease_seconds)
        run.heartbeat_at = now
        checkpoint.status = "running"
        checkpoint.owner_id = owner_id
        checkpoint.lease_expires_at = run.lease_expires_at
        checkpoint.heartbeat_at = now
        if run.execution_status == "queued":
            run.execution_status = "running"
        return ReplayStatus.APPLIED

    def heartbeat(
        self,
        run_id: str,
        *,
        owner_id: str,
        lease_seconds: int | None = None,
    ) -> ReplayStatus:
        run = self.runs.get(run_id)
        if run is None or run.lease_owner != owner_id:
            return ReplayStatus.LEASE_CONFLICT
        now = self.clock()
        if run.lease_expires_at is None or run.lease_expires_at <= now:
            return ReplayStatus.LEASE_EXPIRED
        run.heartbeat_at = now
        run.lease_expires_at = now + (lease_seconds or self.default_lease_seconds)
        if run.active_task_id:
            checkpoint = self.checkpoints.get((run_id, run.active_task_id))
            if checkpoint is not None:
                checkpoint.heartbeat_at = now
                checkpoint.lease_expires_at = run.lease_expires_at
        return ReplayStatus.APPLIED

    def reconcile_orphans(self, *, now: float | None = None) -> list[dict[str, Any]]:
        """Recover expired worker leases without publishing a result."""
        current = self.clock() if now is None else now
        recovered: list[dict[str, Any]] = []
        for run in self.runs.values():
            if run.lease_owner is None or run.lease_expires_at is None:
                continue
            if run.lease_expires_at > current:
                continue
            old_owner = run.lease_owner
            active_task_id = run.active_task_id
            run.lease_owner = None
            run.lease_expires_at = None
            run.heartbeat_at = None
            run.active_task_id = None
            if old_owner and active_task_id:
                checkpoint = self.checkpoints.get((run.run_id, active_task_id))
                if checkpoint is not None:
                    checkpoint.status = "retry"
                    checkpoint.error_class = "lease_expired"
                    checkpoint.owner_id = None
                    checkpoint.lease_expires_at = None
                    checkpoint.heartbeat_at = None
            if run.execution_status == "running":
                run.execution_status = "queued"
                run.state_version += 1
                run.reconcile_count += 1
                run.trace_count += 1
                outcome = ReplayStatus.ORPHAN_RECOVERED
            else:
                outcome = ReplayStatus.ORPHAN_RECOVERED
            recovered.append(
                {"run_id": run.run_id, "previous_owner": old_owner, "outcome": outcome}
            )
        return recovered

    def _release_lease(self, run: ReplayRun) -> None:
        run.lease_owner = None
        run.lease_expires_at = None
        run.heartbeat_at = None
        run.active_task_id = None

    def apply(
        self,
        message: dict[str, Any],
        *,
        owner_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> ReplayStatus:
        """Claim and apply one message with CAS, lease, and final-write guards."""
        try:
            event = validate_message(message)
        except InvalidWorkerMessage:
            return self._dead_letter("message_invalid")

        task_key = (event["run_id"], event["task_id"])
        if task_key in self.seen_tasks:
            return ReplayStatus.DUPLICATE
        if event["stage_key"] not in ALLOWED_STAGE_KEYS:
            return self._dead_letter("stage_not_allowed", event)
        run = self.runs.get(event["run_id"])
        if run is None:
            return self._dead_letter("run_not_registered", event)
        if not self._binding_matches(run, event):
            return self._dead_letter("run_binding_mismatch", event)
        # Classify terminal/cancelled work as a late observation before CAS.
        # Late results commonly carry the old expected_version; returning only
        # CAS_CONFLICT would lose the append-only trace evidence.
        if run.execution_status in TERMINAL_STATUSES or (
            run.cancel_requested and event["stage_key"] != "cancel"
        ):
            self._mark_late(event)
            return ReplayStatus.LATE_TRACE_ONLY
        if run.state_version != event["expected_version"]:
            # A CAS conflict is retryable and must not be treated as a
            # poisonous message/DLQ event.
            return ReplayStatus.CAS_CONFLICT

        worker = owner_id or f"replay:{event['task_id']}"
        claim_status = self.claim(event, owner_id=worker, lease_seconds=lease_seconds)
        if claim_status == ReplayStatus.LATE_TRACE_ONLY:
            # Claim correctly refuses terminal/cancelled work, but the
            # late result still produces an append-only trace observation.
            self._mark_late(event)
            self._release_lease(run)
            return ReplayStatus.LATE_TRACE_ONLY
        if claim_status != ReplayStatus.APPLIED:
            return claim_status

        if run.execution_status in TERMINAL_STATUSES:
            self._release_lease(run)
            self._mark_late(event)
            return ReplayStatus.LATE_TRACE_ONLY

        if event["stage_key"] == "cancel":
            if run.cancel_requested:
                self._release_lease(run)
                self.seen_tasks.add(task_key)
                return ReplayStatus.DUPLICATE
            run.cancel_requested = True
            # The replay models the committed cancel request followed by its
            # worker acknowledgement as one deterministic technical event.
            # Keep the terminal state explicit so late provider work can only
            # append trace evidence and never reopen or publish a result.
            run.execution_status = "cancelled"
            run.state_version += 1
            run.trace_count += 1
            checkpoint = self._checkpoint_for(event)
            checkpoint.status = "cancelled"
            checkpoint.owner_id = None
            checkpoint.lease_expires_at = None
            checkpoint.heartbeat_at = None
            self.seen_tasks.add(task_key)
            self._release_lease(run)
            return ReplayStatus.CANCELLED

        if run.cancel_requested:
            # A provider/worker result after cancellation is trace-only.  It
            # must not mutate the Run CAS version or reopen a terminal state.
            run.trace_count += 1
            self.seen_tasks.add(task_key)
            self.late_tasks.add(task_key)
            self._release_lease(run)
            return ReplayStatus.LATE_TRACE_ONLY

        if event["stage_key"] == "request_gate":
            try:
                self._execute_validation_ai(event, run)
            except ProviderRequestError as exc:
                checkpoint = self._checkpoint_for(event)
                checkpoint.status = "retry" if exc.retryable else "failed"
                checkpoint.error_class = exc.error_class
                checkpoint.owner_id = None
                checkpoint.lease_expires_at = None
                checkpoint.heartbeat_at = None
                run.trace_count += 1
                run.state_version += 1
                run.execution_status = "queued" if exc.retryable else "failed"
                self._release_lease(run)
                if exc.retryable:
                    return ReplayStatus.RETRY_SCHEDULED
                self.seen_tasks.add(task_key)
                return self._dead_letter(exc.error_class, event)
            except ProviderNotQualifiedError:
                checkpoint = self._checkpoint_for(event)
                checkpoint.status = "failed"
                checkpoint.error_class = "provider_output_contract"
                checkpoint.owner_id = None
                checkpoint.lease_expires_at = None
                checkpoint.heartbeat_at = None
                run.trace_count += 1
                run.state_version += 1
                run.execution_status = "failed"
                self.seen_tasks.add(task_key)
                self._release_lease(run)
                return self._dead_letter("provider_output_contract", event)

        # request_gate is the only technical final writer in this replay.
        # A second final writer is rejected by the terminal guard above and
        # cannot increment state_version/final_count.
        run.state_version += 1
        run.trace_count += 1
        run.final_count += 1
        run.execution_status = "completed"
        checkpoint = self._checkpoint_for(event)
        checkpoint.status = "completed"
        checkpoint.owner_id = None
        checkpoint.lease_expires_at = None
        checkpoint.heartbeat_at = None
        self.seen_tasks.add(task_key)
        self._release_lease(run)
        return ReplayStatus.APPLIED


@dataclass
class ReplayOutboxEvent:
    """Safe relay bookkeeping for one already-committed Outbox event."""

    event_id: str
    tenant_id: str
    message: dict[str, Any]
    publish_status: str = "pending"
    attempt_count: int = 0
    next_retry_at: float | None = None
    published_at: float | None = None
    last_error: str | None = None
    relay_owner_id: str | None = None
    relay_lease_expires_at: float | None = None
    event_type: str = "execute"
    aggregate_type: str = "xray_run"
    aggregate_id: str = ""
    message_payload_hash: str = ""
    message_whitelist_version: str = "xray-message.v1"


class ReplayOutboxRelay:
    """No-Broker Outbox relay qualification stub.

    ``publish`` accepts a deterministic outcome supplied by the replay
    harness.  It never opens a network connection and never treats this
    in-memory state as the production source of truth.
    """

    OUTCOMES = frozenset({"published", "retry", "dead_letter"})
    SAFE_ERRORS = frozenset({"transport_error", "timeout", "broker_nack", "publish_failed"})
    EVENT_TYPES = frozenset({"execute", "reconcile", "review", "delivery"})
    MESSAGE_WHITELIST_VERSION = "xray-message.v1"

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        retry_delay_seconds: int = 5,
        max_attempts: int = 3,
        relay_lease_seconds: int = 30,
    ):
        self.clock = clock
        self.retry_delay_seconds = retry_delay_seconds
        self.max_attempts = max_attempts
        self.relay_lease_seconds = relay_lease_seconds
        self.events: dict[str, ReplayOutboxEvent] = {}
        self.dead_letters: list[ReplayDeadLetter] = []

    @staticmethod
    def _message_hash(message: dict[str, Any]) -> str:
        import hashlib
        import json

        encoded = json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def enqueue(self, event: dict[str, Any]) -> str:
        """Validate and remember only the relay-safe fields of an Outbox row."""
        try:
            message = validate_message(event.get("message_json"))
        except (InvalidWorkerMessage, AttributeError):
            self.dead_letters.append(
                ReplayDeadLetter("outbox_message_invalid", None, None, self.clock())
            )
            return ReplayStatus.DEAD_LETTER
        event_id = event.get("event_id")
        task_id = event.get("task_id")
        run_id = event.get("run_id")
        tenant_id = event.get("tenant_id")
        if not all(isinstance(value, str) and value.strip() for value in (event_id, task_id, run_id, tenant_id)):
            self.dead_letters.append(
                ReplayDeadLetter("outbox_identity_invalid", run_id if isinstance(run_id, str) else None, task_id if isinstance(task_id, str) else None, self.clock())
            )
            return ReplayStatus.DEAD_LETTER
        if event_id == task_id or message["task_id"] != task_id or message["run_id"] != run_id:
            self.dead_letters.append(ReplayDeadLetter("outbox_identity_mismatch", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        if (
            event.get("id") != event_id
            or event.get("aggregate_type") != "xray_run"
            or event.get("aggregate_id") != run_id
        ):
            self.dead_letters.append(ReplayDeadLetter("outbox_aggregate_mismatch", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        if event.get("message_whitelist_version") != self.MESSAGE_WHITELIST_VERSION:
            self.dead_letters.append(ReplayDeadLetter("outbox_whitelist_version_invalid", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        if event.get("event_type") not in self.EVENT_TYPES:
            self.dead_letters.append(ReplayDeadLetter("outbox_event_type_invalid", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        for field_name in ("stage_key", "release_fingerprint", "expected_version", "trace_namespace"):
            if event.get(field_name) != message[field_name]:
                self.dead_letters.append(ReplayDeadLetter("outbox_field_mismatch", run_id, task_id, self.clock()))
                return ReplayStatus.DEAD_LETTER
        if event.get("message_payload_hash") != self._message_hash(message):
            self.dead_letters.append(ReplayDeadLetter("outbox_hash_mismatch", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        existing = self.events.get(event_id)
        if existing is not None:
            if (
                existing.message == message
                and existing.tenant_id == tenant_id
                and existing.event_type == event["event_type"]
                and existing.aggregate_type == event["aggregate_type"]
                and existing.aggregate_id == event["aggregate_id"]
                and existing.message_payload_hash == event["message_payload_hash"]
                and existing.message_whitelist_version == event["message_whitelist_version"]
            ):
                return ReplayStatus.DUPLICATE
            self.dead_letters.append(ReplayDeadLetter("outbox_event_conflict", run_id, task_id, self.clock()))
            return ReplayStatus.DEAD_LETTER
        self.events[event_id] = ReplayOutboxEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            message=message,
            event_type=event["event_type"],
            aggregate_type=event["aggregate_type"],
            aggregate_id=event["aggregate_id"],
            message_payload_hash=event["message_payload_hash"],
            message_whitelist_version=event["message_whitelist_version"],
        )
        return ReplayStatus.APPLIED

    def publish(
        self,
        event_id: str,
        *,
        outcome: str,
        error: str | None = None,
        owner_id: str | None = None,
    ) -> str:
        event = self.events.get(event_id)
        if event is None:
            return ReplayStatus.DEAD_LETTER
        owner = owner_id or f"replay-relay:{event_id}"
        now = self.clock()
        if event.publish_status == "published":
            return ReplayStatus.DUPLICATE
        if event.publish_status == "dead_letter":
            return ReplayStatus.DEAD_LETTER
        if (
            event.publish_status == "retry"
            and event.next_retry_at is not None
            and event.next_retry_at > now
        ):
            return ReplayStatus.RETRY_SCHEDULED
        if event.publish_status == "publishing":
            if event.relay_lease_expires_at is not None and event.relay_lease_expires_at <= now:
                return ReplayStatus.LEASE_EXPIRED
            if event.relay_owner_id != owner:
                return ReplayStatus.LEASE_CONFLICT
        else:
            event.relay_owner_id = owner
            event.relay_lease_expires_at = now + self.relay_lease_seconds
        if outcome not in self.OUTCOMES:
            outcome = "dead_letter"
        event.publish_status = "publishing"
        event.attempt_count += 1
        if outcome == "published":
            event.publish_status = "published"
            event.published_at = now
            event.next_retry_at = None
            event.last_error = None
            event.relay_owner_id = None
            event.relay_lease_expires_at = None
            return ReplayStatus.APPLIED
        if outcome == "retry":
            if event.attempt_count >= self.max_attempts:
                outcome = "dead_letter"
            else:
                event.publish_status = "retry"
                event.next_retry_at = now + self.retry_delay_seconds
                event.last_error = error if error in self.SAFE_ERRORS else "publish_failed"
                event.relay_owner_id = None
                event.relay_lease_expires_at = None
                return ReplayStatus.RETRY_SCHEDULED
        event.publish_status = "dead_letter"
        event.last_error = error if error in self.SAFE_ERRORS else "publish_failed"
        event.relay_owner_id = None
        event.relay_lease_expires_at = None
        self.dead_letters.append(
            ReplayDeadLetter("outbox_publish_dead_letter", event.message["run_id"], event.message["task_id"], self.clock())
        )
        return ReplayStatus.DEAD_LETTER

    def recover_expired(self, *, now: float | None = None) -> dict[str, int]:
        current = self.clock() if now is None else now
        recovered = {"retry": 0, "dead_letter": 0}
        for event in self.events.values():
            if (
                event.publish_status != "publishing"
                or event.relay_owner_id is None
                or event.relay_lease_expires_at is None
                or event.relay_lease_expires_at > current
            ):
                continue
            next_status = "dead_letter" if event.attempt_count >= self.max_attempts else "retry"
            event.publish_status = next_status
            event.next_retry_at = None if next_status == "dead_letter" else current
            event.last_error = "relay_lease_expired"
            event.relay_owner_id = None
            event.relay_lease_expires_at = None
            recovered[next_status] += 1
        return recovered

    def heartbeat(
        self,
        event_id: str,
        *,
        owner_id: str,
        lease_seconds: int | None = None,
    ) -> str:
        event = self.events.get(event_id)
        if event is None:
            return ReplayStatus.DEAD_LETTER
        now = self.clock()
        if event.publish_status != "publishing" or event.relay_owner_id != owner_id:
            return ReplayStatus.LEASE_CONFLICT
        if event.relay_lease_expires_at is None or event.relay_lease_expires_at <= now:
            return ReplayStatus.LEASE_EXPIRED
        event.relay_lease_expires_at = now + (lease_seconds or self.relay_lease_seconds)
        return ReplayStatus.APPLIED
