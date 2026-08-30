from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from apps.backend.core.crud import DalBase
from apps.backend.models.study import Study
from apps.backend.models.task import Task


class TaskDal(DalBase):
    TERMINAL_EXECUTION_STATUSES = frozenset(
        {"completed", "failed", "cancelled", "dead_letter"}
    )

    def __init__(self, db: AsyncSession):
        super().__init__(db=db, model=Task)

    async def create_idempotent(self, values: dict[str, Any]) -> Task | None:
        try:
            async with self.db.begin_nested():
                return await self.create_data(values, v_return_obj=True)
        except IntegrityError as exc:
            detail = str(getattr(exc, "orig", exc)).casefold()
            if "uq_task_record_business_key" not in detail and "duplicate" not in detail:
                raise
            return None

    async def get_by_id(self, task_id: str) -> Task | None:
        return await self.get_data(data_id=task_id, v_return_none=True)

    async def get_by_id_for_update(self, task_id: str) -> Task | None:
        """Read the current Task row under a row lock for budget reservation."""
        return await self.get_data(
            data_id=task_id,
            v_start_sql=select(self.model).with_for_update().execution_options(
                populate_existing=True
            ),
            v_return_none=True,
        )

    async def get_by_business_key(self, business_key: str) -> Task | None:
        return await self.get_data(business_key=business_key, v_return_none=True)

    async def list_non_terminal_for_session(
        self, *, session_id: str, for_update: bool = False
    ) -> list[Task]:
        statement = (
            select(self.model)
            .join(Study, self.model.study_id == Study.id)
            .where(
                Study.session_id == session_id,
                self.model.execution_status.notin_(
                    tuple(self.TERMINAL_EXECUTION_STATUSES)
                ),
            )
            .order_by(self.model.id.asc())
        )
        if for_update:
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        return await self.get_datas(
            limit=0,
            v_start_sql=statement,
            v_return_objs=True,
        )

    async def page_for_owner(
        self,
        *,
        requester_id: str,
        session_id: str | None,
        study_id: str | None,
        execution_status: str | None,
        task_type: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        page: int,
        limit: int,
    ) -> tuple[list[Task], int]:
        if page < 1 or limit < 1 or limit > 100:
            raise ValueError("task_page_invalid")
        if session_id is None and study_id is None:
            raise ValueError("task_page_scope_required")

        where = [self.model.requester_id == requester_id]
        joins = None
        if session_id is not None:
            joins = [(Study, self.model.study_id == Study.id)]
            where.append(Study.session_id == session_id)
        if study_id is not None:
            where.append(self.model.study_id == study_id)
        if execution_status is not None:
            where.append(self.model.execution_status == execution_status)
        if task_type is not None:
            where.append(self.model.task_type == task_type)
        if created_from is not None:
            where.append(self.model.created_at >= created_from)
        if created_to is not None:
            where.append(self.model.created_at <= created_to)

        start = select(self.model).order_by(
            self.model.created_at.desc(),
            self.model.id.desc(),
        )
        rows, total = await self.get_datas(
            page=page,
            limit=limit,
            v_start_sql=start,
            v_join=joins,
            v_where=where,
            v_options=[
                load_only(
                    self.model.id,
                    self.model.study_id,
                    self.model.request_id,
                    self.model.task_type,
                    self.model.study_revision_id,
                    self.model.run_mode,
                    self.model.execution_status,
                    self.model.ai_medical_status,
                    self.model.state_version,
                    self.model.current_report_id,
                    self.model.trace_id,
                    self.model.error_code,
                    self.model.next_retry_at,
                    self.model.cancel_requested_at,
                    self.model.started_at,
                    self.model.finished_at,
                    self.model.created_at,
                    self.model.updated_at,
                )
            ],
            v_return_count=True,
            v_return_objs=True,
        )
        return rows, total

    async def cas_update(
        self, *, task_id: str, expected_version: int, values: dict[str, Any]
    ) -> Task | None:
        allowed = {
            "execution_status",
            "ai_medical_status",
            "budget_reserved_json",
            "budget_consumed_json",
            "current_report_id",
            "next_retry_at",
            "error_code",
            "error_message",
            "cancel_requested_by_id",
            "cancel_reason",
            "cancel_requested_at",
            "started_at",
            "finished_at",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("task_update_fields_invalid")
        return await self.cas_put_data(
            data_id=task_id, expected_version=expected_version, data=values
        )


__all__ = ["TaskDal"]
