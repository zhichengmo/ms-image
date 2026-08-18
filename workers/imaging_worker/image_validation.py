"""Reliable Image validation consumer orchestration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.imaging.object_store import (
    OSSObjectStore,
    ObjectStorageGateway,
    ObjectStoreError,
)
from app.service.image_service import (
    ImageService,
    ImageStateConflictError,
    ImageValidationClaim,
)


_TRANSIENT_OBJECT_ERRORS = frozenset(
    {
        "object_store_not_configured",
        "object_store_head_failed",
        "object_store_download_failed",
    }
)


class ImageValidationWorker:
    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession],
        gateway_factory: Callable[[], ObjectStorageGateway] = OSSObjectStore,
    ):
        self.session_factory = session_factory_
        self.gateway_factory = gateway_factory

    async def execute(
        self,
        *,
        event_id: str,
        message: dict[str, Any],
        message_version: str,
        header_trace_id: str,
        owner_id: str,
        lease_seconds: int,
        max_attempts: int,
    ) -> dict[str, Any]:
        if lease_seconds < 10 or max_attempts < 1:
            raise ValueError("image_worker_runtime_invalid")
        claimed_at = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                claim = await ImageService(session).claim_validation_event(
                    event_id=event_id,
                    message=message,
                    message_version=message_version,
                    header_trace_id=header_trace_id,
                    owner_id=owner_id,
                    claimed_at=claimed_at,
                    lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                    max_attempts=max_attempts,
                )
        if claim.outcome != "claimed":
            return {
                "outcome": claim.outcome,
                "event_id": claim.event_id,
                "image_id": claim.image_id,
            }

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat_loop(
                claim=claim,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
                stop=stop_heartbeat,
                lease_lost=lease_lost,
            )
        )
        try:
            gateway = self.gateway_factory()
            if gateway.storage_profile != claim.storage_profile:
                raise ObjectStoreError("object_storage_profile_mismatch")
            validation = await gateway.validate_image_object(
                object_key=str(claim.object_key),
                file_format=str(claim.file_format),
                declared_content_type=claim.declared_content_type,
                expected_sha256=claim.expected_sha256,
                expected_size_bytes=claim.expected_size_bytes,
                expected_object_version_id=claim.object_version_id,
            )
        except ObjectStoreError as exc:
            stop_heartbeat.set()
            await heartbeat
            if lease_lost.is_set():
                return self._lease_lost(claim)
            return await self._handle_object_error(
                claim=claim,
                owner_id=owner_id,
                error_code=self._safe_error_code(exc),
                max_attempts=max_attempts,
            )
        except Exception:
            stop_heartbeat.set()
            await heartbeat
            if lease_lost.is_set():
                return self._lease_lost(claim)
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code="image_validation_worker_error",
                max_attempts=max_attempts,
            )

        stop_heartbeat.set()
        await heartbeat
        if lease_lost.is_set():
            return self._lease_lost(claim)
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    image = await ImageService(session).complete_validation(
                        claim=claim,
                        owner_id=owner_id,
                        validation=validation,
                        finished_at=datetime.utcnow(),
                    )
        except ImageStateConflictError as exc:
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code=self._safe_error_code(exc),
                max_attempts=max_attempts,
            )
        except Exception:
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code="image_validation_commit_error",
                max_attempts=max_attempts,
            )
        return {
            "outcome": "ready",
            "event_id": claim.event_id,
            "image_id": image.id,
            "state_version": image.state_version,
        }

    async def _heartbeat_loop(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        lease_seconds: int,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = max(1.0, min(30.0, lease_seconds / 3))
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            heartbeat_at = datetime.utcnow()
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        renewed = await ImageService(session).heartbeat_validation_claim(
                            claim=claim,
                            owner_id=owner_id,
                            heartbeat_at=heartbeat_at,
                            lease_expires_at=heartbeat_at
                            + timedelta(seconds=lease_seconds),
                        )
            except Exception:
                renewed = False
            if not renewed:
                lease_lost.set()
                return

    async def _handle_object_error(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        error_code: str,
        max_attempts: int,
    ) -> dict[str, Any]:
        if error_code in _TRANSIENT_OBJECT_ERRORS:
            return await self._schedule_retry(
                claim=claim,
                owner_id=owner_id,
                error_code=error_code,
                max_attempts=max_attempts,
            )
        async with self.session_factory() as session:
            async with session.begin():
                image = await ImageService(session).quarantine_validation(
                    claim=claim,
                    owner_id=owner_id,
                    error_code=error_code,
                    finished_at=datetime.utcnow(),
                )
        return {
            "outcome": "quarantined" if image is not None else "lease_lost",
            "event_id": claim.event_id,
            "image_id": claim.image_id,
            "error_code": error_code,
        }

    async def _schedule_retry(
        self,
        *,
        claim: ImageValidationClaim,
        owner_id: str,
        error_code: str,
        max_attempts: int,
    ) -> dict[str, Any]:
        if (claim.attempt_count or 0) >= max_attempts:
            async with self.session_factory() as session:
                async with session.begin():
                    image = await ImageService(session).quarantine_validation(
                        claim=claim,
                        owner_id=owner_id,
                        error_code="validation_attempts_exhausted",
                        finished_at=datetime.utcnow(),
                    )
            return {
                "outcome": "dead_letter" if image is not None else "lease_lost",
                "event_id": claim.event_id,
                "image_id": claim.image_id,
                "error_code": "validation_attempts_exhausted",
            }
        delay_seconds = min(300, 2 ** min(max(claim.attempt_count or 1, 1), 8))
        released_at = datetime.utcnow()
        async with self.session_factory() as session:
            async with session.begin():
                released = await ImageService(session).release_validation_retry(
                    claim=claim,
                    owner_id=owner_id,
                    released_at=released_at,
                    next_validation_at=released_at + timedelta(seconds=delay_seconds),
                    error_code=error_code,
                )
        return {
            "outcome": "retry" if released else "lease_lost",
            "event_id": claim.event_id,
            "image_id": claim.image_id,
            "error_code": error_code,
            "retry_after_seconds": delay_seconds,
        }

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        code = str(exc).strip()
        if not code or len(code) > 80 or any(char.isspace() for char in code):
            return "image_validation_error"
        return code

    @staticmethod
    def _lease_lost(claim: ImageValidationClaim) -> dict[str, Any]:
        return {
            "outcome": "lease_lost",
            "event_id": claim.event_id,
            "image_id": claim.image_id,
            "error_code": "image_validation_lease_lost",
        }


__all__ = ["ImageValidationWorker"]
