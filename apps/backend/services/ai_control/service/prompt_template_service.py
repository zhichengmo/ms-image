from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.async_db import session_factory
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.ai.prompting.message_contract import (
    PromptMessageContractError,
    normalize_prompt_message_contract,
    validate_prompt_message_template,
)
from apps.backend.core.ai.prompting.renderer import (
    PromptRenderError,
    PromptRenderer,
    normalize_prompt_content,
)
from apps.backend.crud.ai_prompt_template import AIPromptTemplateDal
from apps.backend.models.ai_prompt_template import AIPromptTemplate
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_control import (
    PageResult,
    PromptCreate,
    PromptDetailResponse,
    PromptSummaryResponse,
    PromptUpdate,
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


class PromptTemplateService:
    RESOURCE_TYPE = "prompt"

    def __init__(self, db: AsyncSession):
        self.dal = AIPromptTemplateDal(db)
        self.audit = AIControlAuditService(db)

    @staticmethod
    def _normalize_content(value: str) -> str:
        return normalize_prompt_content(value)

    @classmethod
    def _content_sha(cls, value: str) -> str:
        from apps.backend.core.ai.prompting.contracts import sha256_text

        return sha256_text(cls._normalize_content(value))

    @classmethod
    def content_sha(cls, value: str) -> str:
        """Public Prompt content SHA helper for control-plane reuse."""
        return cls._content_sha(value)

    @staticmethod
    def _validate_language(language: str) -> None:
        if language != "zh-CN":
            raise AIControlValidationError("ai_prompt_template_language_invalid")

    @staticmethod
    def _summary(value: AIPromptTemplate) -> PromptSummaryResponse:
        return PromptSummaryResponse(
            id=value.id,
            prompt_key=value.prompt_key,
            version=value.version,
            name=value.name,
            description=value.description,
            language=value.language,
            content_sha256=value.content_sha256,
            message_contract_json=value.message_contract_json,
            source_receipt_sha256=value.source_receipt_sha256,
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
    def _detail(cls, value: AIPromptTemplate) -> PromptDetailResponse:
        return PromptDetailResponse(
            **cls._summary(value).model_dump(),
            content=value.content,
            variables_json=value.variables_json,
        )

    @classmethod
    def detail_response(cls, value: AIPromptTemplate) -> PromptDetailResponse:
        """Public Prompt detail response helper for control-plane reuse."""
        return cls._detail(value)

    async def _replay_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIPromptTemplate | None:
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
                audit.error_code or "ai_prompt_template_command_rejected"
            )
        item = await self.dal.get_by_id(audit.resource_id)
        if item is None:
            raise AIControlStateConflictError("ai_control_audit_resource_missing")
        return item

    async def _replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIPromptTemplate | None:
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
                    audit.error_code or "ai_prompt_template_command_rejected"
                )
            item = await AIPromptTemplateDal(replay_db).get_by_id(audit.resource_id)
            if item is None:
                raise AIControlStateConflictError("ai_control_audit_resource_missing")
            return item

    async def _rollback_and_replay_committed_or_none(
        self, *, request_id: str, action_type: str
    ) -> AIPromptTemplate | None:
        """Undo local business changes before returning another command's replay."""
        await self.dal.db.rollback()
        return await self._replay_committed_or_none(
            request_id=request_id, action_type=action_type
        )

    @staticmethod
    def _normalize_message_contract(
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        try:
            return normalize_prompt_message_contract(value)
        except PromptMessageContractError as exc:
            raise AIControlValidationError(str(exc)) from exc

    @classmethod
    def _validate_content_contract(
        cls, *, content: str, variables_json: dict[str, Any]
    ) -> None:
        try:
            normalized = PromptRenderer.validate_template(
                content=content, variables_json=variables_json
            )
        except PromptRenderError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if not normalized.strip():
            raise AIControlValidationError("prompt_content_empty")
        if len(normalized) > 120_000:
            raise AIControlValidationError("prompt_content_hard_budget_exceeded")

    @staticmethod
    def _validate_message_contract_variables(
        *,
        variables_json: dict[str, Any],
        message_contract_json: dict[str, Any] | None,
        content: str = "",
    ) -> None:
        """Reject a message contract whose context keys are not declared variables."""
        if message_contract_json is None:
            return
        try:
            validate_prompt_message_template(
                content=content,
                message_contract_json=message_contract_json,
            )
            required, optional = PromptRenderer.declared_variables(variables_json)
        except (PromptRenderError, PromptMessageContractError) as exc:
            raise AIControlValidationError(str(exc)) from exc
        missing = set(message_contract_json.get("user_context_keys") or []) - (
            required | optional
        )
        if missing:
            raise AIControlValidationError(
                "prompt_message_contract_context_variable_missing"
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
        item: AIPromptTemplate,
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
            rejected_dal = AIPromptTemplateDal(rejected_db)
            rejected_audit = AIControlAuditService(rejected_db)
            current = await rejected_dal.get_by_id(item.id)
            if (
                current is None
                or current.status != "draft"
                or current.state_version != payload.expected_state_version
                or current.content_sha256 != item.content_sha256
            ):
                replay_required = True
            else:
                audit = await rejected_audit.append_rejected(
                    resource_type=self.RESOURCE_TYPE,
                    resource_id=item.id,
                    resource_key=item.prompt_key,
                    action_type="validate",
                    request_id=payload.request_id,
                    actor=actor,
                    before_sha256=item.content_sha256,
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
        raise AIControlStateConflictError("ai_prompt_template_validate_conflict")

    async def create(
        self, *, payload: PromptCreate, actor: ControlPlaneContext
    ) -> PromptDetailResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="create"
        )
        if replay is not None:
            return self._detail(replay)
        existing = await self.dal.get_by_key_version(
            payload.prompt_key, payload.version
        )
        if existing is not None:
            raise AIControlStateConflictError("ai_prompt_template_key_version_exists")
        self._validate_language(payload.language)
        content = self._normalize_content(payload.content)
        variables = payload.variables_json.model_dump(mode="json")
        message_contract = self._normalize_message_contract(
            payload.message_contract_json.model_dump(mode="json")
            if payload.message_contract_json is not None
            else None
        )
        self._validate_content_contract(content=content, variables_json=variables)
        self._validate_message_contract_variables(
            content=content,
            variables_json=variables,
            message_contract_json=message_contract,
        )
        item = await self.dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "prompt_key": payload.prompt_key,
                "version": payload.version,
                "name": payload.name,
                "description": payload.description,
                "language": payload.language,
                "content": content,
                "variables_json": variables,
                "content_sha256": self._content_sha(content),
                "message_contract_json": message_contract,
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
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_prompt_template_create_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=item.id,
            resource_key=item.prompt_key,
            action_type="create",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=None,
            after_sha256=item.content_sha256,
            changed_fields=[
                "prompt_key",
                "version",
                "name",
                "description",
                "language",
                "content_sha256",
                "variables_json",
                "message_contract_json",
                "status",
            ],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="create"
            )
            if replayed is not None:
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._detail(item)

    async def update(
        self, *, payload: PromptUpdate, actor: ControlPlaneContext
    ) -> PromptDetailResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="update"
        )
        if replay is not None:
            return self._detail(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_prompt_template_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError("ai_prompt_template_draft_required")
        self._validate_language(payload.language)
        variables = payload.variables_json.model_dump(mode="json")
        content = self._normalize_content(payload.content)
        message_contract = self._normalize_message_contract(
            payload.message_contract_json.model_dump(mode="json")
            if payload.message_contract_json is not None
            else None
        )
        self._validate_content_contract(content=content, variables_json=variables)
        self._validate_message_contract_variables(
            content=content,
            variables_json=variables,
            message_contract_json=message_contract,
        )
        updated = await self.dal.cas_update(
            prompt_id=item.id,
            expected_version=payload.expected_state_version,
            values={
                "name": payload.name,
                "description": payload.description,
                "language": payload.language,
                "content": content,
                "variables_json": variables,
                "content_sha256": self._content_sha(content),
                "message_contract_json": message_contract,
                "updated_by_id": actor.subject_id,
            },
        )
        if updated is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id, action_type="update"
            )
            if replayed is not None:
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_prompt_template_update_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.prompt_key,
            action_type="update",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.content_sha256,
            after_sha256=updated.content_sha256,
            changed_fields=[
                "name",
                "description",
                "language",
                "content_sha256",
                "variables_json",
                "message_contract_json",
            ],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="update"
            )
            if replayed is not None:
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._detail(updated)

    async def validate(
        self, *, payload: StateCommandRequest, actor: ControlPlaneContext
    ) -> PromptDetailResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="validate"
        )
        if replay is not None:
            return self._detail(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_prompt_template_not_found")
        if item.status != "draft":
            raise AIControlStateConflictError(
                "ai_prompt_template_validate_draft_required"
            )
        try:
            self._validate_language(item.language)
            self._validate_content_contract(
                content=item.content, variables_json=item.variables_json
            )
            self._validate_message_contract_variables(
                content=item.content,
                variables_json=item.variables_json,
                message_contract_json=item.message_contract_json,
            )
            self._normalize_message_contract(item.message_contract_json)
            current_sha = self._content_sha(item.content)
            if item.content_sha256 != current_sha:
                raise AIControlValidationError("ai_prompt_template_sha_mismatch")
        except AIControlValidationError as exc:
            await self._mark_rejected_validation(
                item=item,
                payload=payload,
                actor=actor,
                error_code=str(exc),
            )
            raise
        updated = await self.dal.cas_update(
            prompt_id=item.id,
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
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_prompt_template_validate_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.prompt_key,
            action_type="validate",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.content_sha256,
            after_sha256=updated.content_sha256,
            changed_fields=["status", "validated_at"],
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="validate"
            )
            if replayed is not None:
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._detail(updated)

    async def retire(
        self, *, payload: RetireCommandRequest, actor: ControlPlaneContext
    ) -> PromptDetailResponse:
        replay = await self._replay_or_none(
            request_id=payload.request_id, action_type="retire"
        )
        if replay is not None:
            return self._detail(replay)
        item = await self.dal.get_by_id(payload.id)
        if item is None:
            raise AIControlNotFoundError("ai_prompt_template_not_found")
        if item.status not in {"draft", "validated"}:
            raise AIControlStateConflictError("ai_prompt_template_retire_state_invalid")
        updated = await self.dal.cas_update(
            prompt_id=item.id,
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
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_prompt_template_retire_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=updated.id,
            resource_key=updated.prompt_key,
            action_type="retire",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=item.content_sha256,
            after_sha256=updated.content_sha256,
            changed_fields=["status", "retired_at"],
            reason=payload.reason,
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id, action_type="retire"
            )
            if replayed is not None:
                return self._detail(replayed)
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._detail(updated)

    async def detail(self, *, prompt_id: str) -> PromptDetailResponse:
        item = await self.dal.get_by_id(prompt_id)
        if item is None:
            raise AIControlNotFoundError("ai_prompt_template_not_found")
        return self._detail(item)

    async def page(
        self, *, page: int, limit: int, prompt_key: str | None, status: str | None
    ) -> PageResult[PromptSummaryResponse]:
        items, total = await self.dal.page(
            page=page, limit=limit, prompt_key=prompt_key, status=status
        )
        return PageResult(
            data=[self._summary(item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )


__all__ = ["PromptTemplateService"]
