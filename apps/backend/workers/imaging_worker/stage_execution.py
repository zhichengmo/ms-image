from __future__ import annotations

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    GatewayDefiniteResponseError,
    GatewayUnknownDeliveryError,
)
from apps.backend.core.ai.gateway.image_signer import (
    AttemptImageSigner,
    ImageSigningError,
)
from apps.backend.core.ai.gateway_client import GatewayClient
from apps.backend.core.ai.prompt_runtime_client import PromptRuntimeClient
from apps.backend.core.config import settings
from apps.backend.services.runtime.service.ai_request_service import (
    AIRequestService,
    AIRequestStateConflict,
)
from apps.backend.services.runtime.service.imaging_execution_service import (
    ImagingExecutionService,
    StageExecutionStateConflict,
)


class StageExecutionWorker:
    def __init__(
        self,
        *,
        session_factory_: async_sessionmaker[AsyncSession],
        gateway_client: GatewayClient | None = None,
        image_signer: AttemptImageSigner | None = None,
        prompt_client: PromptRuntimeClient | None = None,
    ):
        self.session_factory = session_factory_
        self.gateway_client = gateway_client
        self.image_signer = image_signer
        self.prompt_client = prompt_client

    async def execute(
        self,
        *,
        event_id: str,
        message: dict,
        message_version: str,
        trace_id: str,
        owner_id: str,
        lease_seconds: int,
    ) -> dict:
        async with self.session_factory() as session:
            async with session.begin():
                stage = await ImagingExecutionService(session).claim(
                    event_id=event_id,
                    message=message,
                    message_version=message_version,
                    trace_id=trace_id,
                    owner_id=owner_id,
                    lease_seconds=lease_seconds,
                )
                # The claim transaction expires ORM state on commit.  Keep only
                # the scalar identity needed by the next transaction boundary.
                stage_id = None if stage is None else stage.id
        if stage_id is None:
            return {"outcome": "already_applied", "event_id": event_id}
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    prepared = await ImagingExecutionService(
                        session
                    ).prepare_stage_execution(
                        stage_checkpoint_id=stage_id,
                        owner_id=owner_id,
                        trace_id=trace_id,
                        request_id=event_id,
                    )
            if prepared.get("prompt_render_required"):
                ai_request = prepared.get("ai_request")
                if ai_request is None:
                    raise StageExecutionStateConflict("ai_prompt_request_missing")
                prompt_client = self.prompt_client or PromptRuntimeClient()
                rendered_prompt = await prompt_client.render(
                    service_code=settings.PROMPT_SERVICE_CODE,
                    module_code=ai_request.module_code,
                    prompt_key=ai_request.prompt_key,
                    variables=AIRequestService.prompt_runtime_variables(
                        prompt_command=ai_request.prompt_command
                    ),
                    locale=ai_request.locale,
                    variant=ai_request.variant,
                    trace_id=trace_id,
                    request_id=event_id,
                )
                async with self.session_factory() as session:
                    async with session.begin():
                        prepared = await ImagingExecutionService(
                            session
                        ).prepare_stage_execution(
                            stage_checkpoint_id=stage_id,
                            owner_id=owner_id,
                            trace_id=trace_id,
                            request_id=event_id,
                            rendered_prompt=rendered_prompt,
                        )
            if prepared.get("pending_reconcile"):
                return {
                    "outcome": "pending_reconcile",
                    "event_id": event_id,
                    "attempt_id": prepared.get("attempt_id"),
                }
            if not prepared.get("network_required"):
                return self._completed(
                    event_id=event_id, output=prepared.get("output") or {}
                )
            attempt_id = str(prepared.get("attempt_id") or "")
            if not attempt_id:
                raise StageExecutionStateConflict("ai_call_attempt_missing")

            async with self.session_factory() as session:
                async with session.begin():
                    network_plan = await AIRequestService(
                        session
                    ).load_attempt_for_network(attempt_id=attempt_id)

            try:
                network_result = await AIRequestService.execute_gateway_attempt_network(
                    network_plan=network_plan,
                    gateway_client=self.gateway_client,
                    image_signer=self.image_signer,
                )
            except GatewayUnknownDeliveryError as exc:
                async with self.session_factory() as session:
                    async with session.begin():
                        await AIRequestService(session).finalize_attempt_failure(
                            attempt_id=attempt_id,
                            error_code=str(exc),
                            unknown=True,
                        )
                return {
                    "outcome": "pending_reconcile",
                    "event_id": event_id,
                    "attempt_id": attempt_id,
                }
            except GatewayDefiniteResponseError as exc:
                async with self.session_factory() as session:
                    async with session.begin():
                        ai_service = AIRequestService(session)
                        call_result = await ai_service.finalize_attempt_failure(
                            attempt_id=attempt_id,
                            error_code=str(exc),
                            unknown=False,
                            image_receipt=exc.image_receipt,
                            image_manifest_sha256=exc.image_manifest_sha256,
                            image_count_sent=exc.image_count_sent,
                            provider_request_id=exc.provider_request_id,
                            actual_model=exc.actual_model,
                            usage_json=exc.usage_json,
                            response_sha256=exc.response_sha256,
                        )
                        output = await ImagingExecutionService(
                            session
                        ).finalize_ai_stage(
                            stage_checkpoint_id=stage_id,
                            owner_id=owner_id,
                            call_result=call_result,
                        )
                return self._completed(event_id=event_id, output=output)
            except (GatewayContractError, ImageSigningError) as exc:
                async with self.session_factory() as session:
                    async with session.begin():
                        ai_service = AIRequestService(session)
                        call_result = await ai_service.finalize_attempt_failure(
                            attempt_id=attempt_id,
                            error_code=str(exc),
                            unknown=False,
                        )
                        output = await ImagingExecutionService(
                            session
                        ).finalize_ai_stage(
                            stage_checkpoint_id=stage_id,
                            owner_id=owner_id,
                            call_result=call_result,
                        )
                return self._completed(event_id=event_id, output=output)

            async with self.session_factory() as session:
                async with session.begin():
                    ai_service = AIRequestService(session)
                    call_result = await ai_service.finalize_attempt(
                        attempt_id=attempt_id,
                        execution=network_result["execution"],
                        image_receipt=network_result["image_receipt"],
                        image_manifest_sha256=network_result["image_manifest_sha256"],
                        image_count_sent=network_result["image_count_sent"],
                    )
                    output = await ImagingExecutionService(session).finalize_ai_stage(
                        stage_checkpoint_id=stage_id,
                        owner_id=owner_id,
                        call_result=call_result,
                    )
        except (StageExecutionStateConflict, AIRequestStateConflict) as exc:
            return {
                "outcome": "conflict",
                "event_id": event_id,
                "error_code": str(exc),
            }
        return self._completed(event_id=event_id, output=output)

    @staticmethod
    def _completed(*, event_id: str, output: dict) -> dict:
        output_sha256 = hashlib.sha256(
            json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "outcome": "completed",
            "event_id": event_id,
            "output_sha256": output_sha256,
        }
