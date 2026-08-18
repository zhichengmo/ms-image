"""Validation-only AI request boundary.

The modality service owns prompt/schema semantics and ModelCall persistence;
transport, timeout, retry, cooldown and fallback are provided by the shared
``app.core.ai`` layer.
"""

from __future__ import annotations

import json
from time import monotonic
from typing import Any, Awaitable, Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.connection_pool import AIConnectionPool
from app.core.ai.qualification import transport_qualification_artifact_is_current
from app.core.ai.egress_proof import adapter_egress_proof_is_valid
from app.core.ai.contracts import (
    AIConnectionConfig,
    ProviderAdapter,
    ProviderImageInput,
    ProviderNotQualifiedError,
    ProviderRequest,
    ProviderRequestError,
    ProviderResponse,
)
from app.core.config import settings
from app.crud.xray_accuracy.model_call import XRayModelCallDal
from app.service.ai_governance_service import AIGovernanceService
from .providers import governed_provider_pool

from .prompt_service import PromptManifest, RenderedPrompt, XRayPromptRegistry, sha256_text


def validate_validation_response(
    output: dict[str, Any],
    schema_key: str,
    schema: dict[str, Any] | None = None,
) -> None:
    """Validate the technical, validation-only JSON response contract."""
    if not isinstance(output, dict):
        raise ProviderNotQualifiedError("provider_response_schema_invalid")
    schema = schema or {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "technical_status",
            "medical_verdict",
            "validation_only",
            "response_schema_key",
        ],
        "properties": {
            "technical_status": {"type": "string", "const": "accepted"},
            "medical_verdict": {"type": "null"},
            "validation_only": {"type": "boolean", "const": True},
            "response_schema_key": {"type": "string", "const": schema_key},
        },
    }
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise ProviderNotQualifiedError("provider_response_schema_invalid")
    if set(output) - set(properties) or any(field not in output for field in required):
        raise ProviderNotQualifiedError("provider_response_schema_invalid")
    for field, rule in properties.items():
        if field not in output:
            continue
        value = output[field]
        expected_type = rule.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ProviderNotQualifiedError("provider_response_schema_invalid")
        if expected_type == "boolean" and type(value) is not bool:
            raise ProviderNotQualifiedError("provider_response_schema_invalid")
        if expected_type == "null" and value is not None:
            raise ProviderNotQualifiedError("provider_response_medical_output_invalid")
        if "const" in rule and value != rule["const"]:
            raise ProviderNotQualifiedError("provider_response_medical_output_invalid")


class StubAIProvider:
    """Deterministic adapter; it never contacts a network or emits a verdict."""

    provider_key = "stub/replay"
    model_name = "xray-engineering-stub.v1"

    def __init__(
        self,
        *,
        model_name: str | None = None,
        behavior: Callable[[ProviderRequest], Awaitable[ProviderResponse]] | None = None,
    ):
        if model_name:
            self.model_name = model_name
        self.behavior = behavior

    def request_sync(self, request: ProviderRequest) -> ProviderResponse:
        started = monotonic()
        output = {
            "technical_status": "accepted",
            "medical_verdict": None,
            "validation_only": True,
            "response_schema_key": request.response_schema_key,
        }
        encoded = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        request_fingerprint = sha256_text(
            f"{request.run_id}:{request.attempt_id}:{request.request_nonce or ''}:"
            f"{request.prompt.rendered_sha256}:{request.connection_id or ''}"
        )
        request_id = f"stub-{request_fingerprint[:32]}"
        image_receipts = [
            {
                "source_index": image.source_index,
                "sent_sha256": image.sent_sha256,
                "status": "confirmed",
            }
            for image in request.images
        ]
        receipt = {
            "provider_request_id": request_id,
            "provider_key": self.provider_key,
            "actual_model": self.model_name,
            "image_count_received": request.image_count,
            "image_receipts": image_receipts,
            "image_ordered_sha256": request.image_ordered_sha256,
            "receipt_capability_version": "stub-receipt.v1",
            "status": "confirmed",
            "full_sent": "confirmed" if request.images else "not_applicable",
            "connection_id": request.connection_id,
        }
        return ProviderResponse(
            provider_request_id=request_id,
            actual_model=self.model_name,
            output_json=output,
            finish_reason="stop",
            receipt_json=receipt,
            raw_output_sha256=sha256_text(encoded),
            parsed_output_sha256=sha256_text(encoded),
            latency_ms=max(0, int((monotonic() - started) * 1000)),
        )

    async def request(self, request: ProviderRequest) -> ProviderResponse:
        if self.behavior is not None:
            return await self.behavior(request)
        return self.request_sync(request)


