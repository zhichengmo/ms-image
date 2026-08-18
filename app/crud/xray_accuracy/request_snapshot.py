import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.request_snapshot import XRayRequestSnapshot


class XRayRequestSnapshotDal(DalBase):
    _FORBIDDEN_KEYS = {
        "abn", "nor", "disease_code", "filename", "file_name", "path",
        "history", "historical_output", "truth", "annotation", "ocr", "exif",
        "failure_bank", "score", "scorer", "diagnosis", "previous_output",
        "url", "signed_url", "image_url", "original_image", "authorization",
        "token", "secret",
    }
    _SENSITIVE_VALUE_MARKERS = (
        "://", "bearer ", "authorization:", "signed_url", "signedurl",
        "token=", "secret=", "api_key", "-----begin ",
    )

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayRequestSnapshot)

    async def create_snapshot(self, values: dict) -> XRayRequestSnapshot:
        self._validate_snapshot(values)
        return await self.create_data(values, v_return_obj=True)

    @classmethod
    def _validate_snapshot(cls, values: dict[str, Any]) -> None:
        """Keep direct DAL callers fail-closed at the persistence boundary.

        The Service validates the public request contract first, but a DAL is
        also callable from workers and administrative tooling.  The snapshot
        is immutable evidence, so accepting sensitive or caller-controlled URL
        fields here would bypass the Service's leakage gate.
        """
        manifest = values.get("manifest_json")
        if not isinstance(manifest, list) or not manifest:
            raise ValueError("snapshot_manifest_invalid")
        expected = list(range(len(manifest)))
        indexes = [item.get("source_index") for item in manifest if isinstance(item, dict)]
        if len(indexes) != len(manifest) or indexes != expected:
            raise ValueError("snapshot_manifest_source_index_invalid")
        for item in manifest:
            if set(item) - {"source_index", "source_image_ref", "mime_type", "expected_sha256", "projection_hint"}:
                raise ValueError("snapshot_manifest_fields_invalid")
            ref = item.get("source_image_ref")
            if not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}", ref):
                raise ValueError("snapshot_image_ref_must_be_opaque")
        cls._scan_json(manifest, "$.manifest_json")
        cls._scan_json(values.get("safe_metadata_json"), "$.safe_metadata_json")

    @classmethod
    def _scan_json(cls, value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                if key_text.casefold() in cls._FORBIDDEN_KEYS:
                    raise ValueError("snapshot_sensitive_field")
                cls._scan_json(child, f"{path}.{key_text}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._scan_json(child, f"{path}[{index}]")
        elif isinstance(value, str):
            if any(marker in value.casefold() for marker in cls._SENSITIVE_VALUE_MARKERS):
                raise ValueError("snapshot_sensitive_value")

    async def get_by_run(
        self, *, run_id: str, tenant_id: str
    ) -> XRayRequestSnapshot | None:
        return await self.get_data(
            v_where=[
                self.model.run_id == run_id,
                self.model.tenant_id == tenant_id,
            ],
            v_return_none=True,
        )
