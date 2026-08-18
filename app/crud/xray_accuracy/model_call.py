from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.model_call import XRayModelCall


_SENSITIVE_KEYS = frozenset({"secret", "token", "authorization", "signed_url", "image_url", "image_bytes"})
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


class XRayModelCallDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayModelCall)

    async def create_call(self, values: dict[str, Any]) -> XRayModelCall:
        provider_key = values.get("provider_key")
        if not isinstance(provider_key, str) or not provider_key.strip() or len(provider_key) > 64:
            raise ValueError("provider_key_invalid")
        if any(char.isspace() for char in provider_key):
            raise ValueError("provider_key_invalid")
        if values.get("fallback_used", "no") not in {"yes", "no"}:
            raise ValueError("fallback_flag_invalid")
        if type(values.get("retry_index", 0)) is not int or values.get("retry_index", 0) < 0:
            raise ValueError("retry_index_invalid")
        error_class = values.get("error_class")
        if error_class is not None and (not isinstance(error_class, str) or not error_class.strip() or len(error_class) > 64):
            raise ValueError("error_class_invalid")
        if values.get("fallback_used", "no") == "yes" and values.get("retry_index", 0) == 0:
            raise ValueError("fallback_retry_binding_invalid")
        if any(key in values for key in {"prompt", "raw_output", "signed_url", "image_bytes"}):
            raise ValueError("model_call_sensitive_payload_forbidden")
        if _contains_sensitive(values.get("receipt_json")):
            raise ValueError("model_call_receipt_sensitive_payload_forbidden")
        return await self.create_data(values, v_return_obj=True)

    async def list_for_tenant_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        page: int = 1,
        limit: int = 100,
    ) -> list[XRayModelCall]:
        return await self.get_datas(
            page=page,
            limit=limit,
            v_where=[self.model.tenant_id == tenant_id, self.model.run_id == run_id],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )
