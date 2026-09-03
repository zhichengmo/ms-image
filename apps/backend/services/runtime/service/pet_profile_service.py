from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.pet_profile import PetProfileDal
from apps.backend.crud.pet_profile_history import PetProfileHistoryDal
from apps.backend.models.pet_profile import PetProfile
from apps.backend.schemas.pet_profile import (
    PET_PROFILE_MUTABLE_FIELDS,
    PetProfileCreate,
    PetProfileHistoryPageResult,
    PetProfileHistoryQuery,
    PetProfileHistoryResponse,
    PetProfilePageQuery,
    PetProfilePageResult,
    PetProfileResponse,
    PetProfileUpdateCommand,
)


class PetProfileServiceError(ValueError):
    pass


class PetProfileNotFoundError(PetProfileServiceError):
    pass


class PetProfileAccessDeniedError(PetProfileServiceError):
    pass


class PetProfileIdempotencyConflictError(PetProfileServiceError):
    pass


class PetProfileStateConflictError(PetProfileServiceError):
    pass


class PetProfileService:
    def __init__(self, db: AsyncSession):
        self.pet_profile_dal = PetProfileDal(db)
        self.history_dal = PetProfileHistoryDal(db)

    @staticmethod
    def _response(profile: PetProfile) -> PetProfileResponse:
        return PetProfileResponse.model_validate(profile)

    @classmethod
    def _snapshot(cls, profile: PetProfile) -> dict[str, Any]:
        return cls._response(profile).model_dump(mode="json")

    @staticmethod
    def _create_values(payload: PetProfileCreate, owner_id: str) -> dict[str, Any]:
        return {
            **payload.model_dump(),
            "owner_id": owner_id,
            "status": "active",
            "state_version": 0,
        }

    @staticmethod
    def _matches_create(
        profile: PetProfile, values: dict[str, Any], *, include_request_id: bool
    ) -> bool:
        fields = tuple(PetProfileCreate.model_fields)
        if not include_request_id:
            fields = tuple(field for field in fields if field != "request_id")
        return profile.owner_id == values["owner_id"] and all(
            getattr(profile, field) == values[field] for field in fields
        )

    async def _record_history(
        self,
        *,
        profile: PetProfile,
        field_name: str,
        old_value: Any,
        new_value: Any,
        operation_type: str,
        operator_id: str,
        remark: str | None = None,
    ) -> None:
        await self.history_dal.create_history(
            {
                "pet_profile_id": profile.id,
                "data_type": "profile",
                "field_name": field_name,
                "old_value_json": jsonable_encoder(old_value),
                "new_value_json": jsonable_encoder(new_value),
                "operation_type": operation_type,
                "operator_id": operator_id,
                "snapshot_json": self._snapshot(profile),
                "remark": remark,
            }
        )

    async def create_profile(
        self, *, payload: PetProfileCreate, owner_id: str
    ) -> PetProfileResponse:
        normalized_owner = owner_id.strip()
        values = self._create_values(payload, normalized_owner)
        created = await self.pet_profile_dal.create_idempotent(values)
        if created is not None:
            await self._record_history(
                profile=created,
                field_name="*",
                old_value=None,
                new_value={"status": "active"},
                operation_type="create",
                operator_id=normalized_owner,
            )
            return self._response(created)

        existing = await self.pet_profile_dal.get_by_request_id(payload.request_id)
        if existing is not None:
            if self._matches_create(existing, values, include_request_id=True):
                return self._response(existing)
            raise PetProfileIdempotencyConflictError("pet_profile_request_conflict")

        if payload.source_system is not None and payload.source_pet_id is not None:
            existing = await self.pet_profile_dal.get_by_source(
                source_system=payload.source_system,
                source_pet_id=payload.source_pet_id,
            )
            if existing is not None and self._matches_create(
                existing, values, include_request_id=False
            ):
                return self._response(existing)
        raise PetProfileIdempotencyConflictError("pet_profile_source_conflict")

    async def get_profile(
        self, *, pet_profile_id: str, owner_id: str
    ) -> PetProfileResponse:
        return self._response(
            await self._owned_profile(
                pet_profile_id=pet_profile_id,
                owner_id=owner_id,
            )
        )

    async def page_profiles(
        self, *, query: PetProfilePageQuery, owner_id: str
    ) -> PetProfilePageResult:
        rows, total = await self.pet_profile_dal.page_for_owner(
            owner_id=owner_id.strip(),
            status=query.status,
            species=query.species,
            query_key=query.query_key,
            page=query.page,
            limit=query.page_size,
        )
        return PetProfilePageResult(
            data=[self._response(row) for row in rows],
            total=total,
            page=query.page,
            limit=query.page_size,
        )

    async def update_profile(
        self, *, payload: PetProfileUpdateCommand, owner_id: str
    ) -> PetProfileResponse:
        normalized_owner = owner_id.strip()
        profile = await self._owned_profile_for_update(
            pet_profile_id=payload.id,
            owner_id=normalized_owner,
        )
        if profile.status != "active":
            raise PetProfileStateConflictError("pet_profile_not_active")
        if profile.state_version != payload.expected_state_version:
            raise PetProfileStateConflictError("pet_profile_state_conflict")

        requested = payload.model_dump(
            include=PET_PROFILE_MUTABLE_FIELDS,
            exclude_unset=True,
        )
        changed = {
            field: value
            for field, value in requested.items()
            if getattr(profile, field) != value
        }
        if not changed:
            return self._response(profile)

        old_values = {field: getattr(profile, field) for field in changed}
        updated = await self.pet_profile_dal.cas_update(
            pet_profile_id=profile.id,
            expected_version=payload.expected_state_version,
            values=changed,
        )
        if updated is None:
            raise PetProfileStateConflictError("pet_profile_state_conflict")
        for field, new_value in changed.items():
            await self._record_history(
                profile=updated,
                field_name=field,
                old_value=old_values[field],
                new_value=new_value,
                operation_type="update",
                operator_id=normalized_owner,
            )
        return self._response(updated)

    async def archive_profile(
        self,
        *,
        pet_profile_id: str,
        owner_id: str,
        expected_state_version: int,
        archive_reason: str,
    ) -> PetProfileResponse:
        normalized_owner = owner_id.strip()
        normalized_reason = archive_reason.strip()
        profile = await self._owned_profile_for_update(
            pet_profile_id=pet_profile_id,
            owner_id=normalized_owner,
        )
        if profile.status == "archived":
            if profile.archive_reason == normalized_reason:
                return self._response(profile)
            raise PetProfileStateConflictError("pet_profile_archive_conflict")
        if (
            profile.status != "active"
            or profile.state_version != expected_state_version
        ):
            raise PetProfileStateConflictError("pet_profile_state_conflict")

        previous_status = profile.status
        updated = await self.pet_profile_dal.cas_update(
            pet_profile_id=profile.id,
            expected_version=expected_state_version,
            values={
                "status": "archived",
                "archived_at": datetime.now(UTC).replace(tzinfo=None),
                "archived_by_id": normalized_owner,
                "archive_reason": normalized_reason,
            },
        )
        if updated is None:
            raise PetProfileStateConflictError("pet_profile_state_conflict")
        await self._record_history(
            profile=updated,
            field_name="status",
            old_value=previous_status,
            new_value="archived",
            operation_type="archive",
            operator_id=normalized_owner,
            remark=normalized_reason,
        )
        return self._response(updated)

    async def restore_profile(
        self,
        *,
        pet_profile_id: str,
        owner_id: str,
        expected_state_version: int,
    ) -> PetProfileResponse:
        normalized_owner = owner_id.strip()
        profile = await self._owned_profile_for_update(
            pet_profile_id=pet_profile_id,
            owner_id=normalized_owner,
        )
        if profile.status == "active":
            return self._response(profile)
        if (
            profile.status != "archived"
            or profile.state_version != expected_state_version
        ):
            raise PetProfileStateConflictError("pet_profile_state_conflict")

        previous_status = profile.status
        updated = await self.pet_profile_dal.cas_update(
            pet_profile_id=profile.id,
            expected_version=expected_state_version,
            values={
                "status": "active",
                "archived_at": None,
                "archived_by_id": None,
                "archive_reason": None,
            },
        )
        if updated is None:
            raise PetProfileStateConflictError("pet_profile_state_conflict")
        await self._record_history(
            profile=updated,
            field_name="status",
            old_value=previous_status,
            new_value="active",
            operation_type="restore",
            operator_id=normalized_owner,
        )
        return self._response(updated)

    async def page_history(
        self, *, query: PetProfileHistoryQuery, owner_id: str
    ) -> PetProfileHistoryPageResult:
        await self._owned_profile(
            pet_profile_id=query.pet_profile_id,
            owner_id=owner_id,
        )
        rows, total = await self.history_dal.page_for_profile(
            pet_profile_id=query.pet_profile_id,
            operation_type=query.operation_type,
            page=query.page,
            limit=query.page_size,
        )
        return PetProfileHistoryPageResult(
            data=[PetProfileHistoryResponse.model_validate(row) for row in rows],
            total=total,
            page=query.page,
            limit=query.page_size,
        )

    async def _owned_profile(self, *, pet_profile_id: str, owner_id: str) -> PetProfile:
        profile = await self.pet_profile_dal.get_by_id(pet_profile_id.strip())
        if profile is None:
            raise PetProfileNotFoundError("pet_profile_not_found")
        if profile.owner_id != owner_id.strip():
            raise PetProfileAccessDeniedError("pet_profile_access_denied")
        return profile

    async def _owned_profile_for_update(
        self, *, pet_profile_id: str, owner_id: str
    ) -> PetProfile:
        profile = await self.pet_profile_dal.get_by_id_for_update(
            pet_profile_id.strip()
        )
        if profile is None:
            raise PetProfileNotFoundError("pet_profile_not_found")
        if profile.owner_id != owner_id.strip():
            raise PetProfileAccessDeniedError("pet_profile_access_denied")
        return profile


__all__ = [
    "PetProfileAccessDeniedError",
    "PetProfileIdempotencyConflictError",
    "PetProfileNotFoundError",
    "PetProfileService",
    "PetProfileServiceError",
    "PetProfileStateConflictError",
]
