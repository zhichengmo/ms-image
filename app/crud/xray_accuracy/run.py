from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.request_snapshot import XRayRequestSnapshot
from app.models.xray_accuracy.run import XRayRun


class XRayRunDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayRun)

    async def get_by_id(self, run_id: str, tenant_id: str) -> XRayRun | None:
        return await self.get_data(
            data_id=run_id,
            v_where=[self.model.tenant_id == tenant_id],
            v_return_none=True,
        )

    async def get_by_id_unscoped(self, run_id: str, tenant_id: str) -> XRayRun | None:
        """Alias kept explicit so callers cannot accidentally omit tenant scope."""
        return await self.get_by_id(run_id, tenant_id)

    async def get_by_request(
        self,
        *,
        tenant_id: str,
        request_id: str,
        contract_version: str,
    ) -> XRayRun | None:
        return await self.get_data(
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.request_id == request_id,
                self.model.contract_version == contract_version,
            ],
            v_return_none=True,
        )

    async def list_for_tenant(
        self, *, tenant_id: str, page: int, limit: int
    ) -> tuple[list[XRayRun], int]:
        rows, count = await self.get_datas(
            page=page,
            limit=limit,
            v_where=[self.model.tenant_id == tenant_id],
            v_order="desc",
            v_order_field="created_at",
            v_return_count=True,
            v_return_objs=True,
        )
        return rows, count

    async def get_latest_for_session_operation(
        self,
        *,
        tenant_id: str,
        session_id: str,
        requested_operation: str,
        study_id: str | None = None,
        study_revision_id: str | None = None,
        execution_statuses: set[str] | None = None,
    ) -> XRayRun | None:
        """Return the newest Run for one logical Session/Study execution.

        ``study_id`` identifies the logical study, while ``study_revision_id``
        identifies the immutable input snapshot. Callers that operate on a
        frozen Study must provide both; otherwise an older revision can be
        selected accidentally. An explicitly empty status set means no row
        matches, which is different from omitting the status filter.
        """
        if not tenant_id or not session_id or not requested_operation:
            raise ValueError("run_lookup_scope_invalid")
        where = []
        joins = None
        if study_revision_id is not None:
            joins = [
                (
                    XRayRequestSnapshot,
                    XRayRequestSnapshot.run_id == self.model.id,
                )
            ]
            where.extend(
                [
                    XRayRequestSnapshot.tenant_id == tenant_id,
                    XRayRequestSnapshot.study_revision == study_revision_id,
                ]
            )
        if execution_statuses is not None:
            if not execution_statuses:
                return None
        return await self.get_data(
            v_join=joins,
            v_where=where or None,
            v_order="desc",
            v_order_field="created_at",
            v_return_none=True,
            tenant_id=tenant_id,
            session_id=session_id,
            requested_operation=requested_operation,
            study_id=study_id,
            execution_status=(
                ("in", sorted(execution_statuses))
                if execution_statuses is not None
                else None
            ),
        )

    async def cas_update(
        self,
        *,
        run_id: str,
        tenant_id: str,
        expected_version: int,
        values: dict[str, Any],
    ) -> XRayRun | None:
        for key, value in values.items():
            if key not in {
                "execution_status",
                "delivery_status",
                "engineering_eligibility",
                "completed_at",
            }:
                raise ValueError(f"Unsupported Run state field: {key}")
        return await self.cas_put_data(
            data_id=run_id,
            expected_version=expected_version,
            data=values,
            v_where=[self.model.tenant_id == tenant_id],
        )

    async def create_idempotent(self, values: dict) -> XRayRun | None:
        """Create under a savepoint so a concurrent unique-key race is recoverable."""
        try:
            async with self.db.begin_nested():
                obj = self.model(**values)
                await self.flush(obj)
            return obj
        except IntegrityError as exc:
            # Only the request idempotency unique key is recoverable.  A
            # missing table, NOT NULL violation, truncation, or any other
            # integrity failure must reach the service as a technical error;
            # otherwise clients would receive a misleading idempotency race.
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_xray_run_tenant_request_contract" not in detail and not (
                ("duplicate" in detail or "unique constraint" in detail)
                and "tenant_id" in detail
                and "request_id" in detail
                and "contract_version" in detail
            ):
                raise
            return None