class XRayAIRequestService:
    """Build and persist one prompt/model-call contract through the DAL."""

    def __init__(
        self,
        db: AsyncSession,
        provider: ProviderAdapter | None = None,
        pool: AIConnectionPool | None = None,
        qualification_run_id: str | None = None,
        config_version: str | None = None,
    ):
        self.model_call_dal = XRayModelCallDal(db)
        self.prompt_registry = XRayPromptRegistry()
        self.qualification_run_id = qualification_run_id
        self.config_version = (config_version or settings.AI_CONFIG_VERSION).strip()
        self.governed_bundle = None
        self._governance_loaded = pool is not None or (
            provider is not None and provider.provider_key == "stub/replay" and not self.config_version
        )
        self.provider = provider or StubAIProvider()
        if pool is not None:
            self.pool = pool
        elif self.provider.provider_key == "stub/replay":
            self.pool = AIConnectionPool(
                connections=[
                    AIConnectionConfig(
                        "stub-default",
                        "stub",
                        "replay://stub",
                        self.provider.model_name,
                        "none",
                    )
                ],
                provider_factory=lambda _config: self.provider,
                allow_network=False,
            )
        else:
            # The real pool is resolved lazily from the legacy DB chain.  This
            # keeps the constructor synchronous for worker dependency
            # injection while preventing any environment-based provider setup.
            self.pool = None

    async def _ensure_governed_runtime(self) -> None:
        if self._governance_loaded and self.governed_bundle is not None:
            return
        if not self.config_version:
            return
        bundle = await AIGovernanceService(self.model_call_dal.db).resolve(
            version=self.config_version,
            language="en",
        )
        if self.pool is None:
            connections, providers, _ = governed_provider_pool(bundle.connection_entries)
            self.pool = AIConnectionPool(
                connections=connections,
                provider_factory=lambda config: providers[config.connection_id],
                allow_network=True,
            )
            self.provider = providers[connections[0].connection_id]
        self.governed_bundle = bundle
        self._governance_loaded = True

    async def _render_prompt(self, *, run_id: str, attempt_id: str, node_key: str, release_fingerprint: str, trace_namespace: str, language: str, image_count: int) -> RenderedPrompt:
        """Render the DB prompt selected by the legacy config chain.

        Filesystem assets provide only the request-gate schema and variable
        contract; the prompt body itself is taken from ``ai_prompt_template``.
        """
        await self._ensure_governed_runtime()
        if self.governed_bundle is None:
            return self.prompt_registry.render(
                prompt_key="xray.request_gate.v1", language=language,
                context={"run_id": run_id, "attempt_id": attempt_id, "node_key": node_key,
                         "release_fingerprint": release_fingerprint, "trace_namespace": trace_namespace,
                         "image_count": image_count},
            )
        base = self.prompt_registry.get_manifest("xray.request_gate.v1", language=language)
        body = self.governed_bundle.prompt.content.strip()
        if not body:
            raise ProviderNotQualifiedError("ai_prompt_template_empty")
        import json
        context = {"run_id": run_id, "attempt_id": attempt_id, "node_key": node_key,
                   "release_fingerprint": release_fingerprint, "trace_namespace": trace_namespace,
                   "image_count": image_count}
        context_json = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        rendered_body = f"{body}\n\nTECHNICAL_CONTEXT_JSON={context_json}"
        manifest = PromptManifest(
            prompt_key=f"ai_prompt_template:{self.governed_bundle.prompt.item_id}",
            node_key=node_key,
            language=language,
            version=self.governed_bundle.version,
            template_path="ai_prompt_template",
            schema_key=base.schema_key,
            body=body,
            status="published",
            variables=base.variables,
            checksum=sha256_text(body),
            module_key=base.module_key,
        )
        return RenderedPrompt(
            manifest=manifest,
            rendered_body=rendered_body,
            rendered_sha256=sha256_text(rendered_body),
            context_sha256=sha256_text(context_json),
        )

    async def _record_attempt(
        self,
        *,
        tenant_id: str,
        run_id: str,
        node_key: str,
        language: str,
        rendered: RenderedPrompt,
        schema_sha256: str,
        trace: dict[str, Any],
        response: ProviderResponse | None = None,
        request_trace: dict[str, Any] | None = None,
        coverage_evidence: dict[str, Any] | None = None,
        error_class: str | None = None,
    ) -> None:
        receipt = (
            {**response.receipt_json, "request_trace": request_trace}
            if response is not None
            else {"status": "failed", "request_trace": {"attempt": trace}}
        )
        if coverage_evidence is not None:
            receipt["coverage_evidence"] = coverage_evidence
        provider_evidence = trace.get("provider_evidence") or {}
        usage = (
            response.receipt_json.get("usage")
            if response is not None
            else provider_evidence.get("usage")
        )
        input_tokens = None
        output_tokens = None
        if isinstance(usage, dict):
            # Provider adapters normalize usage to a bounded, provider-neutral
            # shape.  Keep the two persisted counters populated without
            # retaining the raw response or any provider-specific fields.
            input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
            output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) or input_tokens < 0:
                input_tokens = None
            if not isinstance(output_tokens, int) or isinstance(output_tokens, bool) or output_tokens < 0:
                output_tokens = None
        await self.model_call_dal.create_call(
            {
                "id": uuid4().hex,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "attempt_id": trace["provider_attempt_id"],
                "node_key": node_key,
                "module_key": rendered.manifest.module_key,
                "provider_key": trace.get("provider_key", self.provider.provider_key),
                "requested_model": trace["model"],
                "actual_model": response.actual_model if response is not None else trace["model"],
                "prompt_key": rendered.manifest.prompt_key,
                "prompt_version": rendered.manifest.version,
                "prompt_sha256": rendered.manifest.prompt_sha256,
                "rendered_sha256": rendered.rendered_sha256,
                "schema_key": rendered.manifest.schema_key,
                "schema_sha256": schema_sha256,
                "requested_language": language,
                "actual_language": rendered.manifest.language,
                "receipt_json": receipt,
                "image_ordered_sha256": (
                    response.receipt_json.get("image_ordered_sha256")
                    if response is not None
                    else trace.get("image_ordered_sha256")
                ),
                "raw_output_sha256": (
                    response.raw_output_sha256
                    if response
                    else provider_evidence.get("raw_output_sha256")
                ),
                "parsed_output_sha256": (
                    response.parsed_output_sha256
                    if response
                    else provider_evidence.get("parsed_output_sha256")
                ),
                "finish_reason": (
                    response.finish_reason
                    if response
                    else provider_evidence.get("finish_reason", "error")
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": response.latency_ms if response else trace.get("latency_ms"),
                "retry_index": trace["attempt"],
                "fallback_used": trace.get("fallback_used", "no"),
                "error_class": error_class,
            }
        )

    async def execute_validation_request(
        self,
        *,
        tenant_id: str,
        run_id: str,
        attempt_id: str,
        release_fingerprint: str,
        trace_namespace: str,
        node_key: str = "request_gate",
        language: str = "en",
        images: tuple[ProviderImageInput, ...] = (),
        expected_source_image_refs: tuple[str, ...] = (),
        expected_source_image_hashes: tuple[str, ...] = (),
        resolved_source_image_refs: tuple[str, ...] | None = None,
    ) -> ProviderResponse:
        await self._ensure_governed_runtime()
        if self.pool is None:
            raise ProviderNotQualifiedError("ai_governed_pool_required")
        if node_key != "request_gate":
            raise ProviderNotQualifiedError("medical_provider_not_enabled")
        rendered = await self._render_prompt(
            run_id=run_id, attempt_id=attempt_id, node_key=node_key,
            release_fingerprint=release_fingerprint, trace_namespace=trace_namespace,
            language=language, image_count=len(images),
        )
        response_schema, schema_sha256 = self.prompt_registry.response_schema(
            rendered.manifest.schema_key
        )
        if self.provider.provider_key != "stub/replay":
            if not images:
                raise ProviderNotQualifiedError("image_manifest_not_resolved")
            resolved_refs = tuple(image.source_image_ref for image in images)
            if not expected_source_image_refs or resolved_refs != expected_source_image_refs:
                raise ProviderNotQualifiedError("image_manifest_not_resolved")
            if (
                len(expected_source_image_hashes) != len(images)
                or any(
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                    for digest in expected_source_image_hashes
                )
            ):
                raise ProviderNotQualifiedError("image_manifest_not_resolved")
            controlled_first_qualification = (
                self.qualification_run_id is not None
                and self.qualification_run_id == run_id
            )
            if (
                not controlled_first_qualification
                and (
                    not transport_qualification_artifact_is_current(
                    settings.AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH,
                    base_url=getattr(getattr(self.provider, "client", None), "endpoint", ""),
                    model=self.provider.model_name,
                    api_key=getattr(getattr(self.provider, "client", None), "api_key", ""),
                    prompt_key=rendered.manifest.prompt_key,
                    prompt_version=rendered.manifest.version,
                    prompt_checksum=rendered.manifest.prompt_sha256,
                    schema_key=rendered.manifest.schema_key,
                    schema_checksum=schema_sha256,
                    artifact_signing_key=settings.AI_QUALIFICATION_ARTIFACT_SIGNING_KEY,
                    egress_signing_key=settings.AI_EGRESS_PROOF_SIGNING_KEY,
                )
                )
            ):
                raise ProviderNotQualifiedError("real_provider_not_qualified")
        request = ProviderRequest(
            run_id=run_id,
            attempt_id=attempt_id,
            node_key=node_key,
            release_fingerprint=release_fingerprint,
            prompt=rendered,
            response_schema_key=rendered.manifest.schema_key,
            response_schema_sha256=schema_sha256,
            response_schema=response_schema,
            requested_model=self.provider.model_name,
            images=images,
            # A request containing images has not yet been proven complete.
            # Only the Provider receipt verifier may promote this to
            # ``confirmed`` after the response is received.
            full_sent="unknown" if images else "not_applicable",
            request_nonce=uuid4().hex,
            deadline_seconds=None,
        )
        requested_manifest = [
            {
                "source_index": image.source_index,
                "source_image_ref": image.source_image_ref,
                "sent_sha256": image.sent_sha256,
            }
            for image in images
        ]
        resolved_refs = tuple(resolved_source_image_refs or tuple(item["source_image_ref"] for item in requested_manifest))
        resolved_sha256 = [item["sent_sha256"] for item in requested_manifest]

        def coverage_evidence(response_: ProviderResponse | None = None) -> dict[str, Any]:
            sent_receipts = (
                response_.receipt_json.get("image_receipts", [])
                if response_ is not None
                else []
            )
            if response_ is not None and not sent_receipts:
                proof = response_.receipt_json.get("adapter_egress_proof")
                if (
                    isinstance(proof, dict)
                    and adapter_egress_proof_is_valid(
                        proof,
                        signing_key=getattr(
                            getattr(self.provider, "client", None),
                            "egress_proof_signing_key",
                            "",
                        ),
                        expected_transport_status="qualified",
                        expected_model=request.requested_model,
                        expected_prompt_sha256=request.prompt_checksum,
                        expected_rendered_sha256=request.rendered_sha256,
                        expected_schema_sha256=request.response_schema_sha256,
                        expected_request_nonce_sha256=(
                            sha256_text(request.request_nonce)
                            if request.request_nonce
                            else sha256_text("")
                        ),
                        expected_image_ordered_sha256=request.image_ordered_sha256,
                        expected_images=[
                            {
                                "source_index": image.source_index,
                                "sent_sha256": image.sent_sha256,
                            }
                            for image in request.images
                        ],
                    )
                ):
                    sent_receipts = [
                        {**item, "status": "egress_proven"}
                        for item in proof.get("images", [])
                        if isinstance(item, dict)
                    ]
            sent_by_index = {
                item["source_index"]: item["sent_sha256"]
                for item in sent_receipts
                if isinstance(item, dict)
                and item.get("status") in {"confirmed", "egress_proven"}
                and isinstance(item.get("source_index"), int)
                and isinstance(item.get("sent_sha256"), str)
            }
            sent_manifest = [
                {
                    "source_index": item["source_index"],
                    "source_image_ref": item["source_image_ref"],
                    "sent_sha256": sent_by_index[item["source_index"]],
                }
                for item in requested_manifest
                if item["source_index"] in sent_by_index
            ]
            return {
                "expected_source_image_refs": list(expected_source_image_refs),
                "resolved_source_image_refs": list(resolved_refs),
                "requested_source_image_refs": [item["source_image_ref"] for item in requested_manifest],
                "sent_source_image_refs": [item["source_image_ref"] for item in sent_manifest],
                # Expected hashes bind the immutable OSS source objects.  The
                # resolved/requested/sent hashes bind the bytes actually sent
                # to the Provider (which can differ after DICOM→PNG).
                "expected_image_sha256": list(expected_source_image_hashes),
                "resolved_image_sha256": list(resolved_sha256),
                "requested_image_sha256": [item["sent_sha256"] for item in requested_manifest],
                "sent_image_sha256": [item["sent_sha256"] for item in sent_manifest],
                "coverage_status": (
                    response_.receipt_json.get("coverage_status", "unknown")
                    if response_ is not None
                    else "unknown"
                ),
                "image_ordered_sha256": request.image_ordered_sha256,
            }
        try:
            response, metadata = await self.pool.request(request)
        except ProviderRequestError as exc:
            for trace in exc.attempts:
                await self._record_attempt(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    node_key=node_key,
                    language=language,
                    rendered=rendered,
                    schema_sha256=schema_sha256,
                    trace=trace,
                    coverage_evidence=coverage_evidence(),
                    error_class=trace["error_class"],
                )
            raise
        for failed_trace in metadata["attempts"][:-1]:
            await self._record_attempt(
                tenant_id=tenant_id,
                run_id=run_id,
                node_key=node_key,
                language=language,
                rendered=rendered,
                schema_sha256=schema_sha256,
                trace=failed_trace,
                coverage_evidence=coverage_evidence(),
                error_class=failed_trace["error_class"],
            )
        final_trace = metadata["attempts"][-1]
        try:
            validate_validation_response(
                response.output_json,
                rendered.manifest.schema_key,
                schema=response_schema,
            )
        except ProviderNotQualifiedError:
            await self._record_attempt(
                tenant_id=tenant_id,
                run_id=run_id,
                node_key=node_key,
                language=language,
                rendered=rendered,
                schema_sha256=schema_sha256,
                trace=final_trace,
                response=response,
                request_trace=metadata,
                coverage_evidence=coverage_evidence(response),
                error_class="provider_output_contract",
            )
            raise
        await self._record_attempt(
            tenant_id=tenant_id,
            run_id=run_id,
            node_key=node_key,
            language=language,
            rendered=rendered,
            schema_sha256=schema_sha256,
            trace=final_trace,
            response=response,
            request_trace=metadata,
            coverage_evidence=coverage_evidence(response),
        )
        return response
