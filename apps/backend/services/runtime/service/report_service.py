import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.crud.report import ReportDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.crud.task import TaskDal
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.report import ReportResponse


class ReportServiceError(ValueError):
    pass


class ReportNotFoundError(ReportServiceError):
    pass


class ReportStateConflictError(ReportServiceError):
    pass


class ReportService:
    def __init__(self, db: AsyncSession):
        self.report_dal = ReportDal(db)
        self.task_dal = TaskDal(db)
        self.stage_dal = StageCheckpointDal(db)

    @staticmethod
    def _response(report) -> ReportResponse:
        return ReportResponse.model_validate(report)

    async def finalize(self, *, task_id: str, finalization_stage_id: str, source_call_id: str | None, medical_status: str, content: dict[str, Any]) -> ReportResponse | None:
        task = await self.task_dal.get_by_id(task_id)
        stage = await self.stage_dal.get_by_id(finalization_stage_id)
        if task is None or stage is None or stage.task_id != task.id or stage.stage_key != "decision_finalization":
            raise ReportStateConflictError("report_finalization_source_invalid")
        if task.report_required is False:
            return None
        reports = await self.report_dal.list_for_task(task.id)
        revision = (reports[0].revision_no + 1) if reports else 1
        content_sha = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        report = await self.report_dal.create_idempotent({
            "id": new_opaque_id(), "task_id": task.id, "revision_no": revision,
            "source_stage_checkpoint_id": stage.id, "source_call_id": source_call_id,
            "medical_status": medical_status, "content_json": content,
            "content_sha256": content_sha, "status": "final",
        })
        if report is None:
            raise ReportStateConflictError("report_revision_conflict")
        if reports:
            previous = reports[0]
            superseded = await self.report_dal.cas_update(report_id=previous.id, expected_version=previous.state_version, values={"status": "superseded"})
            if superseded is None:
                raise ReportStateConflictError("report_supersede_conflict")
        updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"current_report_id": report.id, "execution_status": "completed", "ai_medical_status": medical_status, "finished_at": datetime.utcnow()})
        if updated is None:
            raise ReportStateConflictError("report_task_pointer_conflict")
        return self._response(report)

    async def get_current(self, *, task_id: str) -> ReportResponse | None:
        task = await self.task_dal.get_by_id(task_id)
        if task is None:
            raise ReportNotFoundError("task_not_found")
        if task.current_report_id is None:
            return None
        report = await self.report_dal.get_by_id(task.current_report_id)
        if report is None or report.task_id != task.id or report.status not in {"final", "published"}:
            raise ReportStateConflictError("current_report_invalid")
        return self._response(report)

    async def get_for_requester(self, *, report_id: str, requester_id: str) -> ReportResponse:
        report = await self.report_dal.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundError("report_not_found")
        task = await self.task_dal.get_by_id(report.task_id)
        if task is None or task.requester_id != requester_id:
            raise ReportNotFoundError("report_not_found")
        return self._response(report)

    async def list_for_requester(self, *, task_id: str, requester_id: str) -> list[ReportResponse]:
        task = await self.task_dal.get_by_id(task_id)
        if task is None or task.requester_id != requester_id:
            raise ReportNotFoundError("task_not_found")
        return [self._response(item) for item in await self.report_dal.list_for_task(task.id)]

    async def publish(self, *, report_id: str, expected_version: int) -> ReportResponse:
        report = await self.report_dal.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundError("report_not_found")
        task = await self.task_dal.get_by_id(report.task_id)
        if task is None or task.current_report_id != report.id or report.status != "final":
            raise ReportStateConflictError("report_publish_conflict")
        updated = await self.report_dal.cas_update(report_id=report.id, expected_version=expected_version, values={"status": "published", "published_at": datetime.utcnow()})
        if updated is None:
            raise ReportStateConflictError("report_publish_conflict")
        return self._response(updated)

    async def void(self, *, report_id: str, expected_version: int) -> ReportResponse:
        report = await self.report_dal.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundError("report_not_found")
        task = await self.task_dal.get_by_id(report.task_id)
        if task is None or task.current_report_id != report.id or report.status not in {"final", "published"}:
            raise ReportStateConflictError("report_void_conflict")
        updated = await self.report_dal.cas_update(report_id=report.id, expected_version=expected_version, values={"status": "void", "voided_at": datetime.utcnow()})
        if updated is None:
            raise ReportStateConflictError("report_void_conflict")
        task_updated = await self.task_dal.cas_update(task_id=task.id, expected_version=task.state_version, values={"current_report_id": None})
        if task_updated is None:
            raise ReportStateConflictError("report_void_task_pointer_conflict")
        return self._response(updated)
