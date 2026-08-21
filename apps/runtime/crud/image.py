from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.runtime.core.crud import DalBase
from apps.runtime.models.image import Image


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

    async def get_ready_logical(
        self, *, series_id: str, logical_image_key: str
    ) -> Image | None:
        rows = await self.get_datas(
            page=1,
            limit=2,
            series_id=series_id,
            logical_image_key=logical_image_key,
            status="ready",
            v_order="desc",
            v_order_field="image_version_no",
            v_return_objs=True,
        )
        if len(rows) > 1:
            raise ValueError("image_current_version_conflict")
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

    async def list_validation_candidates(
        self, *, now: datetime, limit: int
    ) -> list[Image]:
        if limit < 1:
            raise ValueError("image_validation_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "validating",
                or_(
                    self.model.next_validation_at.is_(None),
                    self.model.next_validation_at <= now,
                ),
                or_(
                    self.model.validation_lease_expires_at.is_(None),
                    self.model.validation_lease_expires_at <= now,
                ),
            ],
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def list_expired_validation_leases(
        self, *, now: datetime, limit: int
    ) -> list[Image]:
        if limit < 1:
            raise ValueError("image_validation_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "validating",
                self.model.validation_lease_generation > 0,
                self.model.validation_lease_expires_at.is_not(None),
                self.model.validation_lease_expires_at <= now,
            ],
            v_order_field="validation_lease_expires_at",
            v_return_objs=True,
        )

    async def list_expired_uploads(
        self, *, now: datetime, limit: int
    ) -> list[Image]:
        if limit < 1:
            raise ValueError("image_upload_reconcile_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "uploading",
                self.model.upload_expires_at.is_not(None),
                self.model.upload_expires_at <= now,
            ],
            v_order_field="upload_expires_at",
            v_return_objs=True,
        )

    async def list_ready_after(self, *, updated_at: datetime | None, image_id: str | None, limit: int) -> list[Image]:
        if limit < 1:
            raise ValueError("image_ready_scan_limit_invalid")
        where = [self.model.status == "ready"]
        if updated_at is not None:
            where.append(or_(self.model.updated_at > updated_at, and_(self.model.updated_at == updated_at, self.model.id > (image_id or ""))))
        return await self.get_datas(page=1, limit=limit, v_where=where, v_order_field="updated_at", v_return_objs=True)

    async def claim_validation_lease(
        self,
        *,
        image_id: str,
        expected_version: int,
        owner_id: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
        max_attempts: int,
    ) -> Image | None:
        owner = owner_id.strip()
        if (
            not owner
            or len(owner) > 128
            or lease_expires_at <= claimed_at
            or max_attempts < 1
        ):
            raise ValueError("image_validation_claim_invalid")
        claimed = await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "validating",
                self.model.state_version == expected_version,
                self.model.validation_attempt_count < max_attempts,
                or_(
                    self.model.next_validation_at.is_(None),
                    self.model.next_validation_at <= claimed_at,
                ),
                or_(
                    self.model.validation_lease_expires_at.is_(None),
                    self.model.validation_lease_expires_at <= claimed_at,
                ),
            ],
            data={
                "validation_owner_id": owner,
                "validation_lease_generation": self.model.validation_lease_generation + 1,
                "validation_lease_expires_at": lease_expires_at,
                "validation_heartbeat_at": claimed_at,
                "validation_attempt_count": self.model.validation_attempt_count + 1,
                "next_validation_at": None,
                "error_code": None,
            },
        )
        if not claimed:
            return None
        image = await self.get_data(
            data_id=image_id,
            v_return_none=True,
            v_expire_all=True,
        )
        if (
            image is None
            or image.status != "validating"
            or image.state_version != expected_version
            or image.validation_owner_id != owner
            or image.validation_lease_generation < 1
            or image.validation_lease_expires_at != lease_expires_at
        ):
            raise ValueError("image_validation_claim_readback_failed")
        return image

    async def refresh_upload_expiry(
        self,
        *,
        image_id: str,
        expected_version: int,
        upload_expires_at: datetime,
    ) -> Image | None:
        refreshed = await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "uploading",
                self.model.state_version == expected_version,
            ],
            data={"upload_expires_at": upload_expires_at},
        )
        if not refreshed:
            return None
        return await self.get_data(
            data_id=image_id,
            v_return_none=True,
            v_expire_all=True,
        )

    async def bind_multipart_upload_session(
        self,
        *,
        image_id: str,
        expected_version: int,
        upload_session_ref: str,
        upload_expires_at: datetime,
    ) -> Image | None:
        reference = upload_session_ref.strip()
        if not reference or len(reference) > 256:
            raise ValueError("multipart_upload_session_invalid")
        bound = await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "uploading",
                self.model.state_version == expected_version,
                self.model.upload_mode == "multipart",
                or_(
                    self.model.upload_session_ref.is_(None),
                    self.model.upload_session_ref == reference,
                ),
            ],
            data={
                "upload_session_ref": reference,
                "upload_expires_at": upload_expires_at,
            },
        )
        if not bound:
            return None
        return await self.get_data(
            data_id=image_id,
            v_return_none=True,
            v_expire_all=True,
        )

    async def heartbeat_validation_lease(
        self,
        *,
        image_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        owner = owner_id.strip()
        if not owner or lease_generation < 1 or lease_expires_at <= heartbeat_at:
            raise ValueError("image_validation_heartbeat_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "validating",
                self.model.state_version == expected_version,
                self.model.validation_owner_id == owner,
                self.model.validation_lease_generation == lease_generation,
                self.model.validation_lease_expires_at > heartbeat_at,
            ],
            data={
                "validation_heartbeat_at": heartbeat_at,
                "validation_lease_expires_at": lease_expires_at,
            },
        )

    async def release_validation_retry(
        self,
        *,
        image_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        released_at: datetime,
        next_validation_at: datetime,
        error_code: str,
    ) -> bool:
        owner = owner_id.strip()
        code = error_code.strip()
        if (
            not owner
            or lease_generation < 1
            or next_validation_at <= released_at
            or not code
        ):
            raise ValueError("image_validation_retry_invalid")
        return await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "validating",
                self.model.state_version == expected_version,
                self.model.validation_owner_id == owner,
                self.model.validation_lease_generation == lease_generation,
                self.model.validation_lease_expires_at > released_at,
            ],
            data={
                "validation_owner_id": None,
                "validation_lease_expires_at": None,
                "validation_heartbeat_at": None,
                "next_validation_at": next_validation_at,
                "error_code": code[:80],
            },
        )

    async def finalize_validation(
        self,
        *,
        image_id: str,
        expected_version: int,
        owner_id: str,
        lease_generation: int,
        finished_at: datetime,
        values: dict[str, Any],
    ) -> Image | None:
        owner = owner_id.strip()
        if (
            not owner
            or lease_generation < 1
            or values.get("status") not in {"ready", "quarantined"}
        ):
            raise ValueError("image_validation_terminal_status_invalid")
        terminal = dict(values)
        terminal.update(
            {
                "validation_owner_id": None,
                "validation_lease_expires_at": None,
                "validation_heartbeat_at": None,
                "next_validation_at": None,
            }
        )
        if not set(terminal).issubset(
            {
                "object_version_id",
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
                "validation_lease_expires_at",
                "validation_heartbeat_at",
                "next_validation_at",
                "error_code",
                "verified_at",
            }
        ):
            raise ValueError("image_validation_terminal_fields_invalid")
        return await self.cas_put_data(
            data_id=image_id,
            expected_version=expected_version,
            data=terminal,
            v_where=[
                self.model.status == "validating",
                self.model.validation_owner_id == owner,
                self.model.validation_lease_generation == lease_generation,
                self.model.validation_lease_expires_at > finished_at,
            ],
        )

    async def recover_expired_validation_lease(
        self,
        *,
        image_id: str,
        expected_version: int,
        lease_generation: int,
        now: datetime,
        max_attempts: int,
    ) -> Image | None:
        if lease_generation < 1 or max_attempts < 1:
            raise ValueError("image_validation_recovery_invalid")
        image = await self.get_data(
            data_id=image_id,
            v_return_none=True,
            v_expire_all=True,
        )
        if image is None or image.validation_attempt_count < 1:
            return None
        exhausted = image.validation_attempt_count >= max_attempts
        data: dict[str, Any] = {
            "validation_owner_id": None,
            "validation_lease_expires_at": None,
            "validation_heartbeat_at": None,
            "next_validation_at": None if exhausted else now,
            "error_code": (
                "validation_attempts_exhausted" if exhausted else "validation_lease_expired"
            ),
        }
        if exhausted:
            data.update(
                {
                    "status": "quarantined",
                    "state_version": expected_version + 1,
                }
            )
        recovered = await self.conditional_update(
            v_where=[
                self.model.id == image_id,
                self.model.status == "validating",
                self.model.state_version == expected_version,
                self.model.validation_lease_generation == lease_generation,
                self.model.validation_lease_expires_at <= now,
            ],
            data=data,
        )
        if not recovered:
            return None
        return await self.get_data(
            data_id=image_id,
            v_return_none=True,
            v_expire_all=True,
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
