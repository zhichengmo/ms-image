from typing import Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.image_asset import XRayImageAsset


class XRayImageAssetDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayImageAsset)

    async def create_assets(self, values: list[dict[str, Any]]) -> list[XRayImageAsset]:
        if not values:
            return []
        await self.create_datas(values)
        tenant_id = str(values[0]["tenant_id"])
        study_revision_id = str(values[0]["study_revision_id"])
        return await self.list_for_study(
            tenant_id=tenant_id, study_revision_id=study_revision_id
        )

    async def get_by_id(self, *, tenant_id: str, asset_id: str) -> XRayImageAsset | None:
        return await self.get_data(
            data_id=asset_id,
            v_where=[self.model.tenant_id == tenant_id],
            v_return_none=True,
        )

    async def list_for_study(
        self, *, tenant_id: str, study_revision_id: str
    ) -> list[XRayImageAsset]:
        return await self.get_datas(
            page=1,
            limit=256,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.study_revision_id == study_revision_id,
            ],
            v_order="asc",
            v_order_field="source_index",
            v_return_objs=True,
        )

    async def list_originals_for_study(
        self, *, tenant_id: str, study_revision_id: str
    ) -> list[XRayImageAsset]:
        return await self.get_datas(
            page=1,
            limit=256,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.study_revision_id == study_revision_id,
                self.model.asset_role == "original",
            ],
            v_order="asc",
            v_order_field="source_index",
            v_return_objs=True,
        )

    async def mark_uploaded(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        object_key: str,
        content_sha256: str,
        mime_type: str,
        byte_size: int,
        pixel_width: int,
        pixel_height: int,
        uploaded_at: datetime,
    ) -> XRayImageAsset | None:
        changed = await self.conditional_update(
            v_where=[
                self.model.id == asset_id,
                self.model.tenant_id == tenant_id,
                self.model.asset_status == "pending",
            ],
            data={
                "object_key": object_key,
                "content_sha256": content_sha256,
                "mime_type": mime_type,
                "byte_size": byte_size,
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
                "asset_status": "uploaded",
                "uploaded_at": uploaded_at,
            },
        )
        if not changed:
            return None
        return await self.get_by_id(tenant_id=tenant_id, asset_id=asset_id)

    async def mark_invalid(self, *, tenant_id: str, asset_id: str) -> bool:
        return await self.conditional_update(
            v_where=[
                self.model.id == asset_id,
                self.model.tenant_id == tenant_id,
                self.model.asset_status == "pending",
            ],
            data={"asset_status": "invalid"},
        )
