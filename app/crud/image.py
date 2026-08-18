from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.image import Image


class ImageDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Image)

    async def create_idempotent(self, values: dict[str, Any]) -> Image | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_image_record_" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, image_id: str) -> Image | None:
        return await self.get_data(data_id=image_id, v_return_none=True)

    async def get_by_object(
        self, *, storage_profile: str, object_key: str
    ) -> Image | None:
        return await self.get_data(
            storage_profile=storage_profile,
            object_key=object_key,
            v_return_none=True,
        )

    async def get_latest_logical(
        self, *, series_id: str, logical_image_key: str
    ) -> Image | None:
        rows = await self.get_datas(
            page=1,
            limit=1,
            series_id=series_id,
            logical_image_key=logical_image_key,
            v_order="desc",
            v_order_field="image_version_no",
            v_return_objs=True,
        )
        return rows[0] if rows else None

    async def list_for_series(self, series_id: str) -> list[Image]:
        return await self.get_datas(
            limit=0,
            series_id=series_id,
            v_order_field="sequence_no",
            v_return_objs=True,
        )

    async def list_ready_for_series(self, series_id: str) -> list[Image]:
        return await self.get_datas(
            limit=0,
            series_id=series_id,
            status="ready",
            v_order_field="sequence_no",
            v_return_objs=True,
        )

    async def cas_update(
        self, *, image_id: str, expected_version: int, values: dict[str, Any]
    ) -> Image | None:
        allowed = {
            "supersedes_image_id",
            "object_version_id",
            "upload_session_ref",
            "content_type",
            "sha256",
            "size_bytes",
            "kms_key_version",
            "sop_instance_uid",
            "sop_class_uid",
            "instance_no",
            "projection",
            "technical_metadata_json",
            "status",
            "validation_owner_id",
            "validation_lease_generation",
            "validation_lease_expires_at",
            "validation_heartbeat_at",
            "validation_attempt_count",
            "next_validation_at",
            "error_code",
            "verified_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("image_update_fields_invalid")
        return await self.cas_put_data(
            data_id=image_id, expected_version=expected_version, data=values
        )


__all__ = ["ImageDal"]
