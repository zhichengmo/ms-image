from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.crud import DalBase
from app.models.xray_accuracy.study_snapshot import XRayStudySnapshot


class XRayStudySnapshotDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayStudySnapshot)

    async def create_snapshot(self, values: dict[str, Any]) -> XRayStudySnapshot:
        return await self.create_data(values, v_return_obj=True)

    async def create_snapshot_idempotent(
        self, values: dict[str, Any]
    ) -> XRayStudySnapshot | None:
        try:
            async with self.db.begin_nested():
                obj = self.model(**values)
                await self.flush(obj)
            return obj
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_xray_study_revision" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_revision(
        self, *, tenant_id: str, study_revision_id: str
    ) -> XRayStudySnapshot | None:
        return await self.get_data(
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.study_revision_id == study_revision_id,
            ],
            v_return_none=True,
        )

    async def list_for_session(
        self, *, tenant_id: str, session_id: str, page: int, limit: int
    ) -> tuple[list[XRayStudySnapshot], int]:
        return await self.get_datas(
            page=page,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.session_id == session_id,
            ],
            v_order="desc",
            v_order_field="created_at",
            v_return_count=True,
            v_return_objs=True,
        )

    async def freeze(
        self,
        *,
        tenant_id: str,
        study_revision_id: str,
        status: str,
        coverage_status: str,
        identity_confidence: str,
        projection_groups: list[dict[str, Any]],
        expected_manifest_sha256: str,
        ordered_source_image_ids: list[str],
        frozen_at: datetime,
    ) -> XRayStudySnapshot | None:
        if not expected_manifest_sha256 or not ordered_source_image_ids:
            raise ValueError("study_freeze_manifest_invalid")
        changed = await self.conditional_update(
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.study_revision_id == study_revision_id,
                self.model.frozen_at.is_(None),
            ],
            data={
                "study_status": status,
                "coverage_status": coverage_status,
                "identity_confidence": identity_confidence,
                "projection_groups_json": projection_groups,
                # These values are immutable facts of the frozen revision.  A
                # caller must supply the canonical values computed from the
                # current uploaded assets; they are intentionally not
                # accepted from an external request.
                "expected_manifest_sha256": expected_manifest_sha256,
                "ordered_source_image_ids_json": ordered_source_image_ids,
                "frozen_at": frozen_at,
            },
        )
        if not changed:
            return None
        return await self.get_by_revision(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )
