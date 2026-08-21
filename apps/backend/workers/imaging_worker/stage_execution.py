from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.backend.services.runtime.service.imaging_execution_service import ImagingExecutionService, StageExecutionStateConflict


class StageExecutionWorker:
    def __init__(self, *, session_factory_: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory_

    async def execute(self, *, event_id: str, message: dict, message_version: str, trace_id: str, owner_id: str, lease_seconds: int) -> dict:
        async with self.session_factory() as session:
            async with session.begin():
                stage = await ImagingExecutionService(session).claim(event_id=event_id, message=message, message_version=message_version, trace_id=trace_id, owner_id=owner_id, lease_seconds=lease_seconds)
        if stage is None:
            return {"outcome": "already_applied", "event_id": event_id}
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    service = ImagingExecutionService(session)
                    handler = {
                        "study_preparation": service.complete_study_preparation,
                        "joint_primary_reader": service.complete_joint_primary_reader,
                        "family_routing": service.complete_family_routing,
                        "targeted_review": service.complete_targeted_review,
                        "decision_finalization": service.complete_decision_finalization,
                    }.get(stage.stage_key)
                    if handler is None:
                        raise StageExecutionStateConflict("stage_handler_not_implemented")
                    output = await handler(stage=stage, owner_id=owner_id)
        except StageExecutionStateConflict as exc:
            return {"outcome": "conflict", "event_id": event_id, "error_code": str(exc)}
        return {"outcome": "completed", "event_id": event_id, "output_sha256": __import__('hashlib').sha256(__import__('json').dumps(output, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
