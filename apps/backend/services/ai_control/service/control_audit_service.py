"""Append-only control-plane audit orchestration.

This service deliberately only appends through ``AIControlAuditRecordDal``.
Business services invoke it in their existing request transaction so a
successful mutation and its succeeded audit fact commit atomically.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.crud.ai_control_audit_record import AIControlAuditRecordDal
from apps.backend.models.ai_control_audit_record import AIControlAuditRecord
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.ai_control import ControlAuditResponse, PageResult


class AIControlAuditService:
    CHANGESET_VERSION = "ai-control-change-set.v1"

    def __init__(self, db: AsyncSession):
        self.dal = AIControlAuditRecordDal(db)

    @staticmethod
    def response(value: AIControlAuditRecord) -> ControlAuditResponse:
        return ControlAuditResponse.model_validate(value)

    async def find_command(
        self, *, request_id: str, resource_type: str, action_type: str
    ) -> AIControlAuditRecord | None:
        return await self.dal.get_by_command(
            request_id=request_id,
            resource_type=resource_type,
            action_type=action_type,
        )

    async def append_succeeded(
        self,
        *,
        resource_type: str,
        resource_id: str,
        resource_key: str,
        action_type: str,
        request_id: str,
        actor: ControlPlaneContext,
        before_sha256: str | None,
        after_sha256: str | None,
        changed_fields: list[str],
        reason: str | None = None,
    ) -> AIControlAuditRecord | None:
        return await self.dal.append_idempotent(
            {
                "id": new_opaque_id(),
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_key": resource_key,
                "action_type": action_type,
                "before_sha256": before_sha256,
                "after_sha256": after_sha256,
                "changed_fields_json": {
                    "contract_version": self.CHANGESET_VERSION,
                    "fields": sorted(set(changed_fields)),
                    "before_sha256": before_sha256,
                    "after_sha256": after_sha256,
                },
                "reason": reason,
                "request_id": request_id,
                "actor_type": "user",
                "actor_id": actor.subject_id,
                "result_type": "succeeded",
                "error_code": None,
            }
        )

    async def append_rejected(
        self,
        *,
        resource_type: str,
        resource_id: str,
        resource_key: str,
        action_type: str,
        request_id: str,
        actor: ControlPlaneContext,
        before_sha256: str | None,
        error_code: str,
        reason: str | None = None,
    ) -> AIControlAuditRecord | None:
        """Append a stable failed-command fact without persisting error detail."""
        return await self.dal.append_idempotent(
            {
                "id": new_opaque_id(),
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_key": resource_key,
                "action_type": action_type,
                "before_sha256": before_sha256,
                "after_sha256": before_sha256,
                "changed_fields_json": {
                    "contract_version": self.CHANGESET_VERSION,
                    "fields": ["error_code"],
                    "before_sha256": before_sha256,
                    "after_sha256": before_sha256,
                },
                "reason": reason,
                "request_id": request_id,
                "actor_type": "user",
                "actor_id": actor.subject_id,
                "result_type": "rejected",
                "error_code": error_code,
            }
        )

    async def page(
        self,
        *,
        page: int,
        limit: int,
        resource_type: str | None,
        resource_id: str | None,
        actor_id: str | None,
    ) -> PageResult[ControlAuditResponse]:
        items, total = await self.dal.page(
            page=page,
            limit=limit,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
        )
        return PageResult(
            data=[self.response(item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )


__all__ = ["AIControlAuditService"]
