from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.evaluation import EvaluationArtifact, EvaluationJob, EvaluationOutbox, EvaluationRun


class EvaluationJobDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationJob)
    async def create_idempotent(self, values: dict[str, Any]):
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError:
            return None
    async def get_by_id(self, job_id: str):
        return await self.get_data(data_id=job_id, v_return_none=True)
    async def get_by_business_key(self, key: str):
        return await self.get_data(business_key=key, v_return_none=True)
    async def cas_update(self, *, job_id: str, expected_version: int, values: dict[str, Any]):
        allowed={"status","error_code"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("evaluation_job_update_fields_invalid")
        return await self.cas_put_data(data_id=job_id, expected_version=expected_version, data=values)


class EvaluationOutboxDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationOutbox)
    async def create_idempotent(self, values: dict[str, Any]):
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError:
            return None


class EvaluationRunDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationRun)
    async def create_idempotent(self, values: dict[str, Any]):
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError:
            return None
    async def get_by_id(self, run_id: str):
        return await self.get_data(data_id=run_id, v_return_none=True)
    async def list_for_job(self, job_id: str):
        return await self.get_datas(limit=0, job_id=job_id, v_order_field="run_no", v_return_objs=True)


class EvaluationArtifactDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=EvaluationArtifact)
    async def create_append_only(self, values: dict[str, Any]):
        return await self.create_data(values, v_return_obj=True)
    async def get_by_id(self, artifact_id: str):
        return await self.get_data(data_id=artifact_id, v_return_none=True)
    async def list_for_job(self, job_id: str):
        return await self.get_datas(limit=0, job_id=job_id, v_order_field="created_at", v_return_objs=True)


__all__=["EvaluationArtifactDal","EvaluationJobDal","EvaluationOutboxDal","EvaluationRunDal"]
