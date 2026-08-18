from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import DalBase
from app.models.xray_accuracy.stage_checkpoint import XRayStageCheckpoint


class XRayStageCheckpointDal(DalBase):
    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=XRayStageCheckpoint)

    async def create_checkpoint(self, values: dict) -> XRayStageCheckpoint:
        return await self.create_data(values, v_return_obj=True)

    async def get_by_id(self, checkpoint_id: str, tenant_id: str) -> XRayStageCheckpoint | None:
        return await self.get_data(
            data_id=checkpoint_id,
            v_where=[self.model.tenant_id == tenant_id],
            v_return_none=True,
        )

    async def get_by_attempt_id(
        self,
        *,
        run_id: str,
        tenant_id: str,
        attempt_id: str,
    ) -> XRayStageCheckpoint | None:
        return await self.get_data(
            v_where=[
                self.model.run_id == run_id,
                self.model.tenant_id == tenant_id,
                self.model.attempt_id == attempt_id,
            ],
            v_return_none=True,
        )

    async def list_for_tenant_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        limit: int = 100,
    ) -> list[XRayStageCheckpoint]:
        """Return a bounded, tenant-scoped technical execution view."""
        if limit <= 0:
            raise ValueError("checkpoint_list_limit_invalid")
        return await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.run_id == run_id,
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )

    async def cancel_for_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        finished_at: datetime,
    ) -> dict[str, int]:
        """Close not-yet-final stages when a Run is cancelled.

        Queued/retry work is cancelled before it can start.  Work already
        owned by a worker is recorded as late so a provider result can never
        become a final writer after the Run CAS reaches ``cancelled``.
        """
        rows = await self.get_datas(
            page=1,
            limit=100,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.run_id == run_id,
                self.model.status.in_(["queued", "retry", "running"]),
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )
        result = {"cancelled": 0, "late": 0}
        for row in rows:
            next_status = "late" if row.status == "running" else "cancelled"
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.tenant_id == tenant_id,
                    self.model.run_id == run_id,
                    self.model.status == row.status,
                ],
                data={
                    "status": next_status,
                    "error_class": "late_result" if next_status == "late" else "cancelled",
                    "finished_at": finished_at,
                    "owner_id": None,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                },
            )
            if changed:
                result[next_status] += 1
        return result

    async def claim_checkpoint(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        owner_id: str,
        expected_version: int,
        lease_expires_at: datetime,
        started_at: datetime,
    ) -> XRayStageCheckpoint | None:
        if not owner_id.strip() or lease_expires_at <= started_at:
            raise ValueError("checkpoint_lease_invalid")
        claimed = await self.conditional_update(
            v_where=[
                self.model.id == checkpoint_id,
                self.model.tenant_id == tenant_id,
                self.model.expected_version == expected_version,
                self.model.status.in_(["queued", "retry"]),
                self.model.owner_id.is_(None),
            ],
            data={
                "status": "running",
                "owner_id": owner_id,
                "lease_expires_at": lease_expires_at,
                "heartbeat_at": started_at,
                "started_at": started_at,
                "finished_at": None,
                "error_class": None,
                "output_hash": None,
            },
        )
        if not claimed:
            return None
        return await self.get_by_id(checkpoint_id, tenant_id)

    async def heartbeat_checkpoint(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        owner_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        return await self.conditional_update(
            v_where=[
                self.model.id == checkpoint_id,
                self.model.tenant_id == tenant_id,
                self.model.status == "running",
                self.model.owner_id == owner_id,
                self.model.lease_expires_at > heartbeat_at,
            ],
            data={"heartbeat_at": heartbeat_at, "lease_expires_at": lease_expires_at},
        )

    async def complete_checkpoint(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        owner_id: str,
        finished_at: datetime,
        output_hash: str | None = None,
    ) -> bool:
        return await self.conditional_update(
            v_where=[
                self.model.id == checkpoint_id,
                self.model.tenant_id == tenant_id,
                self.model.status == "running",
                self.model.owner_id == owner_id,
                self.model.lease_expires_at > finished_at,
            ],
            data={
                "status": "completed",
                "output_hash": output_hash,
                "finished_at": finished_at,
                "owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            },
        )

    async def mark_late(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        finished_at: datetime,
    ) -> bool:
        """Record a result observed after cancel/terminal state without CAS advancement."""
        return await self.conditional_update(
            v_where=[
                self.model.id == checkpoint_id,
                self.model.tenant_id == tenant_id,
                self.model.status.in_(["queued", "retry", "running"]),
            ],
            data={
                "status": "late",
                "error_class": "late_result",
                "finished_at": finished_at,
                "owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            },
        )

    async def fail_checkpoint(
        self,
        *,
        checkpoint_id: str,
        tenant_id: str,
        owner_id: str,
        finished_at: datetime,
        error_class: str,
        retryable: bool,
    ) -> bool:
        status = "retry" if retryable else "failed"
        return await self.conditional_update(
            v_where=[
                self.model.id == checkpoint_id,
                self.model.tenant_id == tenant_id,
                self.model.status == "running",
                self.model.owner_id == owner_id,
                self.model.lease_expires_at > finished_at,
            ],
            data={
                "status": status,
                "error_class": error_class,
                "finished_at": finished_at,
                "owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            },
        )

    async def recover_expired(
        self,
        *,
        tenant_id: str,
        now: datetime,
        limit: int = 100,
    ) -> int:
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.tenant_id == tenant_id,
                self.model.status == "running",
                self.model.owner_id.is_not(None),
                self.model.lease_expires_at <= now,
            ],
            v_return_objs=True,
        )
        recovered = 0
        for row in rows:
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.tenant_id == tenant_id,
                    self.model.status == "running",
                    self.model.owner_id == row.owner_id,
                    self.model.lease_expires_at <= now,
                ],
                data={
                    "status": "retry",
                    "error_class": "lease_expired",
                    "owner_id": None,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                },
            )
            recovered += int(changed)
        return recovered

    async def recover_expired_global(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> dict[str, int]:
        """Recover running checkpoints without relying on a tenant list.

        The relay/reconciler is an internal process and must recover a lost
        worker lease even when the worker never got far enough to emit an
        Outbox transition.  The tenant is still taken from each immutable row;
        no caller-supplied tenant is trusted.
        """
        if limit <= 0:
            raise ValueError("checkpoint_recovery_limit_invalid")
        rows = await self.get_datas(
            page=1,
            limit=limit,
            v_where=[
                self.model.status == "running",
                self.model.owner_id.is_not(None),
                self.model.lease_expires_at <= now,
            ],
            v_order="asc",
            v_order_field="created_at",
            v_return_objs=True,
        )
        recovered = {"retry": 0, "late": 0}
        for row in rows:
            changed = await self.conditional_update(
                v_where=[
                    self.model.id == row.id,
                    self.model.status == "running",
                    self.model.owner_id == row.owner_id,
                    self.model.lease_expires_at <= now,
                ],
                data={
                    "status": "retry",
                    "error_class": "lease_expired",
                    "owner_id": None,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                },
            )
            recovered["retry"] += int(changed)
        return recovered
