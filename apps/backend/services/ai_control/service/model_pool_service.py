from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.async_db import session_factory
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.crud.ai_api_connection import AIAPIConnectionDal
from apps.backend.crud.ai_model_pool import AIModelPoolDal
from apps.backend.models.ai_model_pool import AIModelPool
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_control import (
    ModelPoolCreate,
    ModelPoolResponse,
    ModelPoolUpdate,
    PageResult,
    RetireCommandRequest,
    StateCommandRequest,
)
from apps.backend.services.ai_control.service.control_audit_service import (
    AIControlAuditService,
)
from apps.backend.services.ai_control.service.errors import (
    AIControlNotFoundError,
    AIControlStateConflictError,
    AIControlValidationError,
)


class ModelPoolService:
    RESOURCE_TYPE = "model_pool"

    def __init__(self, db: AsyncSession):
        self.dal = AIModelPoolDal(db)
        self.connection_dal = AIAPIConnectionDal(db)
        self.audit = AIControlAuditService(db)

    @staticmethod
    def _response(value: AIModelPool) -> ModelPoolResponse:
        return ModelPoolResponse.model_validate(value)

    @staticmethod
    def _pool_sha(
        *,
        pool_key: str,
        version: str,
        execution_mode: str,
        winner_policy: str,
        lane_count: int,
        lane_plan_json: dict[str, Any],
    ) -> str:
        return sha256_json(
            {
                "pool_key": pool_key,
                "version": version,
                "execution_mode": execution_mode,
                "winner_policy": winner_policy,
                "lane_count": lane_count,
                "lane_plan_json": lane_plan_json,
            }
        )

    @staticmethod
    def _validate_single_lane_values(
        *,
        execution_mode: str,
        winner_policy: str,
        lane_count: int,
        lane_plan: dict[str, Any],
    ) -> None:
        if execution_mode != "single" or winner_policy != "single" or lane_count != 1:
            raise AIControlValidationError("ai_model_pool_single_lane_required")
        lanes = lane_plan.get("lanes")
        if not isinstance(lanes, list) or len(lanes) != 1:
            raise AIControlValidationError("ai_model_pool_lane_count_invalid")
        lane = lanes[0]
        if not isinstance(lane, dict) or lane.get("max_attempts") != 1:
            raise AIControlValidationError("ai_model_pool_max_attempts_invalid")

    async def _validate_connection_bindings(self, lane_plan: dict[str, Any]) -> None:
        lanes = lane_plan.get("lanes")
        if not isinstance(lanes, list):
            raise AIControlValidationError("ai_model_pool_lane_contract_invalid")
        for lane in lanes:
            if not isinstance(lane, dict):
                raise AIControlValidationError("ai_model_pool_lane_contract_invalid")
            connection = await self.connection_dal.get_by_id(lane["connection_id"])
            if connection is None:
                raise AIControlValidationError("ai_model_pool_connection_not_found")
            if connection.status != "validated":
                raise AIControlValidationError("ai_model_pool_connection_not_validated")
            if connection.connection_sha256 != lane["connection_sha256"]:
                raise AIControlValidationError("ai_model_pool_connection_sha_mismatch")

    async def _replay_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIModelPool | None:
        """Fast-path replay from this request transaction."""
        audit = await self.audit.find_command(
            request_id=request_id,
            resource_type=self.RESOURCE_TYPE,
            action_type=action_type,
        )
        if audit is None:
            return None
        if audit.result_type != "succeeded":
            raise AIControlValidationError(
                audit.error_code or "ai_model_pool_command_rejected"
            )
        item = await self.dal.get_by_id(audit.resource_id)
        if item is None:
            raise AIControlStateConflictError("ai_control_audit_resource_missing")
        return item

    async def _replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIModelPool | None:
        """Read a previously committed command in a fresh transaction snapshot.

        A duplicate command can lose an insert/CAS/audit uniqueness race while
        its original request transaction cannot yet observe the first commit.
        Replaying through a separate session preserves the Audit idempotency
        contract without reapplying the business mutation.
        """
        async with session_factory() as replay_db:
            replay_audit = AIControlAuditService(replay_db)
            audit = await replay_audit.find_command(
                request_id=request_id,
                resource_type=self.RESOURCE_TYPE,
                action_type=action_type,
            )
            if audit is None:
                return None
            if audit.result_type != "succeeded":
                raise AIControlValidationError(
                    audit.error_code or "ai_model_pool_command_rejected"
                )
            item = await AIModelPoolDal(replay_db).get_by_id(audit.resource_id)
            if item is None:
                raise AIControlStateConflictError("ai_control_audit_resource_missing")
            return item

    async def _rollback_and_replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIModelPool | None:
        """Undo local business changes before returning another command's replay."""
        await self.dal.db.rollback()
        return await self._replay_committed_or_none(
            request_id=request_id, action_type=action_type
        )

    async def _has_committed_rejected_validation(
        self, *, request_id: str, resource_id: str
    ) -> bool:
        """Check a duplicate rejected validate command in a fresh snapshot."""
        async with session_factory() as replay_db:
            audit = await AIControlAuditService(replay_db).find_command(
                request_id=request_id,
                resource_type=self.RESOURCE_TYPE,
                action_type="validate",
            )
            return (
                audit is not None
                and audit.result_type == "rejected"
                and audit.resource_id == resource_id
            )

    async def _mark_rejected_validation(
        self,
        *,
        item: AIModelPool,
        payload: StateCommandRequest,
        actor: ControlPlaneContext,
        error_code: str,
    ) -> None:
        """Persist one rejected validate fact even when the endpoint rolls back.

        A duplicate command may lose the audit unique-key race after the first
        request commits.  The fresh-session replay check intentionally happens
        only after the isolated transaction closes, so MySQL's request snapshot
        cannot hide the durable first audit row.
        """
        stable_error_code = error_code[:80]
        replay_required = False
        async with session_factory.begin() as rejected_db:
            rejected_dal = AIModelPoolDal(rejected_db)
            rejected_audit = AIControlAuditService(rejected_db)
            current = await rejected_dal.get_by_id(item.id)
            if (
                current is None
                or current.status != "draft"
                or current.state_version != payload.expected_state_version
                or current.pool_sha256 != item.pool_sha256
            ):
                replay_required = True
            else:
                audit = await rejected_audit.append_rejected(
                    resource_type=self.RESOURCE_TYPE,
                    resource_id=item.id,
                    resource_key=item.pool_key,
                    action_type="validate",
                    request_id=payload.request_id,
                    actor=actor,
                    before_sha256=item.pool_sha256,
                    error_code=stable_error_code,
                )
                if audit is not None:
                    return
                replay_required = True
        if replay_required and await self._has_committed_rejected_validation(
            request_id=payload.request_id,
            resource_id=item.id,
        ):
            return
        raise AIControlStateConflictError("ai_model_pool_validate_conflict")

    async def create(
        self, *, payload: ModelPoolCreate, actor: ControlPlaneContext
    ) -> ModelPoolResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="create"
        )
        if replay is not None:
            return self._response(replay)
        if await self.dal.get_by_key_version(payload.pool_key, payload.version):
            raise AIControlStateConflictError("ai_model_pool_key_version_exists")
        lane_plan = payload.lane_plan_json.model_dump(mode="json")
        self._validate_single_lane_values(
            execution_mode=payload.execution_mode,
            winner_policy=payload.winner_policy,
            lane_count=payload.lane_count,
            lane_plan=lane_plan,
        )
        item = await self.dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "pool_key": payload.pool_key,
                "version": payload.version,
                "name": payload.name,
                "description": payload.description,
                "execution_mode": payload.execution_mode,
                "winner_policy": payload.winner_policy,
                "lane_count": payload.lane_count,
                "lane_plan_json": lane_plan,
                "pool_sha256": self._pool_sha(
                    pool_key=payload.pool_key,
                    version=payload.version,
                    execution_mode=payload.execution_mode,
                    winner_policy=payload.winner_policy,
                    lane_count=payload.lane_count,
                    lane_plan_json=lane_plan,
                ),
                "status": "draft",
                "state_version": 0,
                "created_by_id": actor.subject_id,
                "updated_by_id": actor.subject_id,
            }
        )
        if item is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_model_pool_create_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=item.id,
            resource_key=item.pool_key,
            action_type="create",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=None,
            after_sha256=item.pool_sha256,
            changed_fields=[
                "pool_key",
                "version",
                "name",
                "description",
                "execution_mode",
                "winner_policy",
                "lane_count",
                "lane_plan_json",
                "pool_sha256",
                "status",
            ],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(item)

    async def update(
        self, *, payload: ModelPoolUpdate, actor: ControlPlaneContext
    ) -> ModelPoolResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="update"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_model_pool_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError("ai_model_pool_draft_required")
        lane_plan = payload.lane_plan_json.model_dump(mode="json")
        self._validate_single_lane_values(
            execution_mode=payload.execution_mode,
            winner_policy=payload.winner_policy,
            lane_count=payload.lane_count,
            lane_plan=lane_plan,
        )
        updated = await self.dal.cas_update(
            pool_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "name": payload.name,
                "description": payload.description,
                "execution_mode": payload.execution_mode,
                "winner_policy": payload.winner_policy,
                "lane_count": payload.lane_count,
                "lane_plan_json": lane_plan,
                "pool_sha256": self._pool_sha(
                    pool_key=item.pool_key,
                    version=item.version,
                    execution_mode=payload.execution_mode,
                    winner_policy=payload.winner_policy,
                    lane_count=payload.lane_count,
                    lane_plan_json=lane_plan,
                ),
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="update"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_model_pool_update_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.pool_key,
            action_type="update",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.pool_sha256,
            after_sha256=updated.pool_sha256,
            changed_fields=[
                "name",
                "description",
                "execution_mode",
                "winner_policy",
                "lane_count",
                "lane_plan_json",
                "pool_sha256",
            ],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="update"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def validate(
        self, *, payload: StateCommandRequest, actor: ControlPlaneContext
    ) -> ModelPoolResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="validate"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_model_pool_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError("ai_model_pool_validate_draft_required")
        try:
            self._validate_single_lane_values(
                execution_mode=item.execution_mode,
                winner_policy=item.winner_policy,
                lane_count=item.lane_count,
                lane_plan=item.lane_plan_json,
            )
            await self._validate_connection_bindings(item.lane_plan_json)
            expected_sha = self._pool_sha(
                pool_key=item.pool_key,
                version=item.version,
                execution_mode=item.execution_mode,
                winner_policy=item.winner_policy,
                lane_count=item.lane_count,
                lane_plan_json=item.lane_plan_json,
            )
            if expected_sha != item.pool_sha256:
                raise AIControlValidationError("ai_model_pool_sha_mismatch")
        except AIControlValidationError as exc:
            await self._mark_rejected_validation(
                item=item,
                payload=payload,
                actor=actor,
                error_code=str(exc),
            )
            raise
        updated = await self.dal.cas_update(
            pool_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "status": "validated",
                "validated_at": datetime.utcnow(),
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="validate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_model_pool_validate_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.pool_key,
            action_type="validate",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.pool_sha256,
            after_sha256=updated.pool_sha256,
            changed_fields=["status", "validated_at"],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="validate"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def retire(
        self, *, payload: RetireCommandRequest, actor: ControlPlaneContext
    ) -> ModelPoolResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="retire"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_model_pool_not_found")
        if item.status not in {"draft", "validated"}:
            raise AIControlStateConflictError("ai_model_pool_retire_state_invalid")
        updated = await self.dal.cas_update(
            pool_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "status": "retired",
                "retired_at": datetime.utcnow(),
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="retire"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_model_pool_retire_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.pool_key,
            action_type="retire",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.pool_sha256,
            after_sha256=updated.pool_sha256,
            changed_fields=["status", "retired_at"],
            reason=payload.reason,
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="retire"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(updated)

    async def detail(self, *, pool_id: str) -> ModelPoolResponse:
        item = await self.dal.get_by_id(pool_id)
        if item is None:
            raise AIControlNotFoundError("ai_model_pool_not_found")
        return self._response(item)

    async def page(
        self, *, page: int, limit: int, execution_mode: str | None, status: str | None
    ) -> PageResult[ModelPoolResponse]:
        items, total = await self.dal.page(
            page=page, limit=limit, execution_mode=execution_mode, status=status
        )
        return PageResult(
            data=[self._response(item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )


__all__ = ["ModelPoolService"]
