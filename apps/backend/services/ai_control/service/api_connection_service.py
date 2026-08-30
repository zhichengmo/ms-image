from __future__ import annotations

from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.async_db import session_factory
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.ai.connection_contract import (
    ConnectionContractError,
    canonical_connection_metadata_sha256,
    canonicalize_connection_base_url,
)
from apps.backend.crud.ai_api_connection import AIAPIConnectionDal
from apps.backend.models.ai_api_connection import AIAPIConnection
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_control import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionUpdate,
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


class APIConnectionService:
    RESOURCE_TYPE = "connection"
    # Physical-column compatibility only. The current schema predates the
    # ms-ai-platform runtime contract and keeps this NOT NULL column until a
    # separately authorized migration removes it. It is never accepted from an
    # API caller, hashed, returned, audited, frozen, or consumed by the Worker.
    _LEGACY_SECRET_REF_PLACEHOLDER = ""

    def __init__(self, db: AsyncSession):
        self.dal = AIAPIConnectionDal(db)
        self.audit = AIControlAuditService(db)

    @staticmethod
    def _canonical_base_url(base_url: str) -> str:
        try:
            return canonicalize_connection_base_url(base_url)
        except ConnectionContractError as exc:
            raise AIControlValidationError(str(exc)) from exc

    @staticmethod
    def _connection_sha(values: dict[str, Any]) -> str:
        try:
            return canonical_connection_metadata_sha256(values)
        except ConnectionContractError as exc:
            raise AIControlValidationError(str(exc)) from exc

    @staticmethod
    def _response(value: AIAPIConnection) -> ConnectionResponse:
        return ConnectionResponse(
            id=value.id,
            connection_key=value.connection_key,
            version=value.version,
            name=value.name,
            provider_type=value.provider_type,
            api_format=value.api_format,
            base_url=value.base_url,
            region=value.region,
            capability_json=value.capability_json,
            connection_sha256=value.connection_sha256,
            status=value.status,
            state_version=value.state_version,
            validated_at=value.validated_at,
            retired_at=value.retired_at,
            created_by_id=value.created_by_id,
            updated_by_id=value.updated_by_id,
            created_at=value.created_at,
            updated_at=value.updated_at,
        )

    @classmethod
    def _validate_endpoint(cls, *, base_url: str) -> None:
        canonical_base_url = cls._canonical_base_url(base_url)
        if canonical_base_url != base_url:
            raise AIControlValidationError("ai_connection_base_url_not_canonical")

    async def _replay_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIAPIConnection | None:
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
                audit.error_code or "ai_api_connection_command_rejected"
            )
        item = await self.dal.get_by_id(audit.resource_id)
        if item is None:
            raise AIControlStateConflictError("ai_control_audit_resource_missing")
        return item

    async def _replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIAPIConnection | None:
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
                    audit.error_code or "ai_api_connection_command_rejected"
                )
            item = await AIAPIConnectionDal(replay_db).get_by_id(audit.resource_id)
            if item is None:
                raise AIControlStateConflictError("ai_control_audit_resource_missing")
            return item

    async def _rollback_and_replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIAPIConnection | None:
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
        item: AIAPIConnection,
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
            rejected_dal = AIAPIConnectionDal(rejected_db)
            rejected_audit = AIControlAuditService(rejected_db)
            current = await rejected_dal.get_by_id(item.id)
            if (
                current is None
                or current.status != "draft"
                or current.state_version != payload.expected_state_version
                or current.connection_sha256 != item.connection_sha256
            ):
                replay_required = True
            else:
                audit = await rejected_audit.append_rejected(
                    resource_type=self.RESOURCE_TYPE,
                    resource_id=item.id,
                    resource_key=item.connection_key,
                    action_type="validate",
                    request_id=payload.request_id,
                    actor=actor,
                    before_sha256=item.connection_sha256,
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
        raise AIControlStateConflictError("ai_api_connection_validate_conflict")

    async def create(
        self, *, payload: ConnectionCreate, actor: ControlPlaneContext
    ) -> ConnectionResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="create"
        )
        if replay is not None:
            return self._response(replay)
        if await self.dal.get_by_key_version(payload.connection_key, payload.version):
            raise AIControlStateConflictError("ai_api_connection_key_version_exists")
        capability = payload.capability_json.model_dump(mode="json")
        base_url = self._canonical_base_url(payload.base_url)
        values = {
            "id": new_opaque_id(),
            "connection_key": payload.connection_key,
            "version": payload.version,
            "name": payload.name,
            "provider_type": payload.provider_type,
            "api_format": payload.api_format,
            "base_url": base_url,
            "secret_ref": self._LEGACY_SECRET_REF_PLACEHOLDER,
            "region": payload.region,
            "capability_json": capability,
            "status": "draft",
            "state_version": 0,
            "created_by_id": actor.subject_id,
            "updated_by_id": actor.subject_id,
        }
        self._validate_endpoint(base_url=values["base_url"])
        values["connection_sha256"] = self._connection_sha(values)
        item = await self.dal.create_idempotent(values)
        if item is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_api_connection_create_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=item.id,
            resource_key=item.connection_key,
            action_type="create",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=None,
            after_sha256=item.connection_sha256,
            changed_fields=[
                "connection_key",
                "version",
                "name",
                "provider_type",
                "api_format",
                "base_url",
                "region",
                "capability_json",
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
        self, *, payload: ConnectionUpdate, actor: ControlPlaneContext
    ) -> ConnectionResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="update"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_api_connection_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError("ai_api_connection_draft_required")
        capability = payload.capability_json.model_dump(mode="json")
        base_url = self._canonical_base_url(payload.base_url)
        content = {
            "connection_key": item.connection_key,
            "version": item.version,
            "provider_type": payload.provider_type,
            "api_format": payload.api_format,
            "base_url": base_url,
            "region": payload.region,
            "capability_json": capability,
        }
        self._validate_endpoint(base_url=base_url)
        updated = await self.dal.cas_update(
            connection_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "name": payload.name,
                "provider_type": payload.provider_type,
                "api_format": payload.api_format,
                "base_url": base_url,
                "region": payload.region,
                "capability_json": capability,
                "connection_sha256": self._connection_sha(content),
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="update"
            )
            if replayed is not None:
                return self._response(replayed)
            raise AIControlStateConflictError("ai_api_connection_update_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.connection_key,
            action_type="update",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.connection_sha256,
            after_sha256=updated.connection_sha256,
            changed_fields=[
                "name",
                "provider_type",
                "api_format",
                "base_url",
                "region",
                "capability_json",
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
    ) -> ConnectionResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="validate"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_api_connection_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError(
                "ai_api_connection_validate_draft_required"
            )
        try:
            self._validate_endpoint(base_url=item.base_url)
            expected_sha = self._connection_sha(
                {
                    "connection_key": item.connection_key,
                    "version": item.version,
                    "provider_type": item.provider_type,
                    "api_format": item.api_format,
                    "base_url": item.base_url,
                    "region": item.region,
                    "capability_json": item.capability_json,
                }
            )
            if expected_sha != item.connection_sha256:
                raise AIControlValidationError("ai_api_connection_sha_mismatch")
        except AIControlValidationError as exc:
            await self._mark_rejected_validation(
                item=item,
                payload=payload,
                actor=actor,
                error_code=str(exc),
            )
            raise
        updated = await self.dal.cas_update(
            connection_id=item.id,
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
            raise AIControlStateConflictError("ai_api_connection_validate_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.connection_key,
            action_type="validate",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.connection_sha256,
            after_sha256=updated.connection_sha256,
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
    ) -> ConnectionResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="retire"
        )
        if replay is not None:
            return self._response(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_api_connection_not_found")
        if item.status not in {"draft", "validated"}:
            raise AIControlStateConflictError("ai_api_connection_retire_state_invalid")
        updated = await self.dal.cas_update(
            connection_id=item.id,
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
            raise AIControlStateConflictError("ai_api_connection_retire_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.connection_key,
            action_type="retire",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.connection_sha256,
            after_sha256=updated.connection_sha256,
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

    async def detail(self, *, connection_id: str) -> ConnectionResponse:
        item = await self.dal.get_by_id(connection_id)
        if item is None:
            raise AIControlNotFoundError("ai_api_connection_not_found")
        return self._response(item)

    async def page(
        self, *, page: int, limit: int, provider_type: str | None, status: str | None
    ) -> PageResult[ConnectionResponse]:
        items, total = await self.dal.page(
            page=page, limit=limit, provider_type=provider_type, status=status
        )
        return PageResult(
            data=[self._response(item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )


__all__ = ["APIConnectionService"]
