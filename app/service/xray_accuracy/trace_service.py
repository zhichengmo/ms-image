from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.xray_accuracy import XRayTraceEventDal


class XRayTraceService:
    def __init__(self, db: AsyncSession):
        self.trace_dal = XRayTraceEventDal(db)

    async def list_trace(self, *, tenant_id: str, run_id: str, page: int, limit: int):
        return await self.trace_dal.list_for_tenant_run(
            tenant_id=tenant_id, run_id=run_id, page=page, limit=limit
        )
