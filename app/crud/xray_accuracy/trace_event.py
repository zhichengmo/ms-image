from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.trace_event import XRayTraceEvent


_SENSITIVE_KEYS = frozenset(
    {
        "secret",
        "api_key",
        "token",
        "authorization",
        "signed_url",
        "image_url",
        "source_url",
        "image_bytes",
        "prompt",
        "rendered_prompt",
        "original_prompt",
        "response_text",
        "raw_output",
        "response_body",
    }
)
_SENSITIVE_VALUE_MARKERS = (
    "://",
    "data:image/",
    "bearer ",
    "authorization:",
    "signed_url",
    "signedurl",
    "token=",
    "secret=",
    "api_key=",
    "-----begin ",
)


def _contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _SENSITIVE_KEYS or _contains_sensitive(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive(child) for child in value)
    if isinstance(value, str):
        return any(marker in value.casefold() for marker in _SENSITIVE_VALUE_MARKERS)
    return False


class XRayTraceEventDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayTraceEvent)

    async def create_event(self, values: dict) -> XRayTraceEvent:
        if _contains_sensitive(values.get("event_payload_json")):
            raise ValueError("trace_event_sensitive_payload_forbidden")
        return await self.create_data(values, v_return_obj=True)

    async def get_by_id(self, event_id: str, tenant_id: str) -> XRayTraceEvent | None:
        return await self.get_data(
            data_id=event_id,
            v_where=[self.model.tenant_id == tenant_id],
            v_return_none=True,
        )

    async def create_event_once(self, values: dict) -> XRayTraceEvent:
        """Append one deterministic technical event idempotently.

        Re-delivered broker messages may carry the same trace id.  A unique
        primary-key race is contained in a savepoint and resolved by reading
        the already committed event; no second append or state transition is
        produced.
        """
        event_id = values.get("id")
        tenant_id = values.get("tenant_id")
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("trace_event_identity_invalid")
        existing = await self.get_by_id(event_id, tenant_id)
        if existing is not None:
            return existing
        try:
            async with self.db.begin_nested():
                return await self.create_event(values)
        except IntegrityError:
            existing = await self.get_by_id(event_id, tenant_id)
            if existing is not None:
                return existing
            raise

    async def list_for_tenant_run(
        self, *, tenant_id: str, run_id: str, page: int, limit: int
    ) -> tuple[list[XRayTraceEvent], int]:
        return await self.get_datas(
            page=page,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.run_id == run_id,
            ],
            v_order="desc",
            v_order_field="created_at",
            v_return_count=True,
            v_return_objs=True,
        )
