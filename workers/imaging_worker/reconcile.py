"""Bounded reconciliation for incomplete Image ingestion and validation."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.async_db import async_engine, session_factory
from app.core.config import settings
from app.core.imaging.object_store import (
    OSSObjectStore,
    ObjectStorageGateway,
    ObjectStoreError,
)
from app.core.messaging.config import runtime_config
from app.service.image_service import ImageService, ImageStateConflictError

from .image_validation import ImageValidationWorker


class ImageReconciler:
    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession],
        gateway_factory: Callable[[], ObjectStorageGateway] = OSSObjectStore,
    ):
        self.session_factory = session_factory_
        self.gateway_factory = gateway_factory

    async def run_once(
        self,
        *,
        limit: int,
        lease_seconds: int,
        max_attempts: int,
        ready_image_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("image_reconcile_limit_invalid")
        now = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                expired = await ImageService(session).recover_expired_validation_leases(
                    now=now,
                    limit=limit,
                    max_attempts=max_attempts,
                )
        async with self.session_factory() as session:
            async with session.begin():
                events = await ImageService(session).list_validation_reconcile_events(
                    now=now,
                    limit=limit,
                )

        worker = ImageValidationWorker(
            session_factory_=self.session_factory,
            gateway_factory=self.gateway_factory,
        )
        validation_outcomes: dict[str, int] = {}
        for event in events:
            result = await worker.execute(
                event_id=event.event_id,
                message=event.message,
                message_version=event.message_version,
                header_trace_id=event.trace_id,
                owner_id=f"reconcile:{event.event_id}"[:128],
                lease_seconds=lease_seconds,
                max_attempts=max_attempts,
            )
            outcome = str(result.get("outcome") or "unknown")
            validation_outcomes[outcome] = validation_outcomes.get(outcome, 0) + 1

        async with self.session_factory() as session:
            async with session.begin():
                uploads = await ImageService(session).list_expired_upload_candidates(
                    now=now,
                    limit=limit,
                )
        upload_outcomes = {"accepted": 0, "missing": 0, "retry": 0, "conflicted": 0}
        gateway: ObjectStorageGateway | None = None
        for candidate in uploads:
            try:
                gateway = gateway or self.gateway_factory()
                if gateway.storage_profile != candidate.storage_profile:
                    raise ObjectStoreError("object_storage_profile_mismatch")
                head = await gateway.head_object(object_key=candidate.object_key)
            except ObjectStoreError as exc:
                code = self._safe_error_code(exc)
                if code == "object_not_found":
                    async with self.session_factory() as session:
                        async with session.begin():
                            changed = await ImageService(session).quarantine_expired_upload(
                                image_id=candidate.image_id,
                                expected_state_version=candidate.state_version,
                                error_code="upload_expired_object_missing",
                                now=now,
                            )
                    upload_outcomes["missing" if changed else "conflicted"] += 1
                else:
                    upload_outcomes["retry"] += 1
                continue
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        await ImageService(session).accept_reconciled_upload(
                            image_id=candidate.image_id,
                            expected_state_version=candidate.state_version,
                            object_head=head,
                            trace_id=(
                                f"reconcile:{candidate.image_id}:{candidate.state_version}"
                            ),
                        )
            except ImageStateConflictError:
                async with self.session_factory() as session:
                    async with session.begin():
                        changed = await ImageService(session).quarantine_expired_upload(
                            image_id=candidate.image_id,
                            expected_state_version=candidate.state_version,
                            error_code="upload_reconcile_head_conflict",
                            now=now,
                        )
                upload_outcomes["conflicted" if changed else "retry"] += 1
            else:
                upload_outcomes["accepted"] += 1

        ready_outcomes: dict[str, int] = {}
        for image_id in ready_image_ids:
            outcome = await self.verify_ready_image(image_id=image_id)
            ready_outcomes[outcome] = ready_outcomes.get(outcome, 0) + 1
        return {
            "expired_leases": expired,
            "validation": validation_outcomes,
            "uploads": upload_outcomes,
            "ready": ready_outcomes,
        }

    async def verify_ready_image(self, *, image_id: str) -> str:
        async with self.session_factory() as session:
            async with session.begin():
                candidate = await ImageService(session).get_ready_object_candidate(
                    image_id=image_id
                )
        if candidate is None:
            return "not_ready"
        try:
            gateway = self.gateway_factory()
            if gateway.storage_profile != candidate.storage_profile:
                raise ObjectStoreError("object_storage_profile_mismatch")
            await gateway.validate_image_object(
                object_key=candidate.object_key,
                file_format=candidate.file_format,
                declared_content_type=candidate.declared_content_type,
                expected_sha256=candidate.expected_sha256,
                expected_size_bytes=candidate.expected_size_bytes,
                expected_object_version_id=candidate.object_version_id,
            )
        except ObjectStoreError as exc:
            code = self._safe_error_code(exc)
            if code in {
                "object_store_not_configured",
                "object_store_head_failed",
                "object_store_download_failed",
            }:
                return "retry"
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        changed = await ImageService(session).invalidate_ready_image(
                            image_id=candidate.image_id,
                            expected_state_version=candidate.state_version,
                            error_code=f"ready_{code}"[:80],
                            changed_at=datetime.utcnow(),
                        )
            except ImageStateConflictError:
                return "retry"
            return "invalidated" if changed else "conflicted"
        return "consistent"

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        code = str(exc).strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "image_reconcile_error"
        return code


async def _main(limit: int, ready_image_ids: Sequence[str]) -> None:
    runtime = runtime_config(source=settings, prefix="IMAGING")
    try:
        result = await ImageReconciler(
            session_factory_=session_factory,
        ).run_once(
            limit=limit,
            lease_seconds=runtime.worker_lease_seconds,
            max_attempts=runtime.max_attempts,
            ready_image_ids=ready_image_ids,
        )
        print(result)
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--ready-image-id", action="append", default=[])
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.ready_image_id))


__all__ = ["ImageReconciler"]
