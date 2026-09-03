from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.pet_info import PetInfoDal
from apps.backend.schemas.pet_info import (
    PetInfoCatalogResponse,
    PetInfoGroupResponse,
    PetInfoQuery,
    PetInfoResponse,
)


class PetInfoService:
    def __init__(self, db: AsyncSession):
        self.pet_info_dal = PetInfoDal(db)

    async def get_catalog(self, *, query: PetInfoQuery) -> PetInfoCatalogResponse:
        rows = await self.pet_info_dal.search_catalog(
            species=query.species,
            query_key=query.query_key,
        )
        items = [PetInfoResponse.model_validate(row) for row in rows]
        if not query.group_by_first_letter:
            return PetInfoCatalogResponse(
                species=query.species,
                grouped=False,
                total=len(items),
                items=items,
            )

        grouped: dict[str, list[PetInfoResponse]] = defaultdict(list)
        for item in items:
            letter = item.first_letter.strip().upper() or "#"
            grouped[letter].append(item)
        groups = [
            PetInfoGroupResponse(first_letter=letter, items=grouped[letter])
            for letter in sorted(grouped)
        ]
        return PetInfoCatalogResponse(
            species=query.species,
            grouped=True,
            total=len(items),
            groups=groups,
        )


__all__ = ["PetInfoService"]
