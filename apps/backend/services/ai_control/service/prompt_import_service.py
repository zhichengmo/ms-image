"""Control-plane import of published external Prompts (Nacos first)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.async_db import session_factory
from apps.backend.core.config import settings
from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.ai.prompting.message_contract import (
    PromptMessageContractError,
    normalize_prompt_message_contract,
    validate_prompt_message_template,
)
from apps.backend.crud.ai_prompt_template import AIPromptTemplateDal
from apps.backend.models.ai_prompt_template import AIPromptTemplate
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_control import (
    PromptImportRequest,
    PromptImportResponse,
)
from apps.backend.services.ai_control.service.control_audit_service import (
    AIControlAuditService,
)
from apps.backend.services.ai_control.service.errors import (
    AIControlStateConflictError,
    AIControlValidationError,
)
from apps.backend.services.ai_control.service.prompt_source import (
    ImportedPromptRecord,
    NacosPromptSourceClient,
    PromptSourceError,
    build_source_receipt,
    nacos_data_id,
    normalize_imported_prompt,
    parse_nacos_prompt_payload,
    receipt_sha256,
    variant_candidates,
)
from apps.backend.services.ai_control.service.prompt_template_service import (
    PromptTemplateService,
)

NacosFetcher = Callable[..., Awaitable[ImportedPromptRecord | None]]


class PromptImportService:
    RESOURCE_TYPE = "prompt"

    def __init__(
        self,
        db: AsyncSession,
        *,
        fetcher: NacosFetcher | None = None,
    ):
        self.dal = AIPromptTemplateDal(db)
        self.audit = AIControlAuditService(db)
        self.prompt_service = PromptTemplateService(db)
        self._fetcher = fetcher

    async def _fetch_nacos(
        self,
        *,
        data_id: str,
        release_or_version: str | None,
        label: str | None,
        namespace_id: str,
    ) -> ImportedPromptRecord | None:
        if self._fetcher is not None:
            return await self._fetcher(
                data_id=data_id,
                version=release_or_version,
                label=label,
            )
        client = NacosPromptSourceClient(
            server_addr=settings.NACOS_SERVER_ADDR,
            namespace_id=namespace_id,
            context_path=settings.NACOS_CONTEXT_PATH,
            username=settings.NACOS_USERNAME,
            password=settings.NACOS_PASSWORD,
            timeout_seconds=settings.NACOS_PROMPT_TIMEOUT_SECONDS,
            caller_service=settings.PROMPT_RUNTIME_CALLER_SERVICE,
        )
        try:
            payload = await client.fetch(
                data_id=data_id,
                version=release_or_version,
                label=label,
            )
        finally:
            await client.aclose()
        if payload is None:
            return None
        return parse_nacos_prompt_payload(payload)

    async def _replay_or_none(self, *, request_id: str) -> AIPromptTemplate | None:
        audit = await self.audit.find_command(
            request_id=request_id,
            resource_type=self.RESOURCE_TYPE,
            action_type="import",
        )
        if audit is None:
            return None
        if audit.result_type != "succeeded":
            raise AIControlValidationError(
                audit.error_code or "ai_prompt_import_command_rejected"
            )
        item = await self.dal.get_by_id(audit.resource_id)
        if item is None:
            raise AIControlStateConflictError("ai_control_audit_resource_missing")
        return item

    async def _replay_committed_or_none(
        self, *, request_id: str
    ) -> AIPromptTemplate | None:
        async with session_factory() as replay_db:
            audit = await AIControlAuditService(replay_db).find_command(
                request_id=request_id,
                resource_type=self.RESOURCE_TYPE,
                action_type="import",
            )
            if audit is None or audit.result_type != "succeeded":
                return None
            return await AIPromptTemplateDal(replay_db).get_by_id(audit.resource_id)

    async def _rollback_and_replay_committed_or_none(
        self, *, request_id: str
    ) -> AIPromptTemplate | None:
        await self.dal.db.rollback()
        return await self._replay_committed_or_none(request_id=request_id)

    @classmethod
    def _response(
        cls,
        item: AIPromptTemplate,
        *,
        nacos_data_id: str,
        requested_variant: str,
        resolved_variant: str,
        fallback_used: bool,
    ) -> PromptImportResponse:
        base = PromptTemplateService.detail_response(item).model_dump(mode="json")
        return PromptImportResponse(
            **base,
            nacos_data_id=nacos_data_id,
            requested_variant=requested_variant,
            resolved_variant=resolved_variant,
            fallback_used=fallback_used,
        )

    async def import_prompt(
        self, *, payload: PromptImportRequest, actor: ControlPlaneContext
    ) -> PromptImportResponse:
        replay = await self._replay_or_none(request_id=payload.request_id)
        if replay is not None:
            receipt = replay.source_receipt_json or {}
            return self._response(
                replay,
                nacos_data_id=(
                    receipt.get("source_key", "")
                    if isinstance(receipt, Mapping)
                    else ""
                ),
                requested_variant=(
                    receipt.get("requested_variant", "default")
                    if isinstance(receipt, Mapping)
                    else "default"
                ),
                resolved_variant=(
                    receipt.get("resolved_variant", "default")
                    if isinstance(receipt, Mapping)
                    else "default"
                ),
                fallback_used=bool(
                    receipt.get("fallback_used", False)
                    if isinstance(receipt, Mapping)
                    else False
                ),
            )
        existing = await self.dal.get_by_key_version(
            payload.prompt_key, payload.version
        )
        if existing is not None:
            raise AIControlStateConflictError("ai_prompt_template_key_version_exists")

        requested_variant = payload.variant
        try:
            candidates = variant_candidates(
                requested_variant,
                module_code=payload.module_code,
            )
        except PromptSourceError as exc:
            raise AIControlValidationError(str(exc)) from exc
        resolved: tuple[str, str, ImportedPromptRecord] | None = None
        for candidate in candidates:
            try:
                data_id = nacos_data_id(
                    service_code=payload.service_code,
                    module_code=payload.module_code,
                    prompt_key=payload.prompt_key,
                    variant=candidate,
                    locale=payload.locale,
                )
            except PromptSourceError as exc:
                raise AIControlValidationError(str(exc)) from exc
            record = await self._fetch_nacos(
                data_id=data_id,
                release_or_version=(
                    payload.nacos_release_or_version
                    or settings.NACOS_PROMPT_VERSION
                    or None
                ),
                label=payload.nacos_label or settings.NACOS_PROMPT_LABEL or None,
                namespace_id=(
                    payload.namespace_id
                    or settings.NACOS_PROMPT_NAMESPACE_ID
                    or settings.NACOS_NAMESPACE_ID
                ),
            )
            if record is None:
                continue
            resolved = (candidate, data_id, record)
            break
        if resolved is None:
            raise AIControlValidationError("prompt_source_not_found")
        resolved_variant, data_id, record = resolved
        try:
            content, variables = normalize_imported_prompt(record.template)
        except PromptSourceError as exc:
            raise AIControlValidationError(str(exc)) from exc
        message_contract = self._normalize_message_contract(
            payload.message_contract_json.model_dump(mode="json")
            if payload.message_contract_json is not None
            else None
        )
        try:
            validate_prompt_message_template(
                content=content,
                message_contract_json=message_contract,
            )
        except PromptMessageContractError as exc:
            raise AIControlValidationError(str(exc)) from exc
        content_sha256 = PromptTemplateService.content_sha(content)
        namespace_id = (
            payload.namespace_id
            or settings.NACOS_PROMPT_NAMESPACE_ID
            or settings.NACOS_NAMESPACE_ID
        )
        receipt = build_source_receipt(
            source_type="nacos",
            namespace=namespace_id,
            source_key=data_id,
            release_or_version=(
                record.version
                or record.label
                or record.md5
                or payload.nacos_release_or_version
                or settings.NACOS_PROMPT_VERSION
            ),
            requested_variant=requested_variant,
            resolved_variant=resolved_variant,
            fallback_used=resolved_variant != requested_variant,
            content_sha256=content_sha256,
        )
        receipt_sha = receipt_sha256(receipt)
        item = await self.dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "prompt_key": payload.prompt_key,
                "version": payload.version,
                "name": payload.name,
                "description": payload.description,
                "language": payload.locale,
                "content": content,
                "variables_json": variables,
                "content_sha256": content_sha256,
                "message_contract_json": message_contract,
                "source_receipt_json": receipt,
                "source_receipt_sha256": receipt_sha,
                "status": "draft",
                "state_version": 0,
                "created_by_id": actor.subject_id,
                "updated_by_id": actor.subject_id,
            }
        )
        if item is None:
            replayed = await self._replay_committed_or_none(
                request_id=payload.request_id
            )
            if replayed is not None:
                return self._response(
                    replayed,
                    nacos_data_id=data_id,
                    requested_variant=requested_variant,
                    resolved_variant=resolved_variant,
                    fallback_used=resolved_variant != requested_variant,
                )
            raise AIControlStateConflictError("ai_prompt_import_create_conflict")
        audit = await self.audit.append_succeeded(
            resource_type=self.RESOURCE_TYPE,
            resource_id=item.id,
            resource_key=item.prompt_key,
            action_type="import",
            request_id=payload.request_id,
            actor=actor,
            before_sha256=None,
            after_sha256=receipt_sha,
            changed_fields=[
                "prompt_key",
                "version",
                "name",
                "language",
                "content_sha256",
                "variables_json",
                "message_contract_json",
                "source_receipt_sha256",
                "status",
            ],
            reason=f"nacos:{data_id}",
        )
        if audit is None:
            replayed = await self._rollback_and_replay_committed_or_none(
                request_id=payload.request_id
            )
            if replayed is not None:
                return self._response(
                    replayed,
                    nacos_data_id=data_id,
                    requested_variant=requested_variant,
                    resolved_variant=resolved_variant,
                    fallback_used=resolved_variant != requested_variant,
                )
            raise AIControlStateConflictError("ai_control_audit_command_conflict")
        return self._response(
            item,
            nacos_data_id=data_id,
            requested_variant=requested_variant,
            resolved_variant=resolved_variant,
            fallback_used=resolved_variant != requested_variant,
        )

    @staticmethod
    def _normalize_message_contract(
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        try:
            return normalize_prompt_message_contract(value)
        except PromptMessageContractError as exc:
            raise AIControlValidationError(str(exc)) from exc


__all__ = ["PromptImportService"]
