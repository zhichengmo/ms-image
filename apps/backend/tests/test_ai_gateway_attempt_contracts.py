"""Offline Gateway adapter and Attempt request contracts (no real network)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from apps.backend.core.ai.config_contract import TASK_REQUEST_SNAPSHOT_V3
from apps.backend.core.ai.gateway.contracts import (
    AI_IMAGE_RECEIPT_V2,
    GatewayContractError,
    GatewayDefiniteResponseError,
    GatewayImageInput,
    GatewayRejectedError,
    GatewayRequest,
    GatewayUnknownDeliveryError,
    normalize_gateway_profile,
    response_sha256,
    schema_validate_result,
    validate_signed_image_url,
)
from apps.backend.core.ai.gateway_client import GatewayClient, GatewayResponseParseError
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.ai_control.service.prompt_source import (
    NacosPromptSourceClient,
    PromptSourceError,
)


SCHEMA = {
    "type": "object",
    "required": ["result"],
    "properties": {"result": {"type": "string"}},
    "additionalProperties": False,
}


def _complete_medical_result_v2() -> dict[str, Any]:
    return {
        "result_schema_version": "xray-complete-medical-result.v2",
        "medical_status": "review_required",
        "summary": "本次检查存在需要复核的影像学征象。",
        "impression": "建议结合完整检查进行专业复核。",
        "findings": [
            {
                "finding_id": "finding-1",
                "label": "影像学征象",
                "description": "可见需要复核的局部影像学征象。",
                "anatomy_region": "thorax",
                "laterality": "UNKNOWN",
                "source_ref_ids": ["source-1"],
            }
        ],
        "normal_basis": [],
        "coverage": {
            "status": "partial",
            "assessed_regions": ["thorax"],
            "missing_or_limited_views": [],
        },
        "families_not_assessed": [],
        "limitations": [],
        "review_reason": "该征象需要复核。",
        "source_refs": [
            {
                "source_ref_id": "source-1",
                "image_id": "image_1",
                "series_id": "series_1",
                "projection": "VD",
                "manifest_sha256": "1" * 64,
            }
        ],
        "targeted_candidate": None,
    }


def _image_receipt_v2() -> dict[str, Any]:
    return {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": 1,
        "images": [
            {
                "sequence_no": 1,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "series_sequence_no": 1,
                "image_id": "image_1",
                "logical_image_key": "logical_1",
                "image_version_no": 1,
                "projection": "VD",
                "projection_provenance": {
                    "source": "caller_declared",
                    "schema_version": "xray-projection.v1",
                },
                "sha256": "a" * 64,
                "size_bytes": 10,
                "mime_type": "image/jpeg",
            }
        ],
    }


def _clinical_context_v1() -> dict[str, Any]:
    return {
        "contract_version": "xray-clinical-context.v1",
        "source": {
            "system": "ms-ai-fast",
            "recorded_at": "2026-08-28T10:30:00+08:00",
            "temporal_scope": "available_at_request",
        },
        "chief_complaint": "间歇性咳嗽三天",
        "study_reason": "评估胸部影像",
    }


@pytest.fixture
def anyio_backend() -> str:
    """Run async Gateway tests on the asyncio backend only."""
    return "asyncio"


@pytest.mark.parametrize(
    ("declared_projection", "observed_projection", "expected"),
    [
        ("VD", "ventrodorsal", "consistent"),
        ("ML", "mediolateral", "consistent"),
        ("Lateral", "right_lateral", "consistent"),
        ("Lateral", "left_lateral", "consistent"),
        ("Lateral", "lateral_indeterminate", "indeterminate"),
        ("Lateral", "ventrodorsal", "inconsistent"),
        ("AP", "ventrodorsal", "indeterminate"),
    ],
)
def test_image_quality_projection_alias_consistency(
    declared_projection: str,
    observed_projection: str,
    expected: str,
) -> None:
    from apps.backend.core.ai.image_quality_contract import (
        _expected_projection_consistency,
    )

    assert (
        _expected_projection_consistency(
            declared_projection=declared_projection,
            observed_projection=observed_projection,
        )
        == expected
    )


def _request(
    *,
    images: tuple[GatewayImageInput, ...] = (),
    api_format: str = "chat-completions",
    allowed_models: tuple[str, ...] = ("provider-model",),
    requested_model: str = "provider-model",
    messages: tuple[dict[str, Any], ...] | None = None,
) -> GatewayRequest:
    return GatewayRequest(
        attempt_id="attempt_1",
        logical_call_id="call_1",
        task_id="task_1",
        trace_id="trace_1",
        request_id="req_1",
        connection_sha256="a" * 64,
        provider_type="openai_compatible",
        api_format=api_format,
        requested_model=requested_model,
        allowed_actual_models=allowed_models,
        generation_params={"temperature": 0.1, "max_output_tokens": 64},
        response_schema=SCHEMA,
        messages=messages or ({"role": "user", "content": "analyze"},),
        images=images,
        timeout_ms=30_000,
        provider_idempotency_key="idem-1",
        image_manifest_sha256="b" * 64,
    )


def _network_plan(**overrides: Any) -> dict[str, Any]:
    plan = {
        "attempt_id": "attempt_1",
        "logical_call_id": "call_1",
        "task_id": "task_1",
        "trace_id": "trace_1",
        "request_id": "req_1",
        "connection_sha256": "a" * 64,
        "provider_type": "openai_compatible",
        "api_format": "chat-completions",
        "requested_model": "provider-model",
        "allowed_actual_models": ("provider-model",),
        "generation_params": {"temperature": 0.1, "max_output_tokens": 64},
        "response_schema": {
            **SCHEMA,
            "x-ms-image-contract-version": "complete-medical-result.v1",
        },
        "messages": ({"role": "user", "content": "analyze"},),
        "timeout_ms": 30_000,
        "provider_idempotency_key": "idem-1",
        "image_manifest_sha256": "b" * 64,
        "image_count_requested": 0,
        "image_inputs": (),
        "image_url_ttl_seconds": 60,
    }
    plan.update(overrides)
    return plan


def test_gateway_client_preserves_ms_ai_fast_platform_base_url() -> None:
    client = GatewayClient(
        base_url="http://Platform.Example:80/api/v1/",
        api_key="token",
    )
    assert client.base_url == "http://Platform.Example:80/api/v1"


def test_gateway_request_sha_is_stable_without_secret_or_signed_url() -> None:
    first = _request(
        images=(
            GatewayImageInput(
                sequence_no=1,
                mime_type="image/jpeg",
                signed_url="https://oss.example.com/1.jpg?x=1",
            ),
        )
    )
    second = _request(
        images=(
            GatewayImageInput(
                sequence_no=1,
                mime_type="image/jpeg",
                signed_url="https://oss.example.com/1.jpg?x=2",
            ),
        )
    )
    assert first.request_sha256() == second.request_sha256()
    assert len(first.request_sha256()) == 64


@pytest.mark.anyio
async def test_gateway_client_sends_ms_ai_fast_headers_and_resolves_provider_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": "provider-body-id", "choices": []},
            headers={"x-request-id": "provider-header-id"},
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )
    client = GatewayClient(
        base_url="http://Platform.Example:80/api/v1/",
        api_key="secret-token",
        timeout=3,
    )
    result = await client.chat_completions(
        {
            "model": "provider-model",
            "messages": [{"role": "user", "content": "analyze"}],
            "metadata": {"request_id": "req_1", "trace_id": "trace_1"},
        },
        idempotency_key="idem-1",
    )

    assert result["request_id"] == "provider-header-id"
    assert captured["url"] == "http://platform.example/api/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer secret-token"
    assert captured["headers"]["idempotency-key"] == "idem-1"
    assert captured["headers"]["x-request-id"] == "req_1"
    assert captured["headers"]["x-trace-id"] == "trace_1"
    assert captured["body"]["model"] == "provider-model"


@pytest.mark.anyio
async def test_gateway_client_falls_back_to_body_provider_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "provider-body-id", "choices": []})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )
    result = await GatewayClient(
        base_url="https://platform.example/v1",
        api_key="secret-token",
    ).chat_completions(
        {"model": "provider-model", "messages": [], "metadata": {}},
        idempotency_key="idem-1",
    )
    assert result["request_id"] == "provider-body-id"


@pytest.mark.anyio
async def test_gateway_client_classifies_invalid_http_json_as_definite_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="not-json",
            headers={"x-request-id": "provider-request-1"},
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    with pytest.raises(
        GatewayResponseParseError,
        match="provider_response_payload_invalid",
    ):
        await GatewayClient(
            base_url="https://platform.example/v1",
            api_key="secret-token",
        ).chat_completions(
            {"model": "provider-model", "messages": [], "metadata": {}},
            idempotency_key="idem-1",
        )


@pytest.mark.anyio
async def test_ai_request_network_builds_strict_payload_and_persists_only_audit_facts() -> (
    None
):
    captured: dict[str, Any] = {}
    provider_body = {
        "id": "provider-body-id",
        "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
        "model": "provider-model",
        "usage": {"total_tokens": 7},
    }

    class FakeSigner:
        async def sign(self, **kwargs):
            return [
                GatewayImageInput(
                    sequence_no=1,
                    mime_type="image/jpeg",
                    signed_url="https://bucket.oss.example/source.jpg?signature=secret",
                )
            ]

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            captured["payload"] = payload
            captured["idempotency_key"] = idempotency_key
            return {"request_id": "provider-request-1", "body": provider_body}

    result = await AIRequestService.execute_gateway_attempt_network(
        network_plan=_network_plan(image_count_requested=1),
        gateway_client=FakeGateway(),
        image_signer=FakeSigner(),
    )

    execution = result["execution"]
    assert execution.provider_request_id == "provider-request-1"
    assert execution.parsed_result_json == {"result": "ok"}
    assert execution.usage_json == {"total_tokens": 7}
    assert execution.response_sha256 == response_sha256(provider_body)
    assert not hasattr(execution, "raw_response")
    assert "object_ref" not in result
    assert captured["idempotency_key"] == "idem-1"
    assert captured["payload"]["strategy"] == "race"
    assert captured["payload"]["max_tokens"] == 64
    assert captured["payload"]["response_format"]["json_schema"]["strict"] is True
    assert captured["payload"]["metadata"] == {
        "task_id": "task_1",
        "attempt_id": "attempt_1",
        "request_id": "req_1",
        "trace_id": "trace_1",
        "idempotency_key": "idem-1",
    }
    user_content = captured["payload"]["messages"][0]["content"]
    assert user_content[0] == {"type": "text", "text": "analyze"}
    assert user_content[1]["type"] == "image_url"


@pytest.mark.anyio
async def test_ai_request_provider_reject_is_definite_failure() -> None:
    request = httpx.Request("POST", "https://platform.example/v1/chat/completions")
    response = httpx.Response(401, request=request)

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            raise httpx.HTTPStatusError("rejected", request=request, response=response)

    class FakeSigner:
        async def sign(self, **kwargs):
            return []

    with pytest.raises(GatewayRejectedError, match="provider_http_401") as raised:
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )
    assert raised.value.image_manifest_sha256 == "b" * 64
    assert raised.value.image_count_sent == 0
    assert raised.value.image_receipt == {
        "contract_version": "ai-image-receipt.v1",
        "image_count": 0,
        "images": [],
    }
    assert raised.value.provider_request_id is None
    assert raised.value.actual_model is None
    assert raised.value.usage_json is None
    assert raised.value.response_sha256 is None


@pytest.mark.anyio
async def test_ai_request_gateway_parse_failure_has_no_provider_summary() -> None:
    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            raise GatewayResponseParseError("provider_response_payload_invalid")

    class FakeSigner:
        async def sign(self, **kwargs):
            return []

    with pytest.raises(
        GatewayDefiniteResponseError,
        match="provider_response_payload_invalid",
    ) as raised:
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )

    assert raised.value.provider_request_id is None
    assert raised.value.actual_model is None
    assert raised.value.usage_json is None
    assert raised.value.response_sha256 is None


@pytest.mark.anyio
async def test_ai_request_network_error_is_unknown_delivery() -> None:
    request = httpx.Request("POST", "https://platform.example/v1/chat/completions")

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            raise httpx.ConnectError("boom", request=request)

    class FakeSigner:
        async def sign(self, **kwargs):
            return []

    with pytest.raises(GatewayUnknownDeliveryError, match="provider_delivery_unknown"):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_body", "error_code"),
    [
        (
            {
                "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
                "model": "unexpected-model",
            },
            "provider_actual_model_mismatch",
        ),
        (
            {
                "choices": [{"message": {"content": json.dumps({"wrong": "shape"})}}],
                "model": "provider-model",
            },
            "provider_response_schema_rejected",
        ),
    ],
)
async def test_ai_request_rejects_model_or_schema_mismatch(
    provider_body: dict[str, Any],
    error_code: str,
) -> None:
    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            return {"request_id": "provider-request-1", "body": provider_body}

    class FakeSigner:
        async def sign(self, **kwargs):
            return []

    with pytest.raises(GatewayContractError, match=error_code):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )


@pytest.mark.anyio
async def test_ai_request_preserves_v2_image_receipt_when_content_parse_fails() -> None:
    signed_urls = (
        "https://bucket.oss.example/one.jpg?signature=secret-one",
        "https://bucket.oss.example/two.jpg?signature=secret-two",
    )
    image_inputs = (
        {
            "sequence_no": 1,
            "series_id": "series_1",
            "series_manifest_sha256": "1" * 64,
            "series_sequence_no": 1,
            "image_id": "image_1",
            "logical_image_key": "logical_1",
            "image_version_no": 1,
            "projection": "VD",
            "projection_provenance": "caller_declared",
            "sha256": "a" * 64,
            "size_bytes": 10,
            "mime_type": "image/jpeg",
        },
        {
            "sequence_no": 2,
            "series_id": "series_1",
            "series_manifest_sha256": "1" * 64,
            "series_sequence_no": 2,
            "image_id": "image_2",
            "logical_image_key": "logical_2",
            "image_version_no": 1,
            "projection": "Lateral",
            "projection_provenance": "caller_declared",
            "sha256": "c" * 64,
            "size_bytes": 20,
            "mime_type": "image/jpeg",
        },
    )

    class FakeSigner:
        async def sign(self, **kwargs):
            return [
                GatewayImageInput(
                    sequence_no=index,
                    mime_type="image/jpeg",
                    signed_url=signed_url,
                )
                for index, signed_url in enumerate(signed_urls, start=1)
            ]

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            return {
                "request_id": "provider-request-1",
                "body": {
                    "choices": [{"message": {"content": "{not json"}}],
                    "model": "provider-model",
                },
            }

    with pytest.raises(
        GatewayDefiniteResponseError,
        match="provider_response_json_invalid",
    ) as raised:
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(
                image_count_requested=2,
                image_inputs=image_inputs,
                snapshot_contract_version=TASK_REQUEST_SNAPSHOT_V3,
            ),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )

    error = raised.value
    assert error.image_manifest_sha256 == "b" * 64
    assert error.image_count_sent == 2
    assert error.image_receipt["contract_version"] == AI_IMAGE_RECEIPT_V2
    assert error.image_receipt["image_count"] == 2
    assert [item["image_id"] for item in error.image_receipt["images"]] == [
        "image_1",
        "image_2",
    ]
    assert [item["projection"] for item in error.image_receipt["images"]] == [
        "VD",
        "Lateral",
    ]
    assert "signature" not in json.dumps(error.image_receipt)
    assert "signed_url" not in json.dumps(error.image_receipt)


@pytest.mark.anyio
async def test_ai_request_rejects_v2_source_fact_not_in_actual_receipt() -> None:
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )

    result = _complete_medical_result_v2()
    result["source_refs"][0]["projection"] = "Lateral"
    image_inputs = tuple(_image_receipt_v2()["images"])

    class FakeSigner:
        async def sign(self, **kwargs):
            return [
                GatewayImageInput(
                    sequence_no=1,
                    mime_type="image/jpeg",
                    signed_url="https://bucket.oss.example/one.jpg?signature=secret",
                )
            ]

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            return {
                "request_id": "provider-request-1",
                "body": {
                    "choices": [{"message": {"content": json.dumps(result)}}],
                    "model": "provider-model",
                },
            }

    with pytest.raises(
        GatewayDefiniteResponseError,
        match="provider_result_source_projection_mismatch",
    ) as raised:
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(
                response_schema=AIConfigCompiler._output_schema(
                    profile_key="xray_primary_v2"
                ),
                image_count_requested=1,
                image_inputs=image_inputs,
                snapshot_contract_version=TASK_REQUEST_SNAPSHOT_V3,
            ),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )

    assert raised.value.image_receipt["contract_version"] == AI_IMAGE_RECEIPT_V2
    assert raised.value.image_receipt["images"][0]["projection"] == "VD"


def test_signed_image_url_enforces_https_and_allowlisted_host() -> None:
    url = validate_signed_image_url(
        "https://oss.example.com/private/obj.jpg?x=1&y=2",
        allowed_hosts=["oss.example.com"],
    )
    assert url.startswith("https://")
    for unsafe in (
        "http://oss.example.com/a",
        "https://evil.example.com/a",
        "https://oss.example.com",
        "https://user@oss.example.com/a",
    ):
        with pytest.raises(GatewayContractError, match="ai_image_signed_url_invalid"):
            validate_signed_image_url(unsafe, allowed_hosts=["oss.example.com"])


def test_schema_validate_result_rejects_invalid_json_and_non_schema_payloads() -> None:
    with pytest.raises(GatewayContractError, match="provider_response_json_invalid"):
        schema_validate_result(value="{not json", schema=SCHEMA)
    with pytest.raises(GatewayContractError, match="provider_response_schema_rejected"):
        schema_validate_result(value={"unexpected": 1}, schema=SCHEMA)


def test_schema_validate_result_accepts_bare_json_and_one_complete_json_fence() -> None:
    expected = {"result": "ok"}
    assert (
        schema_validate_result(
            value='  {"result":"ok"}\n',
            schema=SCHEMA,
        )
        == expected
    )
    assert (
        schema_validate_result(
            value='```json\n{"result":"ok"}\n```',
            schema=SCHEMA,
        )
        == expected
    )


def test_schema_validate_result_runs_frozen_schema_after_fence_unwrap() -> None:
    with pytest.raises(
        GatewayContractError,
        match="provider_response_schema_rejected",
    ):
        schema_validate_result(
            value='```json\n{"unexpected":1}\n```',
            schema=SCHEMA,
        )


@pytest.mark.parametrize(
    "value",
    [
        '说明\n```json\n{"result":"ok"}\n```',
        '```json\n{"result":"ok"}\n```\n说明',
        '```\n{"result":"ok"}\n```',
        '```JSON\n{"result":"ok"}\n```',
        '```json\n{"result":"ok"}\n```\n```json\n{"result":"ok"}\n```',
        "```json\n{not json}\n```",
    ],
)
def test_schema_validate_result_rejects_non_unique_or_non_json_fence(
    value: str,
) -> None:
    with pytest.raises(GatewayContractError, match="provider_response_json_invalid"):
        schema_validate_result(value=value, schema=SCHEMA)


def test_complete_medical_result_v2_schema_accepts_only_the_versioned_shape() -> None:
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )

    schema = AIConfigCompiler._output_schema(profile_key="xray_primary_v2")
    result = _complete_medical_result_v2()

    assert schema_validate_result(value=result, schema=schema) == result
    with pytest.raises(GatewayContractError, match="provider_response_schema_rejected"):
        invalid = deepcopy(result)
        invalid.pop("summary")
        schema_validate_result(value=invalid, schema=schema)
    with pytest.raises(GatewayContractError, match="provider_response_schema_rejected"):
        invalid = deepcopy(result)
        invalid["findings"][0]["unexpected"] = True
        schema_validate_result(value=invalid, schema=schema)


def test_complete_medical_result_v2_validates_actual_image_references() -> None:
    from apps.backend.core.ai.xray_result_contract import (
        COMPLETE_MEDICAL_RESULT_V2,
        validate_xray_result_contract,
    )

    result = _complete_medical_result_v2()

    assert (
        validate_xray_result_contract(
            result=result,
            schema_contract_version=COMPLETE_MEDICAL_RESULT_V2,
            image_receipt=_image_receipt_v2(),
        )
        == result
    )


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        (
            lambda result: result["findings"].append(deepcopy(result["findings"][0])),
            "provider_result_finding_id_duplicate",
        ),
        (
            lambda result: result["source_refs"].append(
                deepcopy(result["source_refs"][0])
            ),
            "provider_result_source_ref_id_duplicate",
        ),
        (
            lambda result: result["findings"][0]["source_ref_ids"].append(
                "source-missing"
            ),
            "provider_result_source_ref_missing",
        ),
        (
            lambda result: result["source_refs"][0].update(
                {"image_id": "image_not_sent"}
            ),
            "provider_result_source_image_not_sent",
        ),
        (
            lambda result: result["source_refs"][0].update(
                {"series_id": "series_not_sent"}
            ),
            "provider_result_source_series_id_mismatch",
        ),
        (
            lambda result: result["source_refs"][0].update({"projection": "Lateral"}),
            "provider_result_source_projection_mismatch",
        ),
        (
            lambda result: result["source_refs"][0].update(
                {"manifest_sha256": "f" * 64}
            ),
            "provider_result_source_manifest_sha256_mismatch",
        ),
        (
            lambda result: result.update(
                {
                    "targeted_candidate": {
                        "family_key": "thoracic",
                        "focus_key": "pulmonary_pattern",
                        "reason": "需要专项复核",
                        "source_finding_ids": ["finding-missing"],
                    }
                }
            ),
            "provider_result_targeted_source_finding_missing",
        ),
    ],
)
def test_complete_medical_result_v2_rejects_broken_technical_references(
    mutation,
    error_code: str,
) -> None:
    from apps.backend.core.ai.xray_result_contract import (
        COMPLETE_MEDICAL_RESULT_V2,
        XRayResultContractError,
        validate_xray_result_contract,
    )

    result = _complete_medical_result_v2()
    mutation(result)

    with pytest.raises(XRayResultContractError, match=f"^{error_code}$"):
        validate_xray_result_contract(
            result=result,
            schema_contract_version=COMPLETE_MEDICAL_RESULT_V2,
            image_receipt=_image_receipt_v2(),
        )


def test_gateway_profile_normalization_is_stable() -> None:
    disabled = normalize_gateway_profile(None)
    assert disabled["provider_enabled"] is False
    assert normalize_gateway_profile(dict(disabled)) == disabled


def _frozen_task_config(
    *,
    gateway_profile: dict[str, Any] | None,
    capability_provider_disabled: bool,
    config_contract_version: str = "ai-config.v2",
):
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.core.pipeline import (
        build_default_registry,
        compile_profile_contract,
    )

    registry = build_default_registry()
    profile_key = "xray_primary_v1"
    _, profile_sha = compile_profile_contract(profile_key, registry)
    capability_manifest = {"provider_disabled": capability_provider_disabled}
    if gateway_profile is not None:
        normalized = normalize_gateway_profile(gateway_profile)
        capability_manifest["gateway_profile_sha256"] = sha256_json(normalized)
    return SimpleNamespace(
        status="active",
        config_contract_version=config_contract_version,
        profile_key=profile_key,
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256=profile_sha,
        stage_registry_contract_version=registry.CONTRACT_VERSION,
        compiled_pipeline_json={"profile_key": profile_key},
        capability_manifest_json=capability_manifest,
        gateway_profile_json=gateway_profile,
        provider_plan_json={"enabled": False},
    )


@pytest.mark.parametrize(
    ("gateway_profile", "provider_disabled"),
    [
        (
            {
                "contract_version": "ai-gateway-profile.v1",
                "adapter_key": "openai-compatible",
                "provider_enabled": False,
                "qualification_status": "disabled",
                "streaming_mode": "json",
                "image_url_ttl_seconds": 300,
                "allowed_actual_models": [],
            },
            True,
        ),
        (
            {
                "contract_version": "ai-gateway-profile.v1",
                "adapter_key": "openai-compatible",
                "provider_enabled": True,
                "qualification_status": "qualified",
                "streaming_mode": "json",
                "image_url_ttl_seconds": 300,
                "allowed_actual_models": ["provider-model"],
            },
            False,
        ),
    ],
)
def test_task_assignment_accepts_consistent_frozen_v2_gateway_profile(
    gateway_profile: dict[str, Any], provider_disabled: bool
) -> None:
    from apps.backend.core.pipeline import build_default_registry
    from apps.backend.services.runtime.service.task_service import TaskService

    service = object.__new__(TaskService)
    service.registry = build_default_registry()
    config = _frozen_task_config(
        gateway_profile=gateway_profile,
        capability_provider_disabled=provider_disabled,
    )

    profile_key, _, _ = service._validate_assignable_config(
        config=config,
        allowed_profiles=frozenset({"xray_primary_v1"}),
    )

    assert profile_key == "xray_primary_v1"


def test_task_create_requires_and_normalizes_species_for_diagnose() -> None:
    from apps.backend.schemas.task import TaskCreate

    payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_1",
        task_type="diagnose",
        species=" DOG ",
        trace_id="trace_1",
    )

    assert payload.species == "dog"

    with pytest.raises(ValidationError, match="task_species_required_for_diagnose"):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_2",
            task_type="diagnose",
            trace_id="trace_2",
        )
    with pytest.raises(ValidationError, match="task_species_not_supported"):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_3",
            task_type="diagnose",
            species="rabbit",
            trace_id="trace_3",
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("species", "expected_config_key"),
    (
        ("cat", "xray_diagnose_cat"),
        ("dog", "xray_diagnose_dog"),
    ),
)
async def test_task_create_selects_species_specific_active_config(
    species: str,
    expected_config_key: str,
) -> None:
    from types import SimpleNamespace

    from apps.backend.schemas.task import TaskCreate
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    service = object.__new__(TaskService)

    async def get_study(_: str) -> SimpleNamespace:
        return SimpleNamespace(
            id="study_1",
            session_id="session_1",
            status="ready",
            revision_id="revision_1",
            resolved_manifest_sha256="a" * 64,
            modality_type="xray",
        )

    async def get_session(_: str) -> SimpleNamespace:
        return SimpleNamespace(requester_id="caller_1", status="open")

    async def get_existing(_: str) -> None:
        return None

    selected: dict[str, str] = {}

    async def get_active_config(**kwargs: str) -> None:
        selected.update(kwargs)
        return None

    service.study_dal = SimpleNamespace(get_by_id=get_study)
    service.session_dal = SimpleNamespace(get_by_id_for_update=get_session)
    service.task_dal = SimpleNamespace(get_by_business_key=get_existing)
    service._get_active_config = get_active_config

    with pytest.raises(TaskStateConflictError, match="task_config_not_active"):
        await service.create_task(
            payload=TaskCreate(
                study_id="study_1",
                study_revision_id="revision_1",
                request_id=f"request_{species}",
                task_type="diagnose",
                species=species,
                trace_id=f"trace_{species}",
            ),
            caller=SimpleNamespace(subject_id="caller_1"),
        )

    assert selected == {
        "config_key": expected_config_key,
        "modality_type": "xray",
        "task_type": "diagnose",
    }


@pytest.mark.parametrize(
    ("species", "config_key", "prompt_key"),
    (
        ("cat", "xray_diagnose_cat", "xray_cat_primary"),
        ("dog", "xray_diagnose_dog", "xray_dog_primary"),
    ),
)
def test_task_species_config_binding_is_exact(
    species: str,
    config_key: str,
    prompt_key: str,
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    correct = SimpleNamespace(
        config_key=config_key,
        prompt_key=prompt_key,
        profile_key="xray_primary_v2",
    )
    TaskService._validate_species_config_binding(
        config=correct,
        task_type="diagnose",
        species=species,
    )
    TaskService._validate_species_config_binding(
        config=SimpleNamespace(
            config_key=config_key,
            prompt_key=prompt_key,
            profile_key="xray_targeted_review_v2",
        ),
        task_type="diagnose",
        species=species,
    )

    for invalid in (
        SimpleNamespace(
            config_key="xray_diagnose_dog" if species == "cat" else "xray_diagnose_cat",
            prompt_key=prompt_key,
            profile_key="xray_primary_v2",
        ),
        SimpleNamespace(
            config_key=config_key,
            prompt_key="xray_dog_primary" if species == "cat" else "xray_cat_primary",
            profile_key="xray_primary_v2",
        ),
        SimpleNamespace(
            config_key=config_key,
            prompt_key=prompt_key,
            profile_key="xray_targeted_review_v1",
        ),
    ):
        with pytest.raises(TaskStateConflictError, match="task_config_invalid"):
            TaskService._validate_species_config_binding(
                config=invalid,
                task_type="diagnose",
                species=species,
            )


@pytest.mark.anyio
async def test_task_active_config_uses_explicit_targeted_experiment_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.config_contract import activation_slot_sha256
    from apps.backend.core.config import settings
    from apps.backend.services.runtime.service.task_service import TaskService

    experiment_config = SimpleNamespace(id="config_targeted")
    slots: list[str] = []

    class FakeConfigDal:
        async def get_active(self, slot: str):
            slots.append(slot)
            return experiment_config

    monkeypatch.setattr(
        settings,
        "XRAY_TARGETED_EXPERIMENT_SCOPE_KEY",
        "full-chain-local-v1",
    )
    service = object.__new__(TaskService)
    service.config_dal = FakeConfigDal()

    resolved = await service._get_active_config(
        config_key="xray_diagnose_cat",
        modality_type="xray",
        task_type="diagnose",
    )

    assert resolved is experiment_config
    assert slots == [
        activation_slot_sha256(
            config_key="xray_diagnose_cat",
            modality_type="xray",
            task_type="diagnose",
            activation_scope="experiment",
            scope_key="full-chain-local-v1",
        )
    ]


def test_task_create_normalizes_strict_clinical_context_v1() -> None:
    from apps.backend.schemas.task import TaskCreate

    context = _clinical_context_v1()
    context["source"]["system"] = " ms-ai-fast "
    context["chief_complaint"] = " 间歇性咳嗽三天 "
    payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_1",
        task_type="diagnose",
        species="dog",
        clinical_context=context,
        trace_id="trace_1",
    )

    frozen = payload.clinical_context.model_dump(mode="json")
    assert frozen == {
        "contract_version": "xray-clinical-context.v1",
        "source": {
            "system": "ms-ai-fast",
            "recorded_at": "2026-08-28T02:30:00Z",
            "temporal_scope": "available_at_request",
        },
        "chief_complaint": "间歇性咳嗽三天",
        "study_reason": "评估胸部影像",
    }


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        (
            lambda context: context.update({"expected_status": "abnormal"}),
            "extra_forbidden",
        ),
        (
            lambda context: (
                context.pop("chief_complaint"),
                context.pop("study_reason"),
            ),
            "task_clinical_context_fact_required",
        ),
        (
            lambda context: context["source"].update(
                {"recorded_at": "2026-08-28T10:30:00"}
            ),
            "datetime_timezone_required",
        ),
        (
            lambda context: context.update(
                {
                    "chief_complaint": "症" * 1500,
                    "study_reason": "状" * 1500,
                }
            ),
            "task_clinical_context_too_large",
        ),
    ],
)
def test_task_create_rejects_unsafe_or_unbounded_clinical_context(
    mutation,
    error_code: str,
) -> None:
    from apps.backend.schemas.task import TaskCreate

    context = _clinical_context_v1()
    mutation(context)
    with pytest.raises(ValidationError, match=error_code):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_1",
            task_type="diagnose",
            species="dog",
            clinical_context=context,
            trace_id="trace_1",
        )


def test_task_create_rejects_clinical_context_for_replay() -> None:
    from apps.backend.schemas.task import TaskCreate

    with pytest.raises(ValidationError, match="task_clinical_context_diagnose_only"):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_1",
            task_type="replay",
            clinical_context=_clinical_context_v1(),
            trace_id="trace_1",
        )


def test_task_request_snapshot_freezes_species_parameter() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import TaskService

    config = SimpleNamespace(
        id="config_1",
        config_key="xray_diagnose",
        version=1,
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        config_contract_version="ai-config.v2",
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256="f" * 64,
        stage_registry_contract_version="stage-registry.v1",
    )
    snapshot = TaskService._build_request_snapshot(
        study=SimpleNamespace(
            id="study_1",
            revision_id="revision_1",
            resolved_manifest_sha256="1" * 64,
        ),
        series=[],
        config=config,
        profile_key="xray_primary_v1",
        compiled_profile={"profile_key": "xray_primary_v1", "stages": []},
        task_type="diagnose",
        species="cat",
    )

    assert snapshot["species"] == "cat"


def test_task_request_snapshot_freezes_and_hashes_clinical_context() -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.clinical_context import read_frozen_clinical_context
    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.schemas.task import TaskClinicalContext
    from apps.backend.services.runtime.service.task_service import TaskService

    config = SimpleNamespace(
        id="config_1",
        config_key="xray_diagnose",
        version=1,
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        config_contract_version="ai-config.v2",
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256="f" * 64,
        stage_registry_contract_version="stage-registry.v1",
    )
    clinical_context = TaskClinicalContext.model_validate(_clinical_context_v1())
    common = {
        "study": SimpleNamespace(
            id="study_1",
            revision_id="revision_1",
            resolved_manifest_sha256="1" * 64,
        ),
        "series": [],
        "config": config,
        "profile_key": "xray_primary_v1",
        "compiled_profile": {"profile_key": "xray_primary_v1", "stages": []},
        "task_type": "diagnose",
        "species": "cat",
    }

    snapshot = TaskService._build_request_snapshot(
        **common,
        clinical_context=clinical_context,
    )
    without_context = TaskService._build_request_snapshot(**common)
    frozen = clinical_context.model_dump(mode="json")

    assert snapshot["clinical_context_policy_version"] == ("xray-clinical-context.v1")
    assert snapshot["clinical_context_allowlist"] == frozen
    assert snapshot["clinical_context_sha256"] == sha256_json(frozen)
    assert read_frozen_clinical_context(snapshot).payload == frozen
    assert TaskService._sha(snapshot) != TaskService._sha(without_context)


def test_frozen_clinical_context_is_canonical_and_rejects_hash_drift() -> None:
    from apps.backend.core.ai.clinical_context import (
        ClinicalContextContractError,
        freeze_clinical_context,
        read_frozen_clinical_context,
    )

    context = _clinical_context_v1()
    reordered = {
        "study_reason": context["study_reason"],
        "chief_complaint": context["chief_complaint"],
        "source": {
            "temporal_scope": context["source"]["temporal_scope"],
            "recorded_at": context["source"]["recorded_at"],
            "system": context["source"]["system"],
        },
        "contract_version": context["contract_version"],
    }
    first = freeze_clinical_context(context)
    second = freeze_clinical_context(reordered)

    assert first.snapshot_fields() == second.snapshot_fields()
    corrupted = first.snapshot_fields()
    corrupted["clinical_context_sha256"] = "0" * 64
    with pytest.raises(
        ClinicalContextContractError,
        match="task_clinical_context_snapshot_mismatch",
    ):
        read_frozen_clinical_context(corrupted)


def test_evaluation_export_requires_same_context_for_paired_arms() -> None:
    from types import SimpleNamespace

    from apps.backend.services.evaluation_control.service.evaluation_export_service import (
        EvaluationExportService,
        EvaluationExportValidationError,
    )

    control = SimpleNamespace(
        case_id="case_1",
        clinical_context_policy_version="xray-clinical-context.v1",
        clinical_context_sha256="a" * 64,
    )
    matching_candidate = SimpleNamespace(
        case_id="case_1",
        clinical_context_policy_version="xray-clinical-context.v1",
        clinical_context_sha256="a" * 64,
    )
    EvaluationExportService._validate_context_arm_consistency(
        [control, matching_candidate]
    )

    mismatched_candidate = SimpleNamespace(
        case_id="case_1",
        clinical_context_policy_version="xray-clinical-context.v1",
        clinical_context_sha256="b" * 64,
    )
    with pytest.raises(
        EvaluationExportValidationError,
        match="evaluation_export_clinical_context_arm_mismatch",
    ):
        EvaluationExportService._validate_context_arm_consistency(
            [control, mismatched_candidate]
        )


def test_task_request_snapshot_rejects_missing_species_for_diagnose() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    config = SimpleNamespace(
        id="config_1",
        config_key="xray_diagnose",
        version=1,
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        config_contract_version="ai-config.v2",
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256="f" * 64,
        stage_registry_contract_version="stage-registry.v1",
    )

    with pytest.raises(TaskStateConflictError, match="task_species_snapshot_invalid"):
        TaskService._build_request_snapshot(
            study=SimpleNamespace(
                id="study_1",
                revision_id="revision_1",
                resolved_manifest_sha256="1" * 64,
            ),
            series=[],
            config=config,
            profile_key="xray_primary_v1",
            compiled_profile={"profile_key": "xray_primary_v1", "stages": []},
            task_type="diagnose",
            species=None,
        )


def test_task_request_snapshot_keeps_replay_species_optional_for_v2_config() -> None:
    from types import SimpleNamespace

    from apps.backend.core.pipeline import ZERO_MODEL_PROFILE
    from apps.backend.services.runtime.service import task_service

    config = SimpleNamespace(
        id="config_1",
        config_key="zero_model_replay",
        version=1,
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        config_contract_version="ai-config.v2",
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256="f" * 64,
        stage_registry_contract_version="stage-registry.v1",
    )

    snapshot = task_service.TaskService._build_request_snapshot(
        study=SimpleNamespace(
            id="study_1",
            revision_id="revision_1",
            resolved_manifest_sha256="1" * 64,
        ),
        series=[],
        config=config,
        profile_key=ZERO_MODEL_PROFILE,
        compiled_profile={"profile_key": ZERO_MODEL_PROFILE, "stages": []},
        task_type="replay",
        species=None,
    )

    assert snapshot["species"] == "unknown"


def test_complete_medical_result_v2_requires_frozen_per_image_snapshot() -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import (
        build_series_manifest_legacy,
        build_study_manifest,
    )
    from apps.backend.core.pipeline import XRAY_PRIMARY_PROFILE_V2
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    image = SimpleNamespace(
        id="image_1",
        series_id="series_1",
        logical_image_key="logical_1",
        image_version_no=1,
        sequence_no=1,
        image_role="source",
        image_kind="xray",
        file_format="jpeg",
        projection=None,
        technical_metadata_json=None,
        storage_profile="primary",
        object_key="images/one.jpg",
        object_version_id=None,
        sha256="a" * 64,
        size_bytes=10,
        content_type="image/jpeg",
        status="ready",
    )
    legacy_manifest = build_series_manifest_legacy([image])
    series = SimpleNamespace(
        id="series_1",
        series_key="series-key-1",
        series_no=1,
        actual_image_count=1,
        manifest_sha256=legacy_manifest.sha256,
    )
    study_manifest = build_study_manifest([series])
    study = SimpleNamespace(
        id="study_1",
        revision_id="revision_1",
        resolved_manifest_sha256=study_manifest.sha256,
    )
    config = SimpleNamespace(
        id="config_1",
        config_key="xray_diagnose",
        version="v2",
        config_sha256="a" * 64,
        release_fingerprint="b" * 64,
        config_contract_version="ai-config.v2",
        prompt_content_sha256="c" * 64,
        model_snapshot_sha256="d" * 64,
        output_schema_sha256="e" * 64,
        compiled_pipeline_sha256="f" * 64,
        stage_registry_contract_version="stage-contract.v1",
    )

    with pytest.raises(
        TaskStateConflictError,
        match="task_result_contract_requires_snapshot_v3",
    ):
        TaskService._build_request_snapshot(
            study=study,
            series=[series],
            config=config,
            profile_key=XRAY_PRIMARY_PROFILE_V2,
            compiled_profile={"profile_key": XRAY_PRIMARY_PROFILE_V2},
            task_type="diagnose",
            species="dog",
            series_images=[image],
        )


def test_task_assignment_rejects_v2_gateway_capability_mismatch() -> None:
    from apps.backend.core.pipeline import build_default_registry
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    service = object.__new__(TaskService)
    service.registry = build_default_registry()
    config = _frozen_task_config(
        gateway_profile={
            "contract_version": "ai-gateway-profile.v1",
            "adapter_key": "openai-compatible",
            "provider_enabled": True,
            "qualification_status": "qualified",
            "streaming_mode": "json",
            "image_url_ttl_seconds": 300,
            "allowed_actual_models": ["provider-model"],
        },
        capability_provider_disabled=True,
    )

    with pytest.raises(
        TaskStateConflictError, match="task_config_gateway_profile_mismatch"
    ):
        service._validate_assignable_config(
            config=config,
            allowed_profiles=frozenset({"xray_primary_v1"}),
        )


def test_task_assignment_rejects_unqualified_v2_provider_profile() -> None:
    from apps.backend.core.pipeline import build_default_registry
    from apps.backend.services.runtime.service import task_service

    service = object.__new__(task_service.TaskService)
    service.registry = build_default_registry()
    config = _frozen_task_config(
        gateway_profile={
            "contract_version": "ai-gateway-profile.v1",
            "adapter_key": "openai-compatible",
            "provider_enabled": False,
            "qualification_status": "disabled",
            "streaming_mode": "json",
            "image_url_ttl_seconds": 300,
            "allowed_actual_models": [],
        },
        capability_provider_disabled=True,
    )
    config.gateway_profile_json = {
        "contract_version": "ai-gateway-profile.v1",
        "adapter_key": "openai-compatible",
        "provider_enabled": True,
        "qualification_status": "disabled",
        "streaming_mode": "json",
        "image_url_ttl_seconds": 300,
        "allowed_actual_models": ["provider-model"],
    }

    with pytest.raises(
        task_service.TaskStateConflictError,
        match="gateway_profile_qualification_required",
    ):
        service._validate_assignable_config(
            config=config,
            allowed_profiles=frozenset({"xray_primary_v1"}),
        )


def test_task_assignment_preserves_v1_provider_disabled_compatibility() -> None:
    from apps.backend.core.pipeline import build_default_registry
    from apps.backend.services.runtime.service.task_service import TaskService

    service = object.__new__(TaskService)
    service.registry = build_default_registry()
    config = _frozen_task_config(
        gateway_profile=None,
        capability_provider_disabled=True,
        config_contract_version="ai-config.v1",
    )

    profile_key, _, _ = service._validate_assignable_config(
        config=config,
        allowed_profiles=frozenset({"xray_primary_v1"}),
    )

    assert profile_key == "xray_primary_v1"


def test_gateway_profile_rejects_ttl_above_oss_signer_limit() -> None:
    profile = normalize_gateway_profile(None)
    profile["image_url_ttl_seconds"] = 901

    with pytest.raises(GatewayContractError, match="gateway_profile_invalid"):
        normalize_gateway_profile(profile)


def test_oss_object_store_normalizes_host_only_endpoint_to_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging import object_store as object_store_module

    captured: dict[str, str] = {}

    class FakeAuth:
        def __init__(self, access_key_id: str, access_key_secret: str) -> None:
            captured["access_key_id"] = access_key_id
            captured["access_key_secret"] = access_key_secret

    class FakeBucket:
        def __init__(self, auth, endpoint: str, bucket_name: str) -> None:
            del auth
            captured["endpoint"] = endpoint
            captured["bucket_name"] = bucket_name

    monkeypatch.setattr(object_store_module.oss2, "Auth", FakeAuth)
    monkeypatch.setattr(object_store_module.oss2, "Bucket", FakeBucket)
    store = object_store_module.OSSObjectStore(
        SimpleNamespace(
            OSS_ACCESS_KEY_ID="test-id",
            OSS_ACCESS_KEY_SECRET="test-secret",
            OSS_BUCKET_NAME="test-bucket",
            OSS_ENDPOINT="oss-cn-example.aliyuncs.com",
            OSS_UPLOAD_ENDPOINT="",
            OSS_STORAGE_PROFILE="primary",
            OSS_SIGNED_URL_TTL_SECONDS=300,
        )
    )

    assert store.endpoint == "https://oss-cn-example.aliyuncs.com"
    assert captured["endpoint"] == "https://oss-cn-example.aliyuncs.com"


@pytest.mark.anyio
async def test_oss_object_store_head_reads_mime_and_sse_from_head_response() -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging.object_store import OSSObjectStore

    calls: list[tuple[str, str]] = []

    class FakeBucket:
        def head_object(self, object_key: str):
            calls.append(("head_object", object_key))
            return SimpleNamespace(
                status=200,
                content_length=17,
                content_type=None,
                etag='"etag-1"',
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-OSS-Server-Side-Encryption": "AES256",
                    "X-OSS-Server-Side-Encryption-Key-Id": "kms-key-version",
                    "X-OSS-Version-Id": "version-1",
                },
            )

        def get_object_meta(self, object_key: str):
            del object_key
            raise AssertionError("basic_metadata_endpoint_must_not_be_used")

    store = object.__new__(OSSObjectStore)
    store.storage_profile = "primary"
    store._bucket = FakeBucket()

    head = await store.head_object(object_key="image/image_1/1/source.dcm")

    assert calls == [("head_object", "image/image_1/1/source.dcm")]
    assert head.content_type == "application/octet-stream"
    assert head.server_side_encryption == "AES256"
    assert head.kms_key_version == "kms-key-version"
    assert head.object_version_id == "version-1"


def test_build_oss_attempt_image_signer_uses_runtime_oss_host_and_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway import image_signer as image_signer_module

    class FakeObjectStore:
        endpoint = "https://oss-cn-example.aliyuncs.com"
        bucket_name = "qualified-bucket"
        storage_profile = "primary"

        def __init__(self, config) -> None:
            assert config.OSS_SIGNED_URL_TTL_SECONDS == 180

    monkeypatch.setattr(image_signer_module, "OSSObjectStore", FakeObjectStore)
    signer = image_signer_module.build_oss_attempt_image_signer(
        config=SimpleNamespace(OSS_SIGNED_URL_TTL_SECONDS=180)
    )

    assert signer.max_ttl_seconds == 180
    assert signer.allowed_signed_url_hosts == (
        "oss-cn-example.aliyuncs.com",
        "qualified-bucket.oss-cn-example.aliyuncs.com",
    )


@pytest.mark.anyio
async def test_nacos_fetch_malformed_200_fails_closed_instead_of_fallback() -> None:
    class FakeNacosClient:
        async def request(self, method: str, path: str, **kwargs):
            assert method == "GET"
            assert path == "/v3/client/ai/prompt"
            assert kwargs["params"] == {
                "namespaceId": "ns",
                "promptKey": "ms.ai-pic.x.default.zh-CN",
                "version": None,
                "label": None,
            }
            return ["not", "an", "object"]

    client = NacosPromptSourceClient(
        server_addr="http://nacos.example",
        namespace_id="ns",
        context_path="/nacos",
        client=FakeNacosClient(),
    )
    with pytest.raises(PromptSourceError, match="prompt_source_nacos_payload_invalid"):
        await client.fetch(data_id="ms.ai-pic.x.default.zh-CN")
    await client.aclose()


@pytest.mark.anyio
async def test_oss_attempt_image_signer_revalidates_order_and_hides_url_repr() -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.image_signer import OSSAttemptImageSigner

    class FakeObjectStore:
        storage_profile = "primary"

        def __init__(self) -> None:
            self.validated: list[str] = []

        async def validate_image_object(self, **kwargs):
            self.validated.append(kwargs["object_key"])
            return SimpleNamespace(
                object_ref=SimpleNamespace(
                    storage_profile="primary",
                    object_key=kwargs["object_key"],
                    object_version_id=kwargs["expected_object_version_id"],
                    sha256=kwargs["expected_sha256"],
                    size_bytes=kwargs["expected_size_bytes"],
                    content_type=kwargs["declared_content_type"],
                )
            )

        async def sign_download_url(self, *, object_key: str, expires_seconds: int):
            assert expires_seconds == 60
            return f"https://bucket.oss.example/{object_key}?credential=sensitive"

    store = FakeObjectStore()
    signer = OSSAttemptImageSigner(
        object_store=store,
        allowed_signed_url_hosts=("bucket.oss.example",),
    )
    images = await signer.sign(
        attempt_plan={
            "attempt_id": "attempt_1",
            "image_count_requested": 2,
            "image_inputs": (
                {
                    "sequence_no": 1,
                    "storage_profile": "primary",
                    "object_key": "image/one.jpg",
                    "object_version_id": "v1",
                    "mime_type": "image/jpeg",
                    "sha256": "a" * 64,
                    "size_bytes": 10,
                },
                {
                    "sequence_no": 2,
                    "storage_profile": "primary",
                    "object_key": "image/two.png",
                    "object_version_id": "v2",
                    "mime_type": "image/png",
                    "sha256": "b" * 64,
                    "size_bytes": 20,
                },
            ),
        },
        ttl_seconds=60,
    )
    assert [image.sequence_no for image in images] == [1, 2]
    assert store.validated == ["image/one.jpg", "image/two.png"]
    assert "credential=sensitive" not in repr(images[0])


@pytest.mark.anyio
async def test_stage_execution_worker_uses_gateway_client_without_secret_or_response_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )
    from apps.backend.workers.imaging_worker.stage_execution import StageExecutionWorker

    calls: list[str] = []
    finalized: dict[str, Any] = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    class FakeSigner:
        async def sign(self, **kwargs):
            calls.append("sign")
            return []

    class FakeGateway:
        async def chat_completions(self, payload, *, idempotency_key):
            calls.append("provider")
            assert idempotency_key == "idem-1"
            return {
                "request_id": "provider-1",
                "body": {
                    "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
                    "model": "provider-model",
                    "usage": {"total_tokens": 1},
                },
            }

    async def claim(self, **kwargs):
        return SimpleNamespace(id="stage_1")

    async def prepare(self, **kwargs):
        return {"network_required": True, "attempt_id": "attempt_1"}

    async def load(self, **kwargs):
        return _network_plan(request_id="event_1")

    async def finalize_attempt(self, **kwargs):
        calls.append("attempt_finalize")
        finalized.update(kwargs)
        return {"status": "succeeded", "result_disposition": "accepted"}

    async def finalize_stage(self, **kwargs):
        calls.append("stage_finalize")
        return {"status": "completed"}

    monkeypatch.setattr(ImagingExecutionService, "claim", claim)
    monkeypatch.setattr(ImagingExecutionService, "prepare_stage_execution", prepare)
    monkeypatch.setattr(ImagingExecutionService, "finalize_ai_stage", finalize_stage)
    monkeypatch.setattr(AIRequestService, "load_attempt_for_network", load)
    monkeypatch.setattr(AIRequestService, "finalize_attempt", finalize_attempt)

    result = await StageExecutionWorker(
        session_factory_=session_factory,
        gateway_client=FakeGateway(),
        image_signer=FakeSigner(),
    ).execute(
        event_id="event_1",
        message={},
        message_version="v1",
        trace_id="trace_1",
        owner_id="worker_1",
        lease_seconds=120,
    )
    assert result["outcome"] == "completed"
    assert calls == ["sign", "provider", "attempt_finalize", "stage_finalize"]
    assert "object_ref" not in finalized


@pytest.mark.anyio
async def test_stage_execution_worker_persists_receipt_on_definite_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )
    from apps.backend.workers.imaging_worker.stage_execution import StageExecutionWorker

    receipt = {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": 1,
        "images": [
            {
                "sequence_no": 1,
                "image_id": "image_1",
                "sha256": "a" * 64,
                "projection": "VD",
                "projection_provenance": "caller_declared",
                "mime_type": "image/jpeg",
            }
        ],
    }
    captured: dict[str, Any] = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    async def claim(self, **kwargs):
        return SimpleNamespace(id="stage_1")

    async def prepare(self, **kwargs):
        return {"network_required": True, "attempt_id": "attempt_1"}

    async def load(self, **kwargs):
        return _network_plan(request_id="event_1")

    async def execute_network(**kwargs):
        raise GatewayDefiniteResponseError(
            "provider_response_json_invalid",
            image_receipt=receipt,
            image_manifest_sha256="b" * 64,
            image_count_sent=1,
            provider_request_id="provider-request-1",
            actual_model="provider-model",
            usage_json={"total_tokens": 17},
            response_sha256="c" * 64,
        )

    async def finalize_failure(self, **kwargs):
        captured["failure"] = kwargs
        return {"status": "failed", "result_disposition": "failed"}

    async def finalize_stage(self, **kwargs):
        captured["stage"] = kwargs
        return {"status": "failed"}

    monkeypatch.setattr(ImagingExecutionService, "claim", claim)
    monkeypatch.setattr(ImagingExecutionService, "prepare_stage_execution", prepare)
    monkeypatch.setattr(ImagingExecutionService, "finalize_ai_stage", finalize_stage)
    monkeypatch.setattr(AIRequestService, "load_attempt_for_network", load)
    monkeypatch.setattr(
        AIRequestService,
        "execute_gateway_attempt_network",
        execute_network,
    )
    monkeypatch.setattr(
        AIRequestService,
        "finalize_attempt_failure",
        finalize_failure,
    )

    result = await StageExecutionWorker(
        session_factory_=session_factory,
    ).execute(
        event_id="event_1",
        message={},
        message_version="v1",
        trace_id="trace_1",
        owner_id="worker_1",
        lease_seconds=120,
    )

    assert result["outcome"] == "completed"
    assert captured["failure"] == {
        "attempt_id": "attempt_1",
        "error_code": "provider_response_json_invalid",
        "unknown": False,
        "image_receipt": receipt,
        "image_manifest_sha256": "b" * 64,
        "image_count_sent": 1,
        "provider_request_id": "provider-request-1",
        "actual_model": "provider-model",
        "usage_json": {"total_tokens": 17},
        "response_sha256": "c" * 64,
    }
    assert captured["stage"]["call_result"] == {
        "status": "failed",
        "result_disposition": "failed",
    }


def test_ai_attempt_reconcile_beat_schedule_is_opt_in_and_routes_explicitly() -> None:
    from apps.backend.workers.imaging_worker.celery_app import (
        AI_ATTEMPT_RECONCILE_SCHEDULE_KEY,
        AI_ATTEMPT_RECONCILE_TASK_NAME,
        build_ai_attempt_reconcile_schedule,
        topology,
    )

    assert (
        build_ai_attempt_reconcile_schedule(
            enabled=False,
            interval_seconds=60,
            batch_limit=50,
        )
        == {}
    )
    schedule = build_ai_attempt_reconcile_schedule(
        enabled=True,
        interval_seconds=60,
        batch_limit=50,
    )

    assert set(schedule) == {AI_ATTEMPT_RECONCILE_SCHEDULE_KEY}
    entry = schedule[AI_ATTEMPT_RECONCILE_SCHEDULE_KEY]
    assert entry["task"] == AI_ATTEMPT_RECONCILE_TASK_NAME
    assert entry["schedule"] == 60.0
    assert entry["args"] == (50,)
    assert entry["options"] == {
        "queue": topology.queue,
        "exchange": topology.exchange,
        "routing_key": topology.routing_key,
    }


@pytest.mark.parametrize(
    ("interval_seconds", "batch_limit", "error_code"),
    [
        (29, 50, "ai_attempt_reconcile_interval_invalid"),
        (3601, 50, "ai_attempt_reconcile_interval_invalid"),
        (60, 0, "ai_attempt_reconcile_batch_limit_invalid"),
        (60, 501, "ai_attempt_reconcile_batch_limit_invalid"),
    ],
)
def test_ai_attempt_reconcile_beat_schedule_rejects_invalid_bounds(
    interval_seconds: int,
    batch_limit: int,
    error_code: str,
) -> None:
    from apps.backend.workers.imaging_worker.celery_app import (
        build_ai_attempt_reconcile_schedule,
    )

    with pytest.raises(ValueError, match=f"^{error_code}$"):
        build_ai_attempt_reconcile_schedule(
            enabled=True,
            interval_seconds=interval_seconds,
            batch_limit=batch_limit,
        )


def test_ai_attempt_reconcile_policy_v1_has_immutable_bounds() -> None:
    from pydantic import ValidationError

    from apps.backend.core.config import Settings

    policy = Settings(
        _env_file=None,
        AI_PLATFORM_OPENAI_BASE_URL="",
        AI_PLATFORM_API_KEY="",
        AI_ATTEMPT_RECONCILE_POLICY_VERSION="ai-attempt-reconcile.v1",
        AI_ATTEMPT_RECONCILE_MAX_COUNT=3,
        AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS=10_800,
    )
    assert policy.AI_ATTEMPT_RECONCILE_MAX_COUNT == 3
    assert policy.AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS == 10_800

    with pytest.raises(
        ValidationError,
        match="ai_attempt_reconcile_policy_version_invalid",
    ):
        Settings(
            _env_file=None,
            AI_PLATFORM_OPENAI_BASE_URL="",
            AI_PLATFORM_API_KEY="",
            AI_ATTEMPT_RECONCILE_POLICY_VERSION="ai-attempt-reconcile.v2",
        )
    with pytest.raises(
        ValidationError,
        match="ai_attempt_reconcile_policy_v1_values_invalid",
    ):
        Settings(
            _env_file=None,
            AI_PLATFORM_OPENAI_BASE_URL="",
            AI_PLATFORM_API_KEY="",
            AI_ATTEMPT_RECONCILE_MAX_COUNT=2,
        )


def test_ai_attempt_reconcile_task_clamps_batch_and_logs_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.workers.imaging_worker import celery_app as celery_module

    captured: dict[str, Any] = {}

    class FakeWorker:
        def __init__(self, **kwargs):
            captured["session_factory"] = kwargs["session_factory_"]

        async def run_once(self, **kwargs):
            captured["run_once"] = kwargs
            return {
                "due_scanned": 0,
                "due_remaining_estimate": 0,
                "claimed": 0,
                "succeeded": 0,
                "failed": 0,
                "unknown": 0,
                "unsupported": 0,
                "conflicted": 0,
                "stage_pending": 0,
                "duration_ms": 1,
            }

    async def dispose() -> None:
        captured["disposed"] = True

    def log_info(message: str, payload: str) -> None:
        captured["log"] = (message, json.loads(payload))

    monkeypatch.setattr(celery_module.settings, "BROKER_ENABLED", True)
    monkeypatch.setattr(celery_module, "AIAttemptReconcileWorker", FakeWorker)
    monkeypatch.setattr(celery_module, "async_engine", SimpleNamespace(dispose=dispose))
    monkeypatch.setattr(celery_module.logger, "info", log_info)

    assert celery_module.reconcile_ai_attempts.run(limit=999) is None
    assert captured["run_once"] == {
        "limit": 500,
        "lease_seconds": (celery_module.settings.AI_ATTEMPT_RECONCILE_LEASE_SECONDS),
        "retry_seconds": (celery_module.settings.AI_ATTEMPT_RECONCILE_RETRY_SECONDS),
        "max_reconcile_count": (celery_module.settings.AI_ATTEMPT_RECONCILE_MAX_COUNT),
        "max_unknown_age_seconds": (
            celery_module.settings.AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS
        ),
    }
    assert captured["disposed"] is True
    assert captured["log"][0] == "ai_attempt_reconcile_completed %s"
    assert captured["log"][1]["duration_ms"] == 1


@pytest.mark.anyio
async def test_ai_attempt_dal_reconcile_filters_due_and_claims_with_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from sqlalchemy.sql import operators

    from apps.backend.crud.ai_call_attempt import AICallAttemptDal

    now = datetime(2026, 8, 24, 12, 0, 0)
    candidate = SimpleNamespace(id="attempt_due", state_version=7)
    captured: dict[str, Any] = {}
    dal = AICallAttemptDal(db=object())

    async def fake_get_datas(**kwargs):
        captured["page"] = kwargs
        return [candidate]

    async def fake_cas_put_data(**kwargs):
        captured["claim"] = kwargs
        return None

    monkeypatch.setattr(dal, "get_datas", fake_get_datas)
    monkeypatch.setattr(dal, "cas_put_data", fake_cas_put_data)

    assert await dal.page_reconcile_candidates(now=now, limit=10) == [candidate]
    page_where = captured["page"]["v_where"]
    assert page_where[0].left.key == "status"
    assert page_where[0].right.value == "unknown"
    assert page_where[1].left.key == "next_reconcile_at"
    assert page_where[1].operator is operators.is_not
    assert page_where[2].left.key == "next_reconcile_at"
    assert page_where[2].operator is operators.le
    assert page_where[2].right.value == now
    assert captured["page"]["v_order_field"] == "next_reconcile_at"

    lease_expires_at = now + timedelta(seconds=120)
    unknown_cutoff = now - timedelta(seconds=10_800)
    assert (
        await dal.claim_reconcile_candidate(
            attempt_id="attempt_due",
            expected_version=7,
            now=now,
            lease_expires_at=lease_expires_at,
            unknown_cutoff=unknown_cutoff,
            max_reconcile_count=3,
        )
        is None
    )
    claim = captured["claim"]
    assert claim["data_id"] == "attempt_due"
    assert claim["expected_version"] == 7
    assert claim["data"]["next_reconcile_at"] == lease_expires_at
    count_increment = claim["data"]["reconcile_count"]
    assert count_increment.left.key == "reconcile_count"
    assert count_increment.operator is operators.add
    assert count_increment.right.value == 1
    claim_where = claim["v_where"]
    assert claim_where[0].right.value == "unknown"
    assert claim_where[1].operator is operators.is_not
    assert claim_where[2].operator is operators.le
    assert claim_where[2].right.value == now
    assert claim_where[3].left.key == "reconcile_count"
    assert claim_where[3].operator is operators.lt
    assert claim_where[3].right.value == 3

    assert (
        await dal.claim_exhausted_reconcile_candidate(
            attempt_id="attempt_due",
            expected_version=7,
            now=now,
            lease_expires_at=lease_expires_at,
            unknown_cutoff=unknown_cutoff,
            max_reconcile_count=3,
        )
        is None
    )
    exhausted_claim = captured["claim"]
    assert exhausted_claim["data"] == {"next_reconcile_at": lease_expires_at}
    assert len(exhausted_claim["v_where"]) == 4


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("lookup_status", "apply_result", "expected_counter", "expected_stage_pending"),
    [
        ("unknown", None, "unknown", 0),
        ("unsupported", None, "unsupported", 0),
        ("failed", "stage_restored", "failed", 0),
        ("succeeded", "attempt_finalized_stage_pending", "succeeded", 1),
    ],
)
async def test_ai_attempt_reconcile_worker_converges_each_lookup_status(
    monkeypatch: pytest.MonkeyPatch,
    lookup_status: str,
    apply_result: str | None,
    expected_counter: str,
    expected_stage_pending: int,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    candidate = SimpleNamespace(id="attempt_1", state_version=2)
    plan = {
        "attempt_id": "attempt_1",
        "attempt_state_version": 3,
        "first_unknown_at": None,
        "reconcile_count": (3 if lookup_status in {"succeeded", "failed"} else 1),
        "lookup_authorized": True,
        "limit_reasons": (),
    }
    calls: list[str] = []

    async def list_due(self, **kwargs):
        calls.append("list")
        assert kwargs["limit"] == 11
        return [candidate]

    async def claim(self, **kwargs):
        calls.append("claim")
        return plan

    async def reschedule(self, **kwargs):
        calls.append("reschedule")
        assert kwargs["expected_version"] == 3
        return True

    async def apply(self, **kwargs):
        calls.append("apply")
        return apply_result

    class FakeLookup:
        async def lookup(self, **kwargs):
            calls.append("lookup")
            if lookup_status == "succeeded":
                return AttemptLookupResult(
                    status="succeeded",
                    network_result={"normalized": True},
                )
            return AttemptLookupResult(
                status=lookup_status,
                error_code=f"provider_{lookup_status}",
            )

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)
    monkeypatch.setattr(AIAttemptReconcileService, "reschedule_unknown", reschedule)
    monkeypatch.setattr(AIAttemptReconcileService, "apply_lookup_result", apply)

    outcomes = await AIAttemptReconcileWorker(
        session_factory_=session_factory,
        attempt_lookup=FakeLookup(),
    ).run_once(
        limit=10,
        lease_seconds=120,
        retry_seconds=300,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    )

    assert outcomes["claimed"] == 1
    assert outcomes[expected_counter] == 1
    assert outcomes["stage_pending"] == expected_stage_pending
    assert outcomes["due_scanned"] == 1
    assert outcomes["due_remaining_estimate"] == 0
    assert outcomes["duration_ms"] >= 0
    if lookup_status in {"unknown", "unsupported"}:
        assert calls == ["list", "claim", "lookup", "reschedule"]
    else:
        assert calls == ["list", "claim", "lookup", "apply"]


def test_ai_attempt_reconcile_limit_reasons_use_inclusive_boundaries() -> None:
    from datetime import datetime, timedelta

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )

    now = datetime(2026, 8, 28, 12, 0, 0)
    assert (
        AIAttemptReconcileService.limit_reasons(
            first_unknown_at=now - timedelta(seconds=10_799),
            reconcile_count=2,
            now=now,
            max_reconcile_count=3,
            max_unknown_age_seconds=10_800,
        )
        == ()
    )
    assert AIAttemptReconcileService.limit_reasons(
        first_unknown_at=now - timedelta(seconds=10_800),
        reconcile_count=2,
        now=now,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    ) == ("age",)
    assert AIAttemptReconcileService.limit_reasons(
        first_unknown_at=None,
        reconcile_count=3,
        now=now,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    ) == ("count",)


@pytest.mark.anyio
async def test_ai_attempt_reconcile_worker_terminates_exhausted_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    async def list_due(self, **kwargs):
        return [SimpleNamespace(id="attempt_1", state_version=8)]

    async def claim(self, **kwargs):
        return {
            "attempt_id": "attempt_1",
            "attempt_state_version": 9,
            "first_unknown_at": None,
            "reconcile_count": 3,
            "lookup_authorized": False,
            "limit_reasons": ("count",),
        }

    async def finalize_unresolved(self, **kwargs):
        return {
            "disposition": "terminal_unresolved",
            "stage_outcome": "stage_restored",
        }

    class LookupMustNotRun:
        async def lookup(self, **kwargs):
            raise AssertionError("bounded_attempt_must_not_lookup")

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)
    monkeypatch.setattr(
        AIAttemptReconcileService,
        "finalize_unresolved",
        finalize_unresolved,
    )

    outcomes = await AIAttemptReconcileWorker(
        session_factory_=session_factory,
        attempt_lookup=LookupMustNotRun(),
    ).run_once(
        limit=10,
        lease_seconds=120,
        retry_seconds=300,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    )

    assert outcomes["claimed"] == 1
    assert outcomes["lookup_authorized"] == 0
    assert outcomes["terminal_unresolved"] == 1
    assert outcomes["count_limit_reached"] == 1


@pytest.mark.anyio
async def test_ai_attempt_reconcile_last_lookup_unknown_terminates_without_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    async def list_due(self, **kwargs):
        return [SimpleNamespace(id="attempt_1", state_version=8)]

    async def claim(self, **kwargs):
        return {
            "attempt_id": "attempt_1",
            "attempt_state_version": 9,
            "first_unknown_at": None,
            "reconcile_count": 3,
            "lookup_authorized": True,
            "limit_reasons": (),
        }

    async def reschedule(self, **kwargs):
        raise AssertionError("last_lookup_must_not_reschedule")

    async def finalize_unresolved(self, **kwargs):
        return {
            "disposition": "terminal_unresolved",
            "stage_outcome": "attempt_finalized_stage_pending",
        }

    lookup_count = 0
    replacement_post_count = 0

    class LookupOnly:
        async def lookup(self, **kwargs):
            nonlocal lookup_count
            lookup_count += 1
            return AttemptLookupResult(
                status="unsupported",
                error_code="provider_attempt_lookup_unsupported",
            )

        async def post(self, **kwargs):
            nonlocal replacement_post_count
            replacement_post_count += 1
            raise AssertionError("reconcile_must_never_post_provider")

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)
    monkeypatch.setattr(AIAttemptReconcileService, "reschedule_unknown", reschedule)
    monkeypatch.setattr(
        AIAttemptReconcileService,
        "finalize_unresolved",
        finalize_unresolved,
    )

    outcomes = await AIAttemptReconcileWorker(
        session_factory_=session_factory,
        attempt_lookup=LookupOnly(),
    ).run_once(
        limit=10,
        lease_seconds=120,
        retry_seconds=300,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    )

    assert lookup_count == 1
    assert replacement_post_count == 0
    assert outcomes["lookup_authorized"] == 1
    assert outcomes["unsupported"] == 1
    assert outcomes["terminal_unresolved"] == 1
    assert outcomes["count_limit_reached"] == 1
    assert outcomes["stage_pending"] == 1


@pytest.mark.anyio
async def test_ai_attempt_reconcile_worker_freezes_due_candidate_before_transaction_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    transaction_open = False
    calls: list[tuple[str, str, int]] = []

    class ExpiringCandidate:
        @property
        def id(self) -> str:
            if not transaction_open:
                raise RuntimeError("candidate_accessed_after_transaction_exit")
            return "attempt_1"

        @property
        def state_version(self) -> int:
            if not transaction_open:
                raise RuntimeError("candidate_accessed_after_transaction_exit")
            return 4

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            nonlocal transaction_open
            transaction_open = True
            try:
                yield
            finally:
                transaction_open = False

    def session_factory():
        return FakeSession()

    async def list_due(self, **kwargs):
        return [ExpiringCandidate()]

    async def claim(self, **kwargs):
        calls.append(("claim", kwargs["attempt_id"], kwargs["expected_version"]))
        return None

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)

    outcomes = await AIAttemptReconcileWorker(
        session_factory_=session_factory,
    ).run_once(
        limit=10,
        lease_seconds=120,
        retry_seconds=300,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    )

    assert calls == [("claim", "attempt_1", 4)]
    assert outcomes["claimed"] == 0
    assert outcomes["conflicted"] == 1


@pytest.mark.anyio
async def test_ai_attempt_reconcile_worker_counts_claim_conflict_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    async def list_due(self, **kwargs):
        return [SimpleNamespace(id="attempt_1", state_version=5)]

    async def claim(self, **kwargs):
        return None

    class LookupMustNotRun:
        async def lookup(self, **kwargs):
            raise AssertionError("lookup_must_not_run_after_claim_conflict")

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)
    outcomes = await AIAttemptReconcileWorker(
        session_factory_=session_factory,
        attempt_lookup=LookupMustNotRun(),
    ).run_once(
        limit=10,
        lease_seconds=120,
        retry_seconds=300,
        max_reconcile_count=3,
        max_unknown_age_seconds=10_800,
    )
    assert outcomes["claimed"] == 0
    assert outcomes["conflicted"] == 1


@pytest.mark.anyio
async def test_overlapping_reconcile_workers_claim_and_lookup_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )
    from apps.backend.workers.imaging_worker.ai_attempt_reconcile import (
        AIAttemptReconcileWorker,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        @asynccontextmanager
        async def begin(self):
            yield

    def session_factory():
        return FakeSession()

    candidate = SimpleNamespace(id="attempt_1", state_version=4)
    plan = {
        "attempt_id": candidate.id,
        "attempt_state_version": 5,
        "first_unknown_at": None,
        "reconcile_count": 1,
        "lookup_authorized": True,
        "limit_reasons": (),
    }
    both_scanned = asyncio.Event()
    claim_lock = asyncio.Lock()
    scan_count = 0
    claimed = False
    lookup_count = 0
    reschedule_count = 0
    replacement_post_count = 0

    async def list_due(self, **kwargs):
        nonlocal scan_count
        scan_count += 1
        if scan_count == 2:
            both_scanned.set()
        await both_scanned.wait()
        return [candidate]

    async def claim(self, **kwargs):
        nonlocal claimed
        async with claim_lock:
            if claimed:
                return None
            claimed = True
            return plan

    async def reschedule(self, **kwargs):
        nonlocal reschedule_count
        reschedule_count += 1
        return True

    class LookupOnly:
        async def lookup(self, **kwargs):
            nonlocal lookup_count
            lookup_count += 1
            return AttemptLookupResult(
                status="unsupported",
                error_code="provider_attempt_lookup_unsupported",
            )

        async def post(self, **kwargs):
            nonlocal replacement_post_count
            replacement_post_count += 1
            raise AssertionError("reconcile_must_never_post_provider")

    monkeypatch.setattr(AIAttemptReconcileService, "list_due", list_due)
    monkeypatch.setattr(AIAttemptReconcileService, "claim", claim)
    monkeypatch.setattr(AIAttemptReconcileService, "reschedule_unknown", reschedule)

    workers = [
        AIAttemptReconcileWorker(
            session_factory_=session_factory,
            attempt_lookup=LookupOnly(),
        )
        for _ in range(2)
    ]
    outcomes = await asyncio.gather(
        *(
            worker.run_once(
                limit=10,
                lease_seconds=120,
                retry_seconds=300,
                max_reconcile_count=3,
                max_unknown_age_seconds=10_800,
            )
            for worker in workers
        )
    )

    assert sum(item["claimed"] for item in outcomes) == 1
    assert sum(item["conflicted"] for item in outcomes) == 1
    assert lookup_count == 1
    assert reschedule_count == 1
    assert replacement_post_count == 0


@pytest.mark.anyio
async def test_ai_attempt_reconcile_rejects_incomplete_success() -> None:
    from datetime import datetime

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileError,
        AIAttemptReconcileService,
    )

    service = object.__new__(AIAttemptReconcileService)
    with pytest.raises(
        AIAttemptReconcileError, match="ai_attempt_lookup_result_invalid"
    ):
        await service.apply_lookup_result(
            attempt_id="attempt_1",
            result=AttemptLookupResult(
                status="succeeded",
                network_result={
                    "execution": object(),
                    "image_receipt": {},
                    "image_manifest_sha256": "a" * 64,
                },
            ),
            now=datetime(2026, 8, 24, 12, 0, 0),
        )


@pytest.mark.anyio
async def test_ai_attempt_reconcile_failed_result_restores_running_stage() -> None:
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )

    now = datetime(2026, 8, 24, 12, 0, 0)
    attempt = SimpleNamespace(id="attempt_1", ai_call_id="call_1")
    call = SimpleNamespace(id="call_1", stage_checkpoint_id="stage_1")
    stage = SimpleNamespace(
        id="stage_1",
        status="running",
        lease_owner_id="worker_1",
        lease_expires_at=now + timedelta(seconds=120),
    )
    finalized: list[tuple[str, Any]] = []

    class FakeAIRequestService:
        async def finalize_attempt_failure(self, **kwargs):
            finalized.append(("attempt", kwargs))
            return {"status": "failed", "result_disposition": "failed"}

    class FakeAttemptDal:
        async def get_by_id(self, attempt_id: str):
            return attempt

    class FakeCallDal:
        async def get_by_id(self, call_id: str):
            return call

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return stage

    class FakeImagingExecutionService:
        async def finalize_ai_stage(self, **kwargs):
            finalized.append(("stage", kwargs))
            return {"status": "failed"}

    service = object.__new__(AIAttemptReconcileService)
    service.ai_request_service = FakeAIRequestService()
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.stage_dal = FakeStageDal()
    service.imaging_execution_service = FakeImagingExecutionService()

    assert (
        await service.apply_lookup_result(
            attempt_id="attempt_1",
            result=AttemptLookupResult(
                status="failed",
                error_code="provider_request_failed",
            ),
            now=now,
        )
        == "stage_restored"
    )
    assert finalized[0][0] == "attempt"
    assert finalized[0][1]["unknown"] is False
    assert finalized[1][0] == "stage"
    assert finalized[1][1]["owner_id"] == "worker_1"


@pytest.mark.anyio
async def test_ai_attempt_reconcile_unresolved_uses_technical_failure_path() -> None:
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
        PROVIDER_RESULT_UNRESOLVED,
    )

    now = datetime(2026, 8, 28, 12, 0, 0)
    attempt = SimpleNamespace(id="attempt_1", ai_call_id="call_1")
    call = SimpleNamespace(id="call_1", stage_checkpoint_id="stage_1")
    stage = SimpleNamespace(
        id="stage_1",
        status="running",
        lease_owner_id="worker_1",
        lease_expires_at=now + timedelta(seconds=120),
    )
    captured: dict[str, Any] = {}

    class FakeAIRequestService:
        async def finalize_attempt_failure(self, **kwargs):
            captured["failure"] = kwargs
            return {
                "attempt_status": "failed",
                "status": "failed",
                "result_disposition": "failed",
                "error_code": PROVIDER_RESULT_UNRESOLVED,
            }

    class FakeAttemptDal:
        async def get_by_id(self, attempt_id: str):
            return attempt

    class FakeCallDal:
        async def get_by_id(self, call_id: str):
            return call

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return stage

    class FakeImagingExecutionService:
        async def finalize_ai_stage(self, **kwargs):
            captured["stage"] = kwargs
            return {"status": "failed"}

    service = object.__new__(AIAttemptReconcileService)
    service.ai_request_service = FakeAIRequestService()
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.stage_dal = FakeStageDal()
    service.imaging_execution_service = FakeImagingExecutionService()

    result = await service.finalize_unresolved(attempt_id=attempt.id, now=now)

    assert captured["failure"] == {
        "attempt_id": attempt.id,
        "error_code": PROVIDER_RESULT_UNRESOLVED,
        "unknown": False,
    }
    assert captured["stage"]["call_result"]["error_code"] == (
        PROVIDER_RESULT_UNRESOLVED
    )
    assert result == {
        "disposition": "terminal_unresolved",
        "stage_outcome": "stage_restored",
    }


@pytest.mark.anyio
async def test_ai_attempt_reconcile_unresolved_preserves_late_terminal_success() -> (
    None
):
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )

    now = datetime(2026, 8, 28, 12, 0, 0)
    attempt = SimpleNamespace(id="attempt_1", ai_call_id="call_1")
    call = SimpleNamespace(id="call_1", stage_checkpoint_id="stage_1")

    class FakeAIRequestService:
        async def finalize_attempt_failure(self, **kwargs):
            return {
                "attempt_status": "succeeded",
                "status": "succeeded",
                "result_disposition": "accepted",
                "error_code": None,
            }

    class FakeAttemptDal:
        async def get_by_id(self, attempt_id: str):
            return attempt

    class FakeCallDal:
        async def get_by_id(self, call_id: str):
            return call

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return None

    service = object.__new__(AIAttemptReconcileService)
    service.ai_request_service = FakeAIRequestService()
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.stage_dal = FakeStageDal()
    service.imaging_execution_service = object()

    assert await service.finalize_unresolved(attempt_id=attempt.id, now=now) == {
        "disposition": "terminal_preserved",
        "stage_outcome": "attempt_finalized_stage_pending",
    }


@pytest.mark.anyio
async def test_ai_attempt_reconcile_repeated_success_does_not_refinalize_stage() -> (
    None
):
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileService,
    )

    now = datetime(2026, 8, 24, 12, 0, 0)
    attempt = SimpleNamespace(id="attempt_1", ai_call_id="call_1")
    call = SimpleNamespace(id="call_1", stage_checkpoint_id="stage_1")
    stage = SimpleNamespace(
        id="stage_1",
        status="running",
        lease_owner_id="worker_1",
        lease_expires_at=now + timedelta(seconds=120),
    )
    attempt_finalize_count = 0
    stage_finalize_count = 0

    class FakeAIRequestService:
        async def finalize_attempt(self, **kwargs):
            nonlocal attempt_finalize_count
            attempt_finalize_count += 1
            return {"status": "succeeded", "result_disposition": "accepted"}

    class FakeAttemptDal:
        async def get_by_id(self, attempt_id: str):
            return attempt

    class FakeCallDal:
        async def get_by_id(self, call_id: str):
            return call

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return stage

    class FakeImagingExecutionService:
        async def finalize_ai_stage(self, **kwargs):
            nonlocal stage_finalize_count
            stage_finalize_count += 1
            stage.status = "completed"
            return {"status": "completed"}

    service = object.__new__(AIAttemptReconcileService)
    service.ai_request_service = FakeAIRequestService()
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.stage_dal = FakeStageDal()
    service.imaging_execution_service = FakeImagingExecutionService()
    result = AttemptLookupResult(
        status="succeeded",
        network_result={
            "execution": object(),
            "image_receipt": {},
            "image_manifest_sha256": "a" * 64,
            "image_count_sent": 1,
        },
    )

    first = await service.apply_lookup_result(
        attempt_id="attempt_1", result=result, now=now
    )
    second = await service.apply_lookup_result(
        attempt_id="attempt_1", result=result, now=now
    )
    assert first == "stage_restored"
    assert second == "attempt_finalized_stage_pending"
    assert attempt_finalize_count == 2
    assert stage_finalize_count == 1


@pytest.mark.anyio
async def test_xray_family_routing_only_returns_primary_final_and_preserves_primary_result() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.family_routing import (
        XRayFamilyRoutingStageHandler,
    )

    primary_result = {
        "medical_status": "review_required",
        "findings": [{"finding_id": "finding_1"}],
    }
    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="family_routing",
            input_json={
                "previous_output_sha256": "a" * 64,
                "previous_output": {
                    "medical_status": "produced",
                    "source_call_id": "call_1",
                    "complete_medical_result": primary_result,
                },
            },
        ),
    )

    plan = await XRayFamilyRoutingStageHandler().execute(context)

    assert plan.ai_request is None
    assert plan.completed_result is not None
    output = plan.completed_result.output
    assert output["route_signal"] == "primary_final"
    assert output["medical_status"] == "produced"
    assert output["complete_medical_result"] is primary_result
    assert not {
        "normal",
        "abnormal",
        "review_required",
        "non_diagnostic",
    }.intersection(output)


@pytest.mark.anyio
async def test_xray_family_routing_v2_routes_one_valid_primary_candidate() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.family_routing import (
        XRayFamilyRoutingV2StageHandler,
    )

    primary_result = _complete_medical_result_v2()
    primary_result["targeted_candidate"] = {
        "family_key": "thoracic",
        "focus_key": "pulmonary_pattern",
        "reason": "肺野征象需要一次专项复核",
        "source_finding_ids": ["finding-1"],
    }
    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="family_routing",
            input_json={
                "previous_output_sha256": "a" * 64,
                "previous_output": {
                    "medical_status": "produced",
                    "source_call_id": "call_1",
                    "complete_medical_result": primary_result,
                },
            },
        ),
    )

    plan = await XRayFamilyRoutingV2StageHandler().execute(context)

    assert plan.ai_request is None
    assert plan.completed_result is not None
    output = plan.completed_result.output
    assert output["route_signal"] == "targeted_review"
    assert output["selected_family_key"] == "thoracic"
    assert output["selected_focus_key"] == "pulmonary_pattern"
    assert output["source_finding_ids"] == ["finding-1"]
    assert output["route_reason_codes"] == ["primary_targeted_candidate"]
    assert output["coverage_proof"] == primary_result["coverage"]
    assert output["complete_medical_result"] is primary_result


@pytest.mark.anyio
async def test_xray_family_routing_v2_rejects_unapproved_focus_without_inference() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.family_routing import (
        XRayFamilyRoutingV2StageHandler,
    )

    primary_result = _complete_medical_result_v2()
    primary_result["targeted_candidate"] = {
        "family_key": "thoracic",
        "focus_key": "invented_focus",
        "reason": "不受控候选",
        "source_finding_ids": ["finding-1"],
    }
    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="family_routing",
            input_json={
                "previous_output_sha256": "a" * 64,
                "previous_output": {
                    "medical_status": "produced",
                    "source_call_id": "call_1",
                    "complete_medical_result": primary_result,
                },
            },
        ),
    )

    plan = await XRayFamilyRoutingV2StageHandler().execute(context)

    assert plan.completed_result is not None
    assert plan.completed_result.output["route_signal"] == "primary_final"
    assert "selected_family_key" not in plan.completed_result.output


@pytest.mark.anyio
async def test_xray_family_routing_v2_accepts_catalog_focus_key() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.family_routing import (
        XRayFamilyRoutingV2StageHandler,
    )

    primary_result = _complete_medical_result_v2()
    primary_result["targeted_candidate"] = {
        "family_key": "thoracic",
        "focus_key": "lung_pattern",
        "reason": "肺野征象需要一次专项复核",
        "source_finding_ids": ["finding-1"],
    }
    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="family_routing",
            input_json={
                "previous_output_sha256": "a" * 64,
                "previous_output": {
                    "medical_status": "produced",
                    "source_call_id": "call_1",
                    "complete_medical_result": primary_result,
                },
            },
        ),
    )

    plan = await XRayFamilyRoutingV2StageHandler().execute(context)

    assert plan.completed_result is not None
    assert plan.completed_result.output["route_signal"] == "targeted_review"
    assert plan.completed_result.output["selected_focus_key"] == "lung_pattern"


@pytest.mark.anyio
async def test_targeted_route_evidence_is_frozen_into_dynamic_stage_input() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.core.pipeline import (
        XRAY_TARGETED_REVIEW_PROFILE_V2,
        build_default_registry,
        compile_profile_contract,
    )
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    contract, pipeline_sha = compile_profile_contract(
        XRAY_TARGETED_REVIEW_PROFILE_V2,
        build_default_registry(),
    )
    captured: dict[str, Any] = {}

    class FakeStageDal:
        async def create_idempotent(self, values: dict[str, Any]):
            captured["stage"] = values
            return SimpleNamespace(**values)

    class FakeOutboxDal:
        async def create_idempotent(self, values: dict[str, Any]):
            captured["outbox"] = values
            return SimpleNamespace(**values)

    class FakeTaskDal:
        async def cas_update(self, **kwargs):
            captured["task"] = kwargs
            return SimpleNamespace(id="task_1")

    service = object.__new__(ImagingExecutionService)
    service.stage_dal = FakeStageDal()
    service.outbox_dal = FakeOutboxDal()
    service.task_dal = FakeTaskDal()
    task = SimpleNamespace(
        id="task_1",
        study_revision_id="revision_1",
        request_snapshot_json={
            "compiled_profile": contract,
            "resolved_manifest_sha256": "a" * 64,
        },
        compiled_pipeline_sha256=pipeline_sha,
        attempt_no=1,
        trace_id="trace_1",
        state_version=3,
    )
    stage = SimpleNamespace(
        id="stage_route",
        stage_key="family_routing",
        stage_no=3,
    )
    output = {
        "route_signal": "targeted_review",
        "medical_status": "produced",
        "source_call_id": "call_1",
        "complete_medical_result": _complete_medical_result_v2(),
        "selected_family_key": "thoracic",
        "selected_focus_key": "pulmonary_pattern",
        "selected_strategy_key": None,
        "source_finding_ids": ["finding-1"],
        "coverage_proof": {"status": "partial"},
        "route_reason_codes": ["primary_targeted_candidate"],
    }

    await service._schedule_next_or_complete(
        task=task,
        stage=stage,
        output=output,
        output_sha="b" * 64,
        now=datetime(2026, 8, 29),
    )

    assert captured["stage"]["stage_key"] == "targeted_review"
    stage_input = captured["stage"]["input_json"]
    assert stage_input["selected_family_key"] == "thoracic"
    assert stage_input["selected_focus_key"] == "pulmonary_pattern"
    assert stage_input["source_finding_ids"] == ["finding-1"]
    assert stage_input["route_reason_codes"] == ["primary_targeted_candidate"]
    assert captured["outbox"]["aggregate_id"] == captured["stage"]["id"]
    assert captured["task"]["values"]["execution_status"] == "queued"


def test_dedicated_targeted_review_rejects_recursive_candidate() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.targeted_review import (
        XRayTargetedReviewV2StageHandler,
    )

    context = StageExecutionContext(
        task=SimpleNamespace(
            request_snapshot_json={
                "stage_ai_config_bindings": {
                    "targeted_review": {
                        "prompt_key": "xray_dog_targeted_review",
                    }
                }
            }
        ),
        stage=SimpleNamespace(
            stage_key="targeted_review",
            input_json={"previous_output_sha256": "a" * 64},
        ),
    )

    result = XRayTargetedReviewV2StageHandler().consume_ai_call(
        context,
        {
            "call_id": "call_targeted_1",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": {
                "result_schema_version": "xray-complete-medical-result.v2",
                "targeted_candidate": {"family_key": "thoracic"},
            },
        },
    )

    assert result.status == "failed"
    assert result.error_code == "targeted_review_recursive_candidate_forbidden"
    assert result.output["medical_status"] == "not_produced"
    assert "complete_medical_result" not in result.output


def test_xray_v1_and_v2_profiles_keep_exact_handler_versions() -> None:
    from apps.backend.core.pipeline import (
        XRAY_PRIMARY_PROFILE_V2,
        XRAY_TARGETED_REVIEW_PROFILE_V2,
        build_default_registry,
        compile_profile_contract,
    )
    from apps.backend.services.runtime.stages.registry import resolve_stage_handler

    registry = build_default_registry()
    primary_v1, primary_v1_sha = compile_profile_contract("xray_primary_v1", registry)
    primary_v2, primary_v2_sha = compile_profile_contract(
        XRAY_PRIMARY_PROFILE_V2, registry
    )
    targeted_v2, _ = compile_profile_contract(XRAY_TARGETED_REVIEW_PROFILE_V2, registry)

    assert [item["handler_version"] for item in primary_v1["stages"]] == [
        "v1",
        "v1",
        "v1",
    ]
    assert [item["handler_version"] for item in primary_v2["stages"]] == [
        "v1",
        "v2",
        "v2",
    ]
    assert primary_v1_sha != primary_v2_sha
    assert targeted_v2["dynamic_stage_definitions"][0]["handler_version"] == "v2"
    assert (
        resolve_stage_handler(
            handler_key="joint_primary_reader", handler_version="v1"
        ).handler_version
        == "v1"
    )
    assert (
        resolve_stage_handler(
            handler_key="joint_primary_reader", handler_version="v2"
        ).handler_version
        == "v2"
    )


def test_xray_v2_reader_preserves_complete_result_without_projection() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.joint_primary_reader import (
        XRayJointPrimaryReaderV2StageHandler,
    )

    complete_result = _complete_medical_result_v2()
    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="joint_primary_reader",
            input_json={"manifest_sha256": "a" * 64},
        ),
    )

    stage_result = XRayJointPrimaryReaderV2StageHandler().consume_ai_call(
        context,
        {
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": complete_result,
            "call_id": "call_1",
        },
    )

    assert stage_result.status == "completed"
    assert stage_result.output["medical_status"] == "produced"
    assert stage_result.output["complete_medical_result"] == complete_result


@pytest.mark.parametrize(
    "medical_status",
    ["normal", "abnormal", "review_required", "non_diagnostic"],
)
def test_medical_status_contract_projects_each_model_status(
    medical_status: str,
) -> None:
    from apps.backend.services.runtime.medical_status_contract import (
        project_persisted_medical_status,
    )

    assert (
        project_persisted_medical_status(
            {
                "medical_status": "produced",
                "complete_medical_result": {"medical_status": medical_status},
            }
        )
        == medical_status
    )


def test_medical_status_contract_accepts_legacy_not_produced_without_result() -> None:
    from apps.backend.services.runtime.medical_status_contract import (
        project_persisted_medical_status,
    )

    assert (
        project_persisted_medical_status({"medical_status": "not_produced"})
        == "not_produced"
    )


@pytest.mark.parametrize(
    ("output", "error_code"),
    [
        ({"medical_status": "produced"}, "finalization_medical_result_invalid"),
        (
            {"medical_status": "produced", "complete_medical_result": None},
            "finalization_medical_result_invalid",
        ),
        (
            {"medical_status": "produced", "complete_medical_result": []},
            "finalization_medical_result_invalid",
        ),
        (
            {"medical_status": "produced", "complete_medical_result": {}},
            "finalization_medical_result_invalid",
        ),
        (
            {
                "medical_status": "produced",
                "complete_medical_result": {"medical_status": "unknown"},
            },
            "finalization_medical_result_invalid",
        ),
        (
            {
                "medical_status": "produced",
                "complete_medical_result": {"medical_status": "not_produced"},
            },
            "finalization_medical_result_invalid",
        ),
        (
            {
                "medical_status": "not_produced",
                "complete_medical_result": {"medical_status": "normal"},
            },
            "finalization_result_availability_conflict",
        ),
        (
            {"medical_status": "not_produced", "complete_medical_result": None},
            "finalization_result_availability_conflict",
        ),
        ({}, "finalization_result_availability_invalid"),
        (
            {
                "medical_status": "unknown",
                "complete_medical_result": {"medical_status": "normal"},
            },
            "finalization_result_availability_invalid",
        ),
    ],
)
def test_medical_status_contract_rejects_incoherent_combinations(
    output: dict[str, Any],
    error_code: str,
) -> None:
    from apps.backend.services.runtime.medical_status_contract import (
        MedicalStatusContractError,
        project_persisted_medical_status,
    )

    with pytest.raises(MedicalStatusContractError, match=f"^{error_code}$"):
        project_persisted_medical_status(output)


def test_runtime_and_evaluation_medical_status_sets_stay_aligned() -> None:
    from typing import get_args

    from apps.backend.schemas.evaluation_execution import MedicalStatus
    from apps.backend.services.runtime.medical_status_contract import (
        PERSISTED_MEDICAL_STATUSES,
    )

    assert frozenset(get_args(MedicalStatus)) == PERSISTED_MEDICAL_STATUSES


def test_xray_v1_reader_keeps_internal_availability_markers() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.joint_primary_reader import (
        XRayJointPrimaryReaderStageHandler,
    )

    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="joint_primary_reader",
            input_json={"manifest_sha256": "a" * 64},
        ),
    )
    handler = XRayJointPrimaryReaderStageHandler()

    produced = handler.consume_ai_call(
        context,
        {
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": {"medical_status": "normal"},
            "call_id": "call_1",
        },
    )
    not_produced = handler.consume_ai_call(
        context,
        {
            "status": "failed",
            "result_disposition": "rejected",
            "error_code": "provider_disabled",
            "call_id": "call_2",
        },
    )

    assert produced.status == "completed"
    assert produced.output["medical_status"] == "produced"
    assert not_produced.status == "completed"
    assert not_produced.output["medical_status"] == "not_produced"


@pytest.mark.anyio
async def test_decision_finalization_projects_model_status_at_persistence_boundary(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.pipeline import StageResult
    from apps.backend.services.runtime.service import imaging_execution_service
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    complete_result = _complete_medical_result_v2()
    output = {
        "medical_status": "produced",
        "source_call_id": "call_1",
        "complete_medical_result": complete_result,
    }
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=None,
        execution_status="running",
        state_version=7,
    )
    stage = SimpleNamespace(
        id="stage_1",
        task_id=task.id,
        stage_key="decision_finalization",
        state_version=5,
        lease_generation=2,
        input_json={"previous_output": {"source_call_id": "call_1"}},
    )
    captured: dict[str, Any] = {}

    class FakeStageDal:
        async def finish_with_lease(self, **kwargs):
            captured["stage_values"] = kwargs["values"]
            return SimpleNamespace(**{**stage.__dict__, **kwargs["values"]})

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            assert task_id == task.id
            return task

        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    class FakeReportService:
        def __init__(self, db):
            assert db == "db"

        async def finalize(self, **kwargs):
            captured["report_values"] = kwargs
            return None

    monkeypatch.setattr(
        imaging_execution_service,
        "ReportService",
        FakeReportService,
    )
    service = object.__new__(ImagingExecutionService)
    service.outbox_dal = SimpleNamespace(db="db")
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service._apply_stage_result(
        task=task,
        stage=stage,
        owner_id="worker_1",
        result=StageResult(status="completed", output=output),
    )

    assert result is output
    assert captured["stage_values"]["status"] == "completed"
    assert captured["stage_values"]["output_json"]["medical_status"] == "produced"
    assert captured["report_values"]["medical_status"] == "review_required"
    assert captured["report_values"]["content"]["medical_status"] == "review_required"
    assert (
        captured["report_values"]["content"]["complete_medical_result"]
        == complete_result
    )
    assert captured["task_values"]["ai_medical_status"] == "review_required"
    assert "produced" not in {
        captured["report_values"]["medical_status"],
        captured["report_values"]["content"]["medical_status"],
        captured["task_values"]["ai_medical_status"],
    }


@pytest.mark.anyio
async def test_incoherent_decision_finalization_fails_without_report(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.pipeline import StageResult
    from apps.backend.services.runtime.service import imaging_execution_service
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    output = {"medical_status": "produced"}
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=None,
        execution_status="running",
        state_version=7,
    )
    stage = SimpleNamespace(
        id="stage_1",
        task_id=task.id,
        stage_key="decision_finalization",
        state_version=5,
        lease_generation=2,
    )
    captured: dict[str, Any] = {}

    class FakeStageDal:
        async def finish_with_lease(self, **kwargs):
            captured["stage_values"] = kwargs["values"]
            return SimpleNamespace(**{**stage.__dict__, **kwargs["values"]})

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            assert task_id == task.id
            return task

        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    class RejectReportService:
        def __init__(self, _db):
            raise AssertionError("incoherent finalization must not create a report")

    monkeypatch.setattr(
        imaging_execution_service,
        "ReportService",
        RejectReportService,
    )
    service = object.__new__(ImagingExecutionService)
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service._apply_stage_result(
        task=task,
        stage=stage,
        owner_id="worker_1",
        result=StageResult(status="completed", output=output),
    )

    assert result is output
    assert captured["stage_values"]["status"] == "failed"
    assert (
        captured["stage_values"]["error_code"] == "finalization_medical_result_invalid"
    )
    assert captured["task_values"]["execution_status"] == "failed"
    assert captured["task_values"]["ai_medical_status"] == "not_produced"
    assert (
        captured["task_values"]["error_code"] == "finalization_medical_result_invalid"
    )


@pytest.mark.anyio
async def test_study_preparation_remains_provider_free_and_non_medical() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.common.study_preparation import (
        StudyPreparationStageHandler,
    )
    from apps.backend.services.runtime.stages.contracts import StageExecutionContext

    context = StageExecutionContext(
        task=SimpleNamespace(id="task_1"),
        stage=SimpleNamespace(
            stage_key="study_preparation",
            input_json={
                "study_revision_id": "revision_1",
                "manifest_sha256": "b" * 64,
            },
        ),
    )

    plan = await StudyPreparationStageHandler().execute(context)

    assert plan.ai_request is None
    assert plan.completed_result is not None
    assert plan.completed_result.output == {
        "study_revision_id": "revision_1",
        "manifest_sha256": "b" * 64,
        "status": "prepared",
        "provider_called": False,
    }
    assert "medical_status" not in plan.completed_result.output
    assert "non_diagnostic" not in plan.completed_result.output


@pytest.mark.anyio
async def test_task_cancel_uses_task_row_lock() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import TaskService

    task = SimpleNamespace(
        id="task_1",
        requester_id="caller_1",
        cancel_requested_at=None,
        execution_status="running",
        state_version=3,
    )
    calls: list[str] = []

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            calls.append("lock")
            assert task_id == task.id
            return task

        async def cas_update(self, **kwargs):
            calls.append("cas")
            assert kwargs["expected_version"] == 3
            assert isinstance(kwargs["values"]["cancel_requested_at"], datetime)
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    service = object.__new__(TaskService)
    service.task_dal = FakeTaskDal()
    service._response = lambda value: value

    result = await service.cancel_task(
        task_id=task.id,
        expected_version=3,
        reason="stop",
        caller=SimpleNamespace(subject_id="caller_1"),
    )

    assert result.cancel_reason == "stop"
    assert calls == ["lock", "cas"]


@pytest.mark.anyio
async def test_stage_claim_converges_queued_cancel_before_provider() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.schemas.outbox import ExecuteStageMessage
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    message = {
        "task_id": "task_1",
        "stage_checkpoint_id": "stage_1",
        "expected_state_version": 3,
        "trace_id": "trace_1",
    }
    event = SimpleNamespace(
        id="event_1",
        message_version="stage-execution.v1",
        trace_id="trace_1",
        message_json=message,
    )
    stage = SimpleNamespace(
        id="stage_1",
        task_id="task_1",
        status="queued",
        state_version=3,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=datetime(2026, 8, 27, 6, 0, 0),
        execution_status="queued",
        ai_medical_status="not_produced",
        state_version=5,
    )
    captured: dict[str, Any] = {"stage_claim_count": 0}

    class FakeOutboxDal:
        async def get_by_id(self, event_id: str):
            return event

        def validate_stage_event(self, current_event):
            return ExecuteStageMessage.model_validate(current_event.message_json)

    class FakeStageDal:
        async def get_by_id(self, checkpoint_id: str):
            return stage

        async def cas_update(self, **kwargs):
            captured["stage_values"] = kwargs["values"]
            return SimpleNamespace(
                **{
                    **stage.__dict__,
                    **kwargs["values"],
                    "state_version": stage.state_version + 1,
                }
            )

        async def claim(self, **kwargs):
            captured["stage_claim_count"] += 1
            raise AssertionError("cancelled_stage_must_not_be_claimed")

    class FakeTaskDal:
        async def get_by_id(self, task_id: str):
            return task

        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(
                **{
                    **task.__dict__,
                    **kwargs["values"],
                    "state_version": task.state_version + 1,
                }
            )

    service = object.__new__(ImagingExecutionService)
    service.outbox_dal = FakeOutboxDal()
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service.claim(
        event_id=event.id,
        message=message,
        message_version=event.message_version,
        trace_id=event.trace_id,
        owner_id="worker_1",
        lease_seconds=120,
    )

    assert result is None
    assert captured["stage_values"]["status"] == "cancelled"
    assert captured["stage_values"]["error_code"] == "task_cancelled"
    assert captured["stage_values"]["finished_at"] is not None
    assert captured["task_values"]["execution_status"] == "cancelled"
    assert captured["task_values"]["ai_medical_status"] == "not_produced"
    assert captured["task_values"]["finished_at"] is not None
    assert captured["stage_claim_count"] == 0


@pytest.mark.anyio
async def test_stage_claim_is_idempotent_for_cancelled_duplicate_delivery() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.schemas.outbox import ExecuteStageMessage
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    message = {
        "task_id": "task_1",
        "stage_checkpoint_id": "stage_1",
        "expected_state_version": 3,
        "trace_id": "trace_1",
    }
    event = SimpleNamespace(
        id="event_1",
        message_version="stage-execution.v1",
        trace_id="trace_1",
        message_json=message,
    )
    stage = SimpleNamespace(
        id="stage_1",
        task_id="task_1",
        status="cancelled",
        state_version=4,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=datetime(2026, 8, 27, 6, 0, 0),
        execution_status="cancelled",
        state_version=6,
    )

    class FakeOutboxDal:
        async def get_by_id(self, event_id: str):
            return event

        def validate_stage_event(self, current_event):
            return ExecuteStageMessage.model_validate(current_event.message_json)

    class FakeStageDal:
        async def get_by_id(self, checkpoint_id: str):
            return stage

        async def cas_update(self, **kwargs):
            raise AssertionError("duplicate_cancel_must_not_update_stage")

        async def claim(self, **kwargs):
            raise AssertionError("duplicate_cancel_must_not_claim_stage")

    class FakeTaskDal:
        async def get_by_id(self, task_id: str):
            return task

        async def cas_update(self, **kwargs):
            raise AssertionError("duplicate_cancel_must_not_update_task")

    service = object.__new__(ImagingExecutionService)
    service.outbox_dal = FakeOutboxDal()
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service.claim(
        event_id=event.id,
        message=message,
        message_version=event.message_version,
        trace_id=event.trace_id,
        owner_id="worker_1",
        lease_seconds=120,
    )

    assert result is None


@pytest.mark.anyio
async def test_ai_request_rejects_cancelled_task_before_call_or_retry_creation() -> (
    None
):
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestService,
        AIRequestStateConflict,
    )

    cancelled_task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=datetime(2026, 8, 25, 1, 0, 0),
        execution_status="running",
    )

    class FakeCallDal:
        db = SimpleNamespace()

        async def get_by_logical_key_for_update(self, logical_call_key: str):
            return None

        async def get_by_id_for_update(self, call_id: str):
            return SimpleNamespace(
                id=call_id,
                task_id=cancelled_task.id,
                winner_attempt_id=None,
                status="running",
            )

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return cancelled_task

    service = object.__new__(AIRequestService)
    service.call_dal = FakeCallDal()
    service.task_dal = FakeTaskDal()

    with pytest.raises(AIRequestStateConflict, match="task_cancelled"):
        await service._reserve_v2_budget_and_create_call(
            task_id=cancelled_task.id,
            logical_call_key="logical_1",
            budget_policy_sha256="a" * 64,
            max_total_calls=1,
            max_total_attempts=1,
            deadline_at=datetime(2026, 8, 25, 2, 0, 0),
            reservation={},
            call_values={},
        )

    with pytest.raises(AIRequestStateConflict, match="task_cancelled"):
        await service.prepare_retry_attempt(
            call_id="call_1",
            trace_id="trace_1",
            request_id="request_1",
        )


@pytest.mark.anyio
@pytest.mark.parametrize("usage_json", (None, {"total_tokens": 11}))
async def test_finalize_definite_failure_projects_receipt_to_attempt_and_call(
    usage_json: dict[str, Any] | None,
) -> None:
    from types import SimpleNamespace

    attempt = SimpleNamespace(
        id="attempt_1",
        ai_call_id="call_1",
        status="prepared",
        state_version=4,
        error_code=None,
    )
    call = SimpleNamespace(
        id="call_1",
        task_id="task_1",
        status="running",
        result_disposition="pending",
        winner_attempt_id=None,
        state_version=6,
        error_code=None,
        parsed_result_json=None,
        rendered_prompt_sha256="a" * 64,
        schema_sha256="b" * 64,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=None,
        execution_status="running",
    )
    receipt = {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": 1,
        "images": [{"image_id": "image_1", "sha256": "c" * 64}],
    }
    captured: dict[str, Any] = {}

    class FakeAttemptDal:
        async def get_by_id_for_update(self, attempt_id: str):
            return attempt

        async def cas_update(self, **kwargs):
            captured["attempt"] = kwargs
            return SimpleNamespace(
                **{
                    **attempt.__dict__,
                    **kwargs["values"],
                    "state_version": attempt.state_version + 1,
                }
            )

    class FakeCallDal:
        async def get_by_id_for_update(self, call_id: str):
            return call

        async def cas_update(self, **kwargs):
            captured["call"] = kwargs
            return SimpleNamespace(
                **{
                    **call.__dict__,
                    **kwargs["values"],
                    "state_version": call.state_version + 1,
                }
            )

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

    service = object.__new__(AIRequestService)
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.task_dal = FakeTaskDal()

    result = await service.finalize_attempt_failure(
        attempt_id=attempt.id,
        error_code="provider_response_json_invalid",
        unknown=False,
        image_receipt=receipt,
        image_manifest_sha256="d" * 64,
        image_count_sent=1,
        provider_request_id="provider-request-1",
        actual_model="provider-model",
        usage_json=usage_json,
        response_sha256="e" * 64,
    )

    expected_delivery = {
        "sent_image_manifest_sha256": "d" * 64,
        "image_count_sent": 1,
        "image_receipt_json": receipt,
    }
    expected_provider_attempt = {
        "provider_request_id": "provider-request-1",
        "actual_model": "provider-model",
        "usage_json": usage_json,
        "response_sha256": "e" * 64,
    }
    expected_provider_call = {
        "provider_request_id": "provider-request-1",
        "actual_model": "provider-model",
        "response_sha256": "e" * 64,
    }
    assert captured["attempt"]["values"] == {
        "error_code": "provider_response_json_invalid",
        "finished_at": captured["attempt"]["values"]["finished_at"],
        **expected_delivery,
        **expected_provider_attempt,
        "status": "failed",
        "next_reconcile_at": None,
    }
    assert captured["call"]["expected_version"] == call.state_version
    assert captured["call"]["values"] == {
        **expected_delivery,
        **expected_provider_call,
        "status": "failed",
        "result_disposition": "failed",
        "error_code": "provider_response_json_invalid",
        "finished_at": captured["call"]["values"]["finished_at"],
    }
    assert result["attempt_status"] == "failed"
    assert result["status"] == "failed"
    assert result["result_disposition"] == "failed"


@pytest.mark.anyio
async def test_finalize_unknown_sets_first_timestamp_once_and_starts_at_zero() -> None:
    from types import SimpleNamespace

    current_attempt = SimpleNamespace(
        id="attempt_1",
        ai_call_id="call_1",
        status="prepared",
        state_version=4,
        error_code=None,
        first_unknown_at=None,
        reconcile_count=0,
    )
    call = SimpleNamespace(
        id="call_1",
        task_id="task_1",
        status="running",
        result_disposition="pending",
        winner_attempt_id=None,
        state_version=6,
        error_code=None,
        parsed_result_json=None,
        rendered_prompt_sha256="a" * 64,
        schema_sha256="b" * 64,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=None,
        execution_status="running",
    )
    attempt_updates: list[dict[str, Any]] = []

    class FakeAttemptDal:
        async def get_by_id_for_update(self, attempt_id: str):
            return current_attempt

        async def cas_update(self, **kwargs):
            nonlocal current_attempt
            attempt_updates.append(kwargs["values"])
            current_attempt = SimpleNamespace(
                **{
                    **current_attempt.__dict__,
                    **kwargs["values"],
                    "state_version": current_attempt.state_version + 1,
                }
            )
            return current_attempt

    class FakeCallDal:
        async def get_by_id_for_update(self, call_id: str):
            return call

        async def cas_update(self, **kwargs):
            raise AssertionError("unknown_must_not_finalize_logical_call")

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

    service = object.__new__(AIRequestService)
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.task_dal = FakeTaskDal()

    first = await service.finalize_attempt_failure(
        attempt_id=current_attempt.id,
        error_code="provider_delivery_unknown",
        unknown=True,
        reconcile_after_seconds=300,
    )
    second = await service.finalize_attempt_failure(
        attempt_id=current_attempt.id,
        error_code="provider_delivery_unknown",
        unknown=True,
        reconcile_after_seconds=30,
    )

    assert len(attempt_updates) == 1
    values = attempt_updates[0]
    assert values["status"] == "unknown"
    assert values["first_unknown_at"] == values["finished_at"]
    assert (
        values["next_reconcile_at"] - values["first_unknown_at"]
    ).total_seconds() == 300
    assert current_attempt.reconcile_count == 0
    assert second["attempt_status"] == first["attempt_status"] == "unknown"
    assert current_attempt.first_unknown_at == values["first_unknown_at"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("unknown", "image_receipt", "image_manifest_sha256", "image_count_sent"),
    [
        (False, {"image_count": 1}, None, 1),
        (False, None, "d" * 64, 1),
        (False, {"image_count": 1}, "d" * 64, None),
        (True, {"image_count": 1}, "d" * 64, 1),
    ],
)
async def test_finalize_failure_rejects_partial_or_unknown_delivery_audit(
    unknown: bool,
    image_receipt: dict[str, Any] | None,
    image_manifest_sha256: str | None,
    image_count_sent: int | None,
) -> None:
    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestStateConflict,
    )

    service = object.__new__(AIRequestService)
    with pytest.raises(
        AIRequestStateConflict,
        match="ai_call_attempt_delivery_audit_invalid",
    ):
        await service.finalize_attempt_failure(
            attempt_id="attempt_1",
            error_code="provider_response_json_invalid",
            unknown=unknown,
            image_receipt=image_receipt,
            image_manifest_sha256=image_manifest_sha256,
            image_count_sent=image_count_sent,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "unknown",
        "provider_request_id",
        "actual_model",
        "usage_json",
        "provider_response_sha256",
    ),
    (
        (False, "provider-request-1", None, None, "e" * 64),
        (False, "", "provider-model", None, "e" * 64),
        (False, "p" * 161, "provider-model", None, "e" * 64),
        (False, "provider-request-1", "", None, "e" * 64),
        (False, "provider-request-1", "m" * 129, None, "e" * 64),
        (False, "provider-request-1", "provider-model", None, "E" * 64),
        (False, "provider-request-1", "provider-model", None, "z" * 64),
        (False, None, None, {"total_tokens": 1}, None),
        (False, "provider-request-1", "provider-model", [], "e" * 64),
        (True, "provider-request-1", "provider-model", None, "e" * 64),
    ),
)
async def test_finalize_failure_rejects_invalid_provider_response_audit(
    unknown: bool,
    provider_request_id: str | None,
    actual_model: str | None,
    usage_json: Any,
    provider_response_sha256: str | None,
) -> None:
    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestStateConflict,
    )

    service = object.__new__(AIRequestService)
    with pytest.raises(
        AIRequestStateConflict,
        match="ai_call_attempt_provider_response_audit_invalid",
    ):
        await service.finalize_attempt_failure(
            attempt_id="attempt_1",
            error_code="provider_response_json_invalid",
            unknown=unknown,
            provider_request_id=provider_request_id,
            actual_model=actual_model,
            usage_json=usage_json,
            response_sha256=provider_response_sha256,
        )


@pytest.mark.anyio
async def test_late_attempt_success_is_audited_but_cannot_win_cancelled_task() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestService,
    )

    attempt = SimpleNamespace(
        id="attempt_1",
        ai_call_id="call_1",
        status="prepared",
        state_version=4,
        error_code=None,
    )
    call = SimpleNamespace(
        id="call_1",
        task_id="task_1",
        status="running",
        result_disposition="pending",
        winner_attempt_id=None,
        state_version=6,
        error_code=None,
        parsed_result_json=None,
        rendered_prompt_sha256="a" * 64,
        schema_sha256="b" * 64,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=datetime(2026, 8, 25, 1, 0, 0),
        execution_status="running",
    )
    captured: dict[str, Any] = {}

    class FakeAttemptDal:
        async def get_by_id_for_update(self, attempt_id: str):
            return attempt

        async def cas_update(self, **kwargs):
            captured["attempt_values"] = kwargs["values"]
            return SimpleNamespace(
                **{
                    **attempt.__dict__,
                    **kwargs["values"],
                    "state_version": attempt.state_version + 1,
                }
            )

    class FakeCallDal:
        async def get_by_id_for_update(self, call_id: str):
            return call

        async def cas_update(self, **kwargs):
            captured["call_values"] = kwargs["values"]
            return SimpleNamespace(
                **{
                    **call.__dict__,
                    **kwargs["values"],
                    "state_version": call.state_version + 1,
                }
            )

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

    service = object.__new__(AIRequestService)
    service.attempt_dal = FakeAttemptDal()
    service.call_dal = FakeCallDal()
    service.task_dal = FakeTaskDal()
    execution = SimpleNamespace(
        actual_model="provider-model",
        usage_json={"total_tokens": 17},
        response_sha256="c" * 64,
        parsed_result_json={"medical_status": "normal"},
        provider_request_id="provider-request-1",
    )

    result = await service.finalize_attempt(
        attempt_id=attempt.id,
        execution=execution,
        image_receipt={"contract_version": "ai-image-receipt.v1"},
        image_manifest_sha256="d" * 64,
        image_count_sent=2,
    )

    assert captured["attempt_values"]["status"] == "succeeded"
    assert captured["attempt_values"]["error_code"] is None
    assert captured["attempt_values"]["next_reconcile_at"] is None
    assert captured["attempt_values"]["usage_json"] == {"total_tokens": 17}
    assert captured["attempt_values"]["actual_model"] == "provider-model"
    assert captured["call_values"]["status"] == "cancelled"
    assert captured["call_values"]["result_disposition"] == "cancelled"
    assert captured["call_values"]["error_code"] == "task_cancelled"
    assert captured["call_values"]["finished_at"] is not None
    assert result["status"] == "cancelled"
    assert result["winner"] is False


@pytest.mark.anyio
async def test_ai_stage_finalization_converges_cancel_before_consuming_result() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    stage = SimpleNamespace(
        id="stage_1",
        task_id="task_1",
        status="running",
        lease_owner_id="worker_1",
        lease_generation=2,
        state_version=5,
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=datetime(2026, 8, 25, 1, 0, 0),
        execution_status="running",
        state_version=7,
    )
    captured: dict[str, Any] = {}

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return stage

        async def finish_with_lease(self, **kwargs):
            captured["stage_values"] = kwargs["values"]
            return SimpleNamespace(**{**stage.__dict__, **kwargs["values"]})

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    service = object.__new__(ImagingExecutionService)
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service.finalize_ai_stage(
        stage_checkpoint_id=stage.id,
        owner_id="worker_1",
        call_result={"status": "succeeded", "result_disposition": "accepted"},
    )

    assert result == {"status": "cancelled", "provider_called": True}
    assert captured["stage_values"]["status"] == "cancelled"
    assert captured["task_values"]["execution_status"] == "cancelled"


@pytest.mark.anyio
async def test_report_finalization_is_idempotent_for_same_stage_and_content() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.report_service import ReportService

    content = {"medical_status": "normal", "findings": []}
    content_sha = (
        __import__("hashlib")
        .sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode())
        .hexdigest()
    )
    task = SimpleNamespace(
        id="task_1",
        cancel_requested_at=None,
        execution_status="completed",
        report_required=True,
    )
    stage = SimpleNamespace(
        id="stage_1",
        task_id=task.id,
        stage_key="decision_finalization",
    )
    report = SimpleNamespace(
        id="report_1",
        task_id=task.id,
        revision_no=1,
        source_stage_checkpoint_id=stage.id,
        source_call_id="call_1",
        medical_status="normal",
        content_sha256=content_sha,
    )

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

    class FakeStageDal:
        async def get_by_id(self, stage_id: str):
            return stage

    class FakeReportDal:
        async def list_for_task(self, task_id: str):
            return [report]

        async def create_idempotent(self, values: dict[str, Any]):
            raise AssertionError("idempotent finalization must not create a revision")

    service = object.__new__(ReportService)
    service.task_dal = FakeTaskDal()
    service.stage_dal = FakeStageDal()
    service.report_dal = FakeReportDal()
    service._response = lambda value: value

    result = await service.finalize(
        task_id=task.id,
        finalization_stage_id=stage.id,
        source_call_id="call_1",
        medical_status="normal",
        content=content,
    )

    assert result is report


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("medical_status", "content", "error_code"),
    [
        (
            "produced",
            {"medical_status": "produced"},
            "report_medical_status_invalid",
        ),
        (
            "normal",
            {},
            "report_content_medical_status_missing",
        ),
        (
            "normal",
            {"medical_status": "abnormal"},
            "report_content_medical_status_conflict",
        ),
    ],
)
async def test_report_finalization_rejects_status_drift_before_dal_access(
    medical_status: str,
    content: dict[str, Any],
    error_code: str,
) -> None:
    from apps.backend.services.runtime.service.report_service import (
        ReportService,
        ReportStateConflictError,
    )

    class RejectDalAccess:
        def __getattr__(self, _name: str):
            raise AssertionError("invalid report status must fail before DAL access")

    service = object.__new__(ReportService)
    service.task_dal = RejectDalAccess()
    service.stage_dal = RejectDalAccess()
    service.report_dal = RejectDalAccess()

    with pytest.raises(ReportStateConflictError, match=f"^{error_code}$"):
        await service.finalize(
            task_id="task_1",
            finalization_stage_id="stage_1",
            source_call_id="call_1",
            medical_status=medical_status,
            content=content,
        )


@pytest.mark.anyio
async def test_report_publish_is_idempotent_after_cas_race() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.report_service import ReportService

    report = SimpleNamespace(
        id="report_1",
        task_id="task_1",
        status="final",
    )
    published = SimpleNamespace(
        id=report.id,
        task_id=report.task_id,
        status="published",
    )
    task = SimpleNamespace(
        id=report.task_id,
        current_report_id=report.id,
        cancel_requested_at=None,
        execution_status="completed",
    )
    reads = 0

    class FakeReportDal:
        async def get_by_id(self, report_id: str):
            nonlocal reads
            reads += 1
            return report if reads == 1 else published

        async def cas_update(self, **kwargs):
            return None

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id: str):
            return task

    service = object.__new__(ReportService)
    service.report_dal = FakeReportDal()
    service.task_dal = FakeTaskDal()
    service._response = lambda value: value

    result = await service.publish(report_id=report.id, expected_version=2)

    assert result is published
    assert reads == 2


@pytest.mark.anyio
async def test_runtime_readiness_excludes_evaluation_plane(monkeypatch) -> None:
    from apps.backend.core import readiness as readiness_module

    checked_engines: list[object] = []
    checked_domains: list[str] = []

    class ReadyRedis:
        last_error = None

        async def check_readiness(self) -> bool:
            return True

    async def database_ready(engine: object, *, error_code: str):
        checked_engines.append(engine)
        return True, None

    async def broker_ready(topology):
        checked_domains.append(topology.domain)
        return (
            True,
            None,
            "ready",
            {
                "consumer_count": 1,
                "queue_message_count": 0,
                "dead_letter_message_count": 0,
                "oldest_message_age_seconds": None,
                "oldest_message_age_supported": False,
            },
        )

    monkeypatch.setattr(readiness_module.settings, "BROKER_ENABLED", True)
    monkeypatch.setattr(readiness_module, "_database_ready", database_ready)
    monkeypatch.setattr(readiness_module, "_broker_domain_ready", broker_ready)

    result = await readiness_module.build_runtime_readiness(ReadyRedis())

    assert result["ready"] is True
    assert result["readiness_scope"] == "online_runtime"
    assert checked_engines == [readiness_module.async_engine]
    assert checked_domains == ["imaging"]
    assert "evaluation_database" not in result["components"]
    assert "evaluation_broker" not in result["components"]


@pytest.mark.anyio
async def test_admin_aggregate_readiness_keeps_evaluation_plane(monkeypatch) -> None:
    from apps.backend.core import readiness as readiness_module

    checked_engines: list[object] = []
    checked_domains: list[str] = []

    class ReadyRedis:
        last_error = None

        async def check_readiness(self) -> bool:
            return True

    async def database_ready(engine: object, *, error_code: str):
        checked_engines.append(engine)
        if engine is readiness_module.evaluation_async_engine:
            return False, error_code
        return True, None

    async def broker_ready(topology):
        checked_domains.append(topology.domain)
        return (
            True,
            None,
            "ready",
            {
                "consumer_count": 1,
                "queue_message_count": 0,
                "dead_letter_message_count": 0,
                "oldest_message_age_seconds": None,
                "oldest_message_age_supported": False,
            },
        )

    monkeypatch.setattr(readiness_module.settings, "BROKER_ENABLED", True)
    monkeypatch.setattr(readiness_module, "_database_ready", database_ready)
    monkeypatch.setattr(readiness_module, "_broker_domain_ready", broker_ready)

    result = await readiness_module.build_readiness(ReadyRedis())

    assert result["ready"] is False
    assert checked_engines == [
        readiness_module.async_engine,
        readiness_module.evaluation_async_engine,
    ]
    assert checked_domains == ["imaging", "evaluation"]
    assert result["components"]["evaluation_database"]["ready"] is False
    assert result["components"]["evaluation_broker"]["ready"] is True


@pytest.mark.parametrize("image_count", (0, 1, 6))
def test_xray_study_schema_rejects_out_of_range_counts(image_count: int) -> None:
    from apps.backend.schemas.study import StudyCreate

    with pytest.raises(ValidationError, match="xray_study_image_count_out_of_range"):
        StudyCreate(
            session_id="session_1",
            modality_type="xray",
            metadata_schema_version="imaging.metadata.v1",
            expected_image_count=image_count,
        )


@pytest.mark.parametrize("image_count", (2, 3, 4, 5))
def test_xray_study_schema_accepts_qualified_counts(image_count: int) -> None:
    from apps.backend.schemas.study import StudyCreate

    payload = StudyCreate(
        session_id="session_1",
        modality_type="xray",
        metadata_schema_version="imaging.metadata.v1",
        expected_image_count=image_count,
    )

    assert payload.expected_image_count == image_count


def test_non_xray_study_schema_preserves_existing_count_contract() -> None:
    from apps.backend.schemas.study import StudyCreate

    payload = StudyCreate(
        session_id="session_1",
        modality_type="ct",
        metadata_schema_version="imaging.metadata.v1",
        expected_image_count=0,
    )

    assert payload.expected_image_count == 0


def test_xray_diagnostic_manifest_excludes_derived_images() -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import (
        build_xray_diagnostic_series_manifest,
    )

    def image(image_id: str, *, role: str, kind: str, sequence_no: int):
        return SimpleNamespace(
            id=image_id,
            series_id="series_1",
            logical_image_key=f"logical-{image_id}",
            image_version_no=1,
            sequence_no=sequence_no,
            image_role=role,
            image_kind=kind,
            file_format="jpeg",
            projection="UNKNOWN",
            technical_metadata_json={
                "projection_provenance": {
                    "source": "caller_declared",
                    "schema_version": "xray-projection.v1",
                }
            },
            storage_profile="primary",
            object_key=f"images/{image_id}.jpg",
            object_version_id=None,
            sha256=str(sequence_no) * 64,
            size_bytes=10,
            content_type="image/jpeg",
            status="ready",
        )

    original = image("original", role="original", kind="instance", sequence_no=1)
    derived = image("derived", role="segmentation", kind="instance", sequence_no=2)

    manifest = build_xray_diagnostic_series_manifest([original, derived])

    assert len(manifest.items) == 1
    assert manifest.items[0]["image_id"] == "original"


@pytest.mark.anyio
async def test_xray_image_admission_rejects_sixth_original_slot() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.image_service import (
        ImageService,
        ImageStateConflictError,
    )

    class ImageDal:
        async def list_occupying_diagnostic_slots_for_study(self, study_id: str):
            assert study_id == "study_1"
            return [
                SimpleNamespace(series_id="series_1", logical_image_key=f"image-{i}")
                for i in range(5)
            ]

    service = object.__new__(ImageService)
    service.image_dal = ImageDal()
    study = SimpleNamespace(id="study_1", modality_type="xray")
    payload = SimpleNamespace(image_role="original", image_kind="instance")

    with pytest.raises(
        ImageStateConflictError,
        match="xray_study_image_capacity_exceeded",
    ):
        await service._admit_xray_diagnostic_slot(study=study, payload=payload)


@pytest.mark.anyio
async def test_xray_image_admission_does_not_count_derived_image() -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.image_service import ImageService

    class ImageDal:
        async def list_occupying_diagnostic_slots_for_study(self, study_id: str):
            raise AssertionError("derived image must not query diagnostic capacity")

    service = object.__new__(ImageService)
    service.image_dal = ImageDal()
    await service._admit_xray_diagnostic_slot(
        study=SimpleNamespace(id="study_1", modality_type="xray"),
        payload=SimpleNamespace(image_role="segmentation", image_kind="instance"),
    )


@pytest.mark.parametrize("image_count", (0, 1, 6))
def test_ai_request_rejects_out_of_range_xray_image_count(image_count: int) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestStateConflict,
    )

    config = SimpleNamespace(
        modality_type="xray",
        task_type="diagnose",
        profile_key="xray_primary_v2",
    )
    task = SimpleNamespace(
        request_snapshot_json={
            "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
        }
    )

    with pytest.raises(
        AIRequestStateConflict,
        match="ai_call_xray_image_count_out_of_range",
    ):
        AIRequestService._require_xray_image_count(
            config=config,
            task=task,
            image_count=image_count,
        )


@pytest.mark.parametrize("image_count", (2, 3, 4, 5))
def test_ai_request_accepts_qualified_xray_image_count(image_count: int) -> None:
    from types import SimpleNamespace

    config = SimpleNamespace(
        modality_type="xray",
        task_type="diagnose",
        profile_key="xray_primary_v2",
    )
    task = SimpleNamespace(
        request_snapshot_json={
            "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
        }
    )

    AIRequestService._require_xray_image_count(
        config=config,
        task=task,
        image_count=image_count,
    )


@pytest.mark.anyio
async def test_network_boundary_rejects_xray_count_before_signing() -> None:
    class Signer:
        async def sign(self, *, attempt_plan, ttl_seconds):
            raise AssertionError("invalid X-Ray count must fail before image signing")

    with pytest.raises(
        GatewayContractError,
        match="ai_call_xray_image_count_out_of_range",
    ):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan={
                "xray_image_contract_required": True,
                "image_count_requested": 1,
                "image_url_ttl_seconds": 60,
            },
            image_signer=Signer(),
        )


@pytest.mark.parametrize(
    ("existing_counts", "new_count", "study_count"),
    (([1], 1, 2), ([1], 2, 3), ([2], 3, 5)),
)
@pytest.mark.anyio
async def test_xray_series_budget_accepts_qualified_multi_series_totals(
    existing_counts: list[int], new_count: int, study_count: int
) -> None:
    from types import SimpleNamespace

    from apps.backend.schemas.study import SeriesCreate
    from apps.backend.services.runtime.service.study_service import StudyService

    created = SimpleNamespace(id="series_new", expected_image_count=new_count)

    class SeriesDal:
        async def get_by_key_for_update(self, **kwargs):
            return None

        async def list_for_study(self, study_id: str):
            assert study_id == "study_1"
            return [
                SimpleNamespace(expected_image_count=value) for value in existing_counts
            ]

        async def create_idempotent(self, values):
            assert values["expected_image_count"] == new_count
            return created

    async def owned_study(**kwargs):
        return SimpleNamespace(
            id="study_1",
            session_id="session_1",
            modality_type="xray",
            expected_image_count=study_count,
            status="ingesting",
        )

    async def owned_session(**kwargs):
        return SimpleNamespace(status="processing")

    async def advance_revision(**kwargs):
        return kwargs["study"]

    service = object.__new__(StudyService)
    service.series_dal = SeriesDal()
    service._owned_study_for_update = owned_study
    service._owned_session = owned_session
    service._advance_study_revision = advance_revision
    service._series_response = lambda row: row

    result = await service.create_series(
        payload=SeriesCreate(
            study_id="study_1",
            series_key="series-new",
            metadata_schema_version="imaging.metadata.v1",
            expected_image_count=new_count,
        ),
        requester_id="requester_1",
    )

    assert result is created


@pytest.mark.parametrize(
    ("existing_counts", "new_count", "study_count"),
    (([3], 3, 5), ([5], 1, 5), ([], 0, 2), ([], 6, 5)),
)
@pytest.mark.anyio
async def test_xray_series_budget_rejects_invalid_or_excess_total(
    existing_counts: list[int], new_count: int, study_count: int
) -> None:
    from types import SimpleNamespace

    from apps.backend.schemas.study import SeriesCreate
    from apps.backend.services.runtime.service.study_service import (
        StudyService,
        StudyStateConflictError,
    )

    class SeriesDal:
        async def get_by_key_for_update(self, **kwargs):
            return None

        async def list_for_study(self, study_id: str):
            return [
                SimpleNamespace(expected_image_count=value) for value in existing_counts
            ]

        async def create_idempotent(self, values):
            raise AssertionError("invalid Series budget must fail before create")

    async def owned_study(**kwargs):
        return SimpleNamespace(
            id="study_1",
            session_id="session_1",
            modality_type="xray",
            expected_image_count=study_count,
            status="ingesting",
        )

    async def owned_session(**kwargs):
        return SimpleNamespace(status="processing")

    service = object.__new__(StudyService)
    service.series_dal = SeriesDal()
    service._owned_study_for_update = owned_study
    service._owned_session = owned_session

    expected_error = (
        "xray_series_image_count_out_of_range"
        if new_count in {0, 6}
        else "xray_study_series_budget_exceeded"
    )
    with pytest.raises(StudyStateConflictError, match=expected_error):
        await service.create_series(
            payload=SeriesCreate(
                study_id="study_1",
                series_key="series-new",
                metadata_schema_version="imaging.metadata.v1",
                expected_image_count=new_count,
            ),
            requester_id="requester_1",
        )


@pytest.mark.anyio
async def test_xray_series_idempotent_replay_precedes_budget_counting() -> None:
    from types import SimpleNamespace

    from apps.backend.schemas.study import SeriesCreate
    from apps.backend.services.runtime.service.study_service import StudyService

    existing = SimpleNamespace(id="series_existing")

    class SeriesDal:
        async def get_by_key_for_update(self, **kwargs):
            return existing

        async def list_for_study(self, study_id: str):
            raise AssertionError("idempotent replay must not recount Series budget")

    async def owned_study(**kwargs):
        return SimpleNamespace(
            id="study_1",
            session_id="session_1",
            modality_type="xray",
            expected_image_count=2,
            status="ingesting",
        )

    async def owned_session(**kwargs):
        return SimpleNamespace(status="processing")

    service = object.__new__(StudyService)
    service.series_dal = SeriesDal()
    service._owned_study_for_update = owned_study
    service._owned_session = owned_session
    service._assert_series_match = lambda row, values: None
    service._series_response = lambda row: row

    result = await service.create_series(
        payload=SeriesCreate(
            study_id="study_1",
            series_key="series-existing",
            metadata_schema_version="imaging.metadata.v1",
            expected_image_count=2,
        ),
        requester_id="requester_1",
    )

    assert result is existing


def _image_prepare_payload(*, multipart: bool):
    from apps.backend.schemas.image import (
        ImagePrepareMultipartRequest,
        ImagePrepareUploadRequest,
    )

    values = {
        "series_id": "series_1",
        "logical_image_key": "logical_6",
        "sequence_no": 6,
        "image_role": "original",
        "image_kind": "instance",
        "metadata_schema_version": "imaging.metadata.v1",
        "file_format": "jpeg",
        "expected_sha256": "a" * 64,
        "expected_size_bytes": 10,
        "declared_content_type": "image/jpeg",
        "projection": "UNKNOWN",
    }
    if multipart:
        return ImagePrepareMultipartRequest(**values, expected_part_count=1)
    return ImagePrepareUploadRequest(**values)


@pytest.mark.parametrize("multipart", (False, True))
@pytest.mark.anyio
async def test_xray_prepare_locks_study_and_rejects_sixth_slot(
    multipart: bool,
) -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.image_service import (
        ImageService,
        ImageStateConflictError,
    )

    calls: list[str] = []

    class SeriesDal:
        async def get_by_id(self, series_id: str):
            return SimpleNamespace(id=series_id, study_id="study_1")

    class StudyDal:
        async def get_by_id_for_update(self, study_id: str):
            calls.append(study_id)
            return SimpleNamespace(
                id=study_id,
                session_id="session_1",
                modality_type="xray",
                status="ingesting",
            )

    class ImageDal:
        async def get_ready_logical(self, **kwargs):
            return None

        async def get_latest_logical(self, **kwargs):
            return None

        async def list_occupying_diagnostic_slots_for_study(self, study_id: str):
            return [
                SimpleNamespace(series_id="series_1", logical_image_key=f"key-{i}")
                for i in range(5)
            ]

        async def create_idempotent(self, values):
            raise AssertionError("sixth slot must fail before Image create")

    async def owned_session(**kwargs):
        return SimpleNamespace(status="processing")

    service = object.__new__(ImageService)
    service.series_dal = SeriesDal()
    service.study_dal = StudyDal()
    service.image_dal = ImageDal()
    service._owned_session = owned_session
    method = (
        service.prepare_multipart_upload if multipart else service.prepare_direct_upload
    )

    with pytest.raises(
        ImageStateConflictError,
        match="xray_study_image_capacity_exceeded",
    ):
        await method(
            payload=_image_prepare_payload(multipart=multipart),
            requester_id="requester_1",
            storage_profile="primary",
            upload_expires_at=datetime.now(timezone.utc),
        )

    assert calls == ["study_1"]


@pytest.mark.parametrize("multipart", (False, True))
@pytest.mark.anyio
async def test_xray_prepare_idempotent_uploading_replay_does_not_recount_capacity(
    multipart: bool,
) -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import (
        PROJECTION_SOURCE_CALLER,
        build_projection_metadata,
    )
    from apps.backend.services.runtime.service.image_service import ImageService

    payload = _image_prepare_payload(multipart=multipart)
    latest = SimpleNamespace(
        id="image_1",
        state_version=0,
        status="uploading",
        series_id=payload.series_id,
        source_image_id=payload.source_image_id,
        logical_image_key=payload.logical_image_key,
        source_manifest_json=payload.source_manifest,
        sequence_no=payload.sequence_no,
        image_role=payload.image_role,
        image_kind=payload.image_kind,
        metadata_schema_version=payload.metadata_schema_version,
        storage_profile="primary",
        file_format=payload.file_format,
        upload_mode="multipart" if multipart else "direct_put",
        expected_part_count=getattr(payload, "expected_part_count", None),
        expected_sha256=payload.expected_sha256,
        expected_size_bytes=payload.expected_size_bytes,
        declared_content_type=payload.declared_content_type,
        projection=payload.projection,
        technical_metadata_json=build_projection_metadata(
            payload.technical_metadata,
            source=PROJECTION_SOURCE_CALLER,
        ),
    )

    class SeriesDal:
        async def get_by_id(self, series_id: str):
            return SimpleNamespace(id=series_id, study_id="study_1")

    class StudyDal:
        async def get_by_id_for_update(self, study_id: str):
            return SimpleNamespace(
                id=study_id,
                session_id="session_1",
                modality_type="xray",
                status="ingesting",
            )

    class ImageDal:
        async def get_ready_logical(self, **kwargs):
            return None

        async def get_latest_logical(self, **kwargs):
            return latest

        async def refresh_upload_expiry(self, **kwargs):
            return latest

        async def list_occupying_diagnostic_slots_for_study(self, study_id: str):
            raise AssertionError("idempotent replay must not recount capacity")

    async def owned_session(**kwargs):
        return SimpleNamespace(status="processing")

    service = object.__new__(ImageService)
    service.series_dal = SeriesDal()
    service.study_dal = StudyDal()
    service.image_dal = ImageDal()
    service._owned_session = owned_session
    service._response = lambda image: image
    method = (
        service.prepare_multipart_upload if multipart else service.prepare_direct_upload
    )

    result = await method(
        payload=payload,
        requester_id="requester_1",
        storage_profile="primary",
        upload_expires_at=datetime.now(timezone.utc),
    )

    assert result is latest


@pytest.mark.parametrize("image_count", (1, 6))
def test_task_gate_rejects_anomalous_new_xray_study(image_count: int) -> None:
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    with pytest.raises(
        TaskStateConflictError,
        match="xray_task_image_count_out_of_range",
    ):
        TaskService._require_xray_task_image_count(
            modality_type="xray",
            task_type="diagnose",
            profile_key="xray_primary_v2",
            image_count=image_count,
        )


@pytest.mark.parametrize("image_count", (2, 3, 4, 5))
def test_task_gate_accepts_qualified_new_xray_study(image_count: int) -> None:
    from apps.backend.services.runtime.service.task_service import TaskService

    TaskService._require_xray_task_image_count(
        modality_type="xray",
        task_type="diagnose",
        profile_key="xray_primary_v2",
        image_count=image_count,
    )


@pytest.mark.parametrize(
    ("modality_type", "task_type", "profile_key"),
    (("ct", "diagnose", "xray_primary_v2"), ("xray", "replay", "zero_model_replay")),
)
def test_new_image_count_gates_preserve_non_xray_and_replay_paths(
    modality_type: str, task_type: str, profile_key: str
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import TaskService

    TaskService._require_xray_task_image_count(
        modality_type=modality_type,
        task_type=task_type,
        profile_key=profile_key,
        image_count=1,
    )
    AIRequestService._require_xray_image_count(
        config=SimpleNamespace(
            modality_type=modality_type,
            task_type=task_type,
            profile_key=profile_key,
        ),
        task=SimpleNamespace(
            request_snapshot_json={
                "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
            }
        ),
        image_count=1,
    )


def test_ai_request_preserves_historical_v2_xray_snapshot_count() -> None:
    from types import SimpleNamespace

    AIRequestService._require_xray_image_count(
        config=SimpleNamespace(
            modality_type="xray",
            task_type="diagnose",
            profile_key="xray_primary_v2",
        ),
        task=SimpleNamespace(
            request_snapshot_json={
                "snapshot_contract_version": "task-request-snapshot.v2",
            }
        ),
        image_count=1,
    )


@pytest.mark.anyio
async def test_network_boundary_rejects_expanded_image_count_mismatch() -> None:
    class Signer:
        async def sign(self, *, attempt_plan, ttl_seconds):
            return (object(),)

    with pytest.raises(GatewayContractError, match="ai_call_image_count_mismatch"):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(
                xray_image_contract_required=True,
                image_count_requested=2,
            ),
            image_signer=Signer(),
        )


def _anatomy_localization_receipt(image_count: int = 2) -> dict[str, Any]:
    return {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": image_count,
        "images": [
            {
                "sequence_no": index,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "series_sequence_no": index,
                "image_id": f"image_{index}",
                "logical_image_key": f"logical_{index}",
                "image_version_no": 1,
                "projection": "VD" if index == 1 else "Lateral",
                "projection_provenance": {
                    "source": "caller_declared",
                    "schema_version": "xray-projection.v1",
                },
                "sha256": f"{index}" * 64,
                "size_bytes": index * 10,
                "mime_type": "image/jpeg",
            }
            for index in range(1, image_count + 1)
        ],
    }


def _anatomy_localization_result(
    *, image_count: int = 2, species: str = "cat"
) -> dict[str, Any]:
    receipt = _anatomy_localization_receipt(image_count)
    return {
        "contract_version": "xray-anatomy-localization.v1",
        "label_contract_version": "xray-anatomy-labels.v1",
        "species": species,
        "result_status": "complete",
        "images": [
            {
                "image_id": item["image_id"],
                "series_id": item["series_id"],
                "sequence_no": item["sequence_no"],
                "projection": item["projection"],
                "series_manifest_sha256": item["series_manifest_sha256"],
                "status": "localized",
                "reason_code": None,
                "organs": [
                    {
                        "system": "cardiovascular",
                        "label": "heart",
                        "bbox": [0.1, 0.2, 0.8, 0.9],
                    }
                ],
            }
            for item in receipt["images"]
        ],
    }


def _anatomy_localization_query_facts():
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.core.imaging.manifest import manifest_sha256
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )
    from apps.backend.services.runtime.service.task_service import TaskService

    ordered_images = [
        {
            "image_id": f"image_{index}",
            "series_id": "series_1",
            "logical_image_key": f"logical_{index}",
            "image_version_no": 1,
            "sequence_no": index,
            "image_role": "original",
            "image_kind": "instance",
            "file_format": "jpg",
            "projection": "VD" if index == 1 else "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
            "storage_profile": "primary",
            "object_key": f"objects/{index}.jpg",
            "object_version_id": None,
            "sha256": f"{index}" * 64,
            "size_bytes": index * 10,
            "content_type": "image/jpeg",
        }
        for index in (1, 2)
    ]
    series_manifest_sha256 = manifest_sha256(ordered_images).sha256
    frozen_series = [
        {
            "series_id": "series_1",
            "series_key": "series-key-1",
            "series_no": 1,
            "manifest_contract_version": "series-image-manifest.v2",
            "manifest_sha256": series_manifest_sha256,
            "actual_image_count": 2,
            "ordered_images": ordered_images,
        }
    ]
    resolved_manifest_sha256 = manifest_sha256(
        [
            {
                "series_id": "series_1",
                "series_key": "series-key-1",
                "series_no": 1,
                "actual_image_count": 2,
                "manifest_sha256": series_manifest_sha256,
            }
        ]
    ).sha256
    receipt = {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": 2,
        "images": [
            {
                "sequence_no": index,
                "series_id": "series_1",
                "series_manifest_sha256": series_manifest_sha256,
                "series_sequence_no": index,
                "image_id": item["image_id"],
                "logical_image_key": item["logical_image_key"],
                "image_version_no": item["image_version_no"],
                "projection": item["projection"],
                "projection_provenance": item["projection_provenance"],
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
                "mime_type": item["content_type"],
            }
            for index, item in enumerate(ordered_images, start=1)
        ],
    }
    result = _anatomy_localization_result()
    for result_image, receipt_image in zip(
        result["images"], receipt["images"], strict=True
    ):
        for key in (
            "image_id",
            "series_id",
            "sequence_no",
            "projection",
            "series_manifest_sha256",
        ):
            result_image[key] = receipt_image[key]

    output_schema = AIConfigCompiler._output_schema(
        profile_key="xray_anatomy_localization_v1"
    )
    config = SimpleNamespace(
        id="config_1",
        profile_key="xray_anatomy_localization_v1",
        task_type="anatomy_localization",
        config_sha256="a" * 64,
        output_schema_sha256=sha256_json(output_schema),
        output_schema_json=output_schema,
        compiled_pipeline_sha256="b" * 64,
    )
    snapshot = {
        "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
        "species": "cat",
        "resolved_manifest_sha256": resolved_manifest_sha256,
        "series": frozen_series,
        "ai_config_id": config.id,
        "config_sha256": config.config_sha256,
        "output_schema_sha256": config.output_schema_sha256,
        "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
    }
    task = SimpleNamespace(
        id="task_1",
        requester_id="caller_1",
        task_type="anatomy_localization",
        execution_status="completed",
        ai_medical_status="not_produced",
        report_required=False,
        current_report_id=None,
        study_id="study_1",
        study_revision_id="revision_1",
        ai_config_id=config.id,
        request_snapshot_json=snapshot,
    )
    output = {
        "source_call_id": "call_1",
        "anatomy_localization_result": deepcopy(result),
    }
    stages = [
        SimpleNamespace(
            id="stage_1",
            stage_no=1,
            stage_key="study_preparation",
            handler_key="study_preparation",
            handler_version="v1",
            status="completed",
            output_json={"study_revision_id": "revision_1"},
            output_sha256=None,
        ),
        SimpleNamespace(
            id="stage_2",
            stage_no=2,
            stage_key="anatomy_localization",
            handler_key="anatomy_localization",
            handler_version="v1",
            status="completed",
            output_json=output,
            output_sha256=sha256_json(output),
        ),
    ]
    call = SimpleNamespace(
        id="call_1",
        task_id=task.id,
        stage_checkpoint_id=stages[1].id,
        ai_config_id=config.id,
        config_sha256=config.config_sha256,
        schema_sha256=config.output_schema_sha256,
        status="succeeded",
        result_disposition="accepted",
        attempt_count=1,
        winner_attempt_id="attempt_1",
        parsed_result_json=deepcopy(result),
        image_receipt_json=receipt,
        image_count_requested=2,
        image_count_sent=2,
        requested_image_manifest_sha256=resolved_manifest_sha256,
        sent_image_manifest_sha256=resolved_manifest_sha256,
    )
    attempt = SimpleNamespace(
        id="attempt_1",
        ai_call_id=call.id,
        attempt_no=1,
        status="succeeded",
    )
    facts = {
        "task": task,
        "stages": stages,
        "call": call,
        "attempt": attempt,
        "attempt_count": 1,
        "config": config,
        "result": result,
        "receipt": receipt,
    }

    async def get_task(_task_id: str):
        return facts["task"]

    async def list_stages(_task_id: str):
        return facts["stages"]

    async def get_call(_call_id: str):
        return facts["call"]

    async def get_config(_config_id: str):
        return facts["config"]

    async def get_attempt_count(**_kwargs):
        return facts["attempt_count"]

    async def get_attempt(**_kwargs):
        return facts["attempt"]

    service = object.__new__(TaskService)
    service.task_dal = SimpleNamespace(get_by_id=get_task)
    service.stage_dal = SimpleNamespace(list_for_task=list_stages)
    service.call_dal = SimpleNamespace(get_by_id=get_call)
    service.config_dal = SimpleNamespace(get_by_id=get_config)
    service.attempt_dal = SimpleNamespace(
        get_count=get_attempt_count,
        get_by_call_attempt_no=get_attempt,
    )
    service.config_compiler = SimpleNamespace(
        verify_frozen_integrity=lambda _config: None
    )
    return service, facts


@pytest.mark.anyio
async def test_anatomy_localization_query_returns_only_verified_lineage() -> None:
    from types import SimpleNamespace

    service, facts = _anatomy_localization_query_facts()

    response = await service.get_anatomy_localization(
        task_id="task_1",
        caller=SimpleNamespace(subject_id="caller_1"),
    )

    assert response.task_id == "task_1"
    assert response.stage_checkpoint_id == "stage_2"
    assert response.source_call_id == "call_1"
    assert response.output_sha256 == facts["stages"][1].output_sha256
    assert response.result.model_dump(mode="json") == facts["result"]
    assert facts["task"].report_required is False
    assert facts["task"].current_report_id is None
    assert facts["task"].ai_medical_status == "not_produced"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        (
            lambda facts: setattr(facts["task"], "task_type", "diagnose"),
            "task_not_anatomy_localization",
        ),
        (
            lambda facts: setattr(facts["task"], "execution_status", "running"),
            "anatomy_localization_not_ready",
        ),
        (
            lambda facts: setattr(facts["task"], "report_required", True),
            "anatomy_localization_not_ready",
        ),
        (
            lambda facts: setattr(facts["task"], "current_report_id", "report_1"),
            "anatomy_localization_not_ready",
        ),
        (
            lambda facts: setattr(facts["task"], "ai_medical_status", "produced"),
            "anatomy_localization_not_ready",
        ),
    ),
)
async def test_anatomy_localization_query_rejects_invalid_task_state(
    mutation,
    error_code: str,
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import (
        TaskStateConflictError,
    )

    service, facts = _anatomy_localization_query_facts()
    mutation(facts)

    with pytest.raises(TaskStateConflictError, match=error_code):
        await service.get_anatomy_localization(
            task_id="task_1",
            caller=SimpleNamespace(subject_id="caller_1"),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    (
        lambda facts: facts["stages"].pop(0),
        lambda facts: setattr(facts["stages"][1], "handler_version", "v2"),
        lambda facts: setattr(facts["stages"][1], "output_sha256", "0" * 64),
        lambda facts: setattr(facts["call"], "task_id", "task_other"),
        lambda facts: setattr(facts["call"], "stage_checkpoint_id", "stage_other"),
        lambda facts: setattr(facts["call"], "ai_config_id", "config_other"),
        lambda facts: setattr(facts["call"], "status", "failed"),
        lambda facts: setattr(facts["call"], "result_disposition", "rejected"),
        lambda facts: setattr(facts["call"], "attempt_count", 2),
        lambda facts: facts.update(attempt_count=2),
        lambda facts: setattr(facts["attempt"], "attempt_no", 2),
        lambda facts: setattr(facts["attempt"], "ai_call_id", "call_other"),
        lambda facts: setattr(facts["attempt"], "status", "failed"),
        lambda facts: setattr(facts["call"], "winner_attempt_id", "attempt_other"),
        lambda facts: setattr(facts["call"], "schema_sha256", "0" * 64),
        lambda facts: facts["config"].output_schema_json.update(
            {"x-ms-image-contract-version": "unknown.v1"}
        ),
        lambda facts: facts["task"].request_snapshot_json.update(
            {"config_sha256": "0" * 64}
        ),
        lambda facts: facts["call"]
        .parsed_result_json["images"][0]["organs"][0]
        .update({"bbox": [0.2, 0.2, 0.8, 0.9]}),
        lambda facts: facts["call"].image_receipt_json["images"].reverse(),
    ),
)
async def test_anatomy_localization_query_fails_closed_on_lineage_drift(
    mutation,
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import (
        TaskStateConflictError,
    )

    service, facts = _anatomy_localization_query_facts()
    mutation(facts)

    with pytest.raises(
        TaskStateConflictError,
        match="anatomy_localization_lineage_invalid",
    ):
        await service.get_anatomy_localization(
            task_id="task_1",
            caller=SimpleNamespace(subject_id="caller_1"),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "service_error",
    ("not_found", "access_denied"),
)
async def test_anatomy_localization_endpoint_hides_missing_and_non_owner_tasks(
    service_error: str,
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.api.api_v1.endpoints.anatomy_localizations import (
        get_anatomy_localization,
    )
    from apps.backend.services.runtime.service.task_service import (
        TaskAccessDeniedError,
        TaskNotFoundError,
    )

    error = (
        TaskNotFoundError("task_not_found")
        if service_error == "not_found"
        else TaskAccessDeniedError("task_access_denied")
    )

    class FakeService:
        async def get_anatomy_localization(self, **_kwargs):
            raise error

    class FakeDB:
        rolled_back = False

        async def rollback(self):
            self.rolled_back = True

    db = FakeDB()
    response = await get_anatomy_localization(
        task_id="task_1",
        context=SimpleNamespace(subject_id="caller_other"),
        service=FakeService(),
        db=db,
    )

    assert response.status_code == 404
    assert db.rolled_back is True
    assert b'"error_code":4041' in response.body


@pytest.mark.anyio
async def test_evaluation_export_rejects_localization_without_current_report() -> None:
    from types import SimpleNamespace

    from apps.backend.services.evaluation_control.service.evaluation_export_service import (
        EvaluationExportService,
        EvaluationExportValidationError,
    )

    _service, facts = _anatomy_localization_query_facts()

    async def get_task(_task_id: str):
        return facts["task"]

    export_service = object.__new__(EvaluationExportService)
    export_service.task_dal = SimpleNamespace(get_by_id=get_task)

    with pytest.raises(
        EvaluationExportValidationError,
        match="evaluation_export_report_missing",
    ):
        await export_service._build_case_row(
            spec=SimpleNamespace(task_id="task_1", report_id=None),
            payload=SimpleNamespace(),
        )


@pytest.mark.parametrize("image_count", (1, 6))
def test_anatomy_localization_task_gate_rejects_out_of_range_counts(
    image_count: int,
) -> None:
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    with pytest.raises(
        TaskStateConflictError,
        match="xray_task_image_count_out_of_range",
    ):
        TaskService._require_xray_task_image_count(
            modality_type="xray",
            task_type="anatomy_localization",
            profile_key="xray_anatomy_localization_v1",
            image_count=image_count,
        )


@pytest.mark.parametrize("image_count", (2, 3, 4, 5))
def test_anatomy_localization_task_gate_accepts_qualified_counts(
    image_count: int,
) -> None:
    from apps.backend.services.runtime.service.task_service import TaskService

    TaskService._require_xray_task_image_count(
        modality_type="xray",
        task_type="anatomy_localization",
        profile_key="xray_anatomy_localization_v1",
        image_count=image_count,
    )


def test_anatomy_localization_task_schema_and_config_binding_are_exact() -> None:
    from types import SimpleNamespace

    from apps.backend.schemas.task import TaskCreate
    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_1",
        task_type="anatomy_localization",
        species="cat",
        trace_id="trace_1",
    )
    assert payload.clinical_context is None
    with pytest.raises(
        ValidationError,
        match="task_species_required_for_anatomy_localization",
    ):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_2",
            task_type="anatomy_localization",
            trace_id="trace_2",
        )
    with pytest.raises(
        ValidationError,
        match="task_clinical_context_diagnose_only",
    ):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_3",
            task_type="anatomy_localization",
            species="cat",
            clinical_context=_clinical_context_v1(),
            trace_id="trace_3",
        )

    TaskService._validate_species_config_binding(
        config=SimpleNamespace(
            config_key="xray_anatomy_localization_cat",
            prompt_key="xray_cat_anatomy_localization",
            profile_key="xray_anatomy_localization_v1",
        ),
        task_type="anatomy_localization",
        species="cat",
    )
    with pytest.raises(TaskStateConflictError, match="task_config_invalid"):
        TaskService._validate_species_config_binding(
            config=SimpleNamespace(
                config_key="xray_anatomy_localization_cat",
                prompt_key="xray_cat_anatomy_localization",
                profile_key="xray_primary_v2",
            ),
            task_type="anatomy_localization",
            species="cat",
        )


@pytest.mark.parametrize(
    ("config_key", "prompt_key", "profile_key", "task_type", "species"),
    (
        (
            "xray_anatomy_localization_dog",
            "xray_dog_anatomy_localization",
            "xray_anatomy_localization_v1",
            "anatomy_localization",
            "cat",
        ),
        (
            "xray_anatomy_localization_cat",
            "xray_dog_anatomy_localization",
            "xray_anatomy_localization_v1",
            "anatomy_localization",
            "cat",
        ),
        (
            "xray_anatomy_localization_cat",
            "xray_cat_anatomy_localization",
            "xray_primary_v2",
            "anatomy_localization",
            "cat",
        ),
        (
            "xray_anatomy_localization_cat",
            "xray_cat_anatomy_localization",
            "xray_anatomy_localization_v1",
            "diagnose",
            "cat",
        ),
    ),
)
def test_anatomy_localization_task_config_cross_bindings_fail_closed(
    config_key: str,
    prompt_key: str,
    profile_key: str,
    task_type: str,
    species: str,
) -> None:
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.task_service import (
        TaskService,
        TaskStateConflictError,
    )

    with pytest.raises(TaskStateConflictError, match="task_config_invalid"):
        TaskService._validate_species_config_binding(
            config=SimpleNamespace(
                config_key=config_key,
                prompt_key=prompt_key,
                profile_key=profile_key,
            ),
            task_type=task_type,
            species=species,
        )


def test_anatomy_localization_profile_has_two_stages_and_one_provider_stage() -> None:
    from apps.backend.core.pipeline import (
        XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
        build_default_registry,
        compile_profile_contract,
    )
    from apps.backend.services.runtime.stages.registry import resolve_stage_handler

    contract, _ = compile_profile_contract(
        XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
        build_default_registry(),
    )
    assert [item["stage_key"] for item in contract["stages"]] == [
        "study_preparation",
        "anatomy_localization",
    ]
    assert [item["provider_required"] for item in contract["stages"]] == [
        False,
        True,
    ]
    assert contract["conditional_edges"] == []
    assert contract["dynamic_stage_definitions"] == []
    handler = resolve_stage_handler(
        handler_key="anatomy_localization",
        handler_version="v1",
    )
    assert handler.handler_key == "anatomy_localization"


@pytest.mark.anyio
async def test_anatomy_localization_stage_builds_one_pure_ai_request_and_consumes_it() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import manifest_sha256
    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.anatomy_localization import (
        AnatomyLocalizationStageHandler,
    )

    ordered_images = [
        {
            "image_id": f"image_{index}",
            "series_id": "series_1",
            "logical_image_key": f"logical_{index}",
            "image_version_no": 1,
            "sequence_no": index,
            "image_role": "original",
            "image_kind": "instance",
            "file_format": "jpg",
            "projection": "VD" if index == 1 else "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
            "storage_profile": "primary",
            "object_key": f"objects/{index}.jpg",
            "object_version_id": None,
            "sha256": f"{index}" * 64,
            "size_bytes": index * 10,
            "content_type": "image/jpeg",
        }
        for index in (1, 2)
    ]
    series_manifest = manifest_sha256(ordered_images).sha256
    study_manifest = manifest_sha256(
        [
            {
                "series_id": "series_1",
                "series_key": "series-key-1",
                "series_no": 1,
                "actual_image_count": 2,
                "manifest_sha256": series_manifest,
            }
        ]
    ).sha256
    context = StageExecutionContext(
        task=SimpleNamespace(
            id="task_1",
            request_snapshot_json={
                "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
                "species": "cat",
                "resolved_manifest_sha256": study_manifest,
                "series": [
                    {
                        "series_id": "series_1",
                        "series_key": "series-key-1",
                        "series_no": 1,
                        "manifest_contract_version": "series-image-manifest.v2",
                        "manifest_sha256": series_manifest,
                        "actual_image_count": 2,
                        "ordered_images": ordered_images,
                    }
                ],
            },
        ),
        stage=SimpleNamespace(
            stage_key="anatomy_localization",
            input_json={"study_revision_id": "revision_1"},
        ),
    )
    handler = AnatomyLocalizationStageHandler()
    plan = await handler.execute(context)
    assert plan.completed_result is None
    assert plan.ai_request is not None
    safe_context = plan.ai_request.prompt_command.safe_context
    assert set(safe_context) == {
        "task_id",
        "study_revision_id",
        "species",
        "resolved_manifest_sha256",
        "ordered_image_refs",
    }
    assert "clinical_context_allowlist" not in safe_context

    result = _anatomy_localization_result()
    consumed = handler.consume_ai_call(
        context,
        {
            "call_id": "call_1",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": result,
        },
    )
    assert consumed.status == "completed"
    assert consumed.output == {
        "source_call_id": "call_1",
        "anatomy_localization_result": result,
    }


@pytest.mark.anyio
async def test_anatomy_localization_prepare_structured_call_creates_one_call_and_attempt() -> (
    None
):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestService,
        AIRequestStateConflict,
    )

    budget = {
        "contract_version": "ai-budget-policy.v1",
        "max_prompt_chars": 120_000,
        "max_input_images": 5,
        "max_total_calls": 1,
        "max_total_attempts": 1,
        "task_deadline_ms": 120_000,
        "reserve_before_send": True,
    }
    budget_sha = sha256_json(budget)
    lane = {
        "lane_key": "primary",
        "connection_id": "connection_1",
        "connection_sha256": "1" * 64,
        "provider_type": "openai_compatible",
        "api_format": "chat-completions",
        "requested_model": "provider-model",
        "max_attempts": 1,
        "timeout_ms": 120_000,
        "generation_params": {
            "temperature": 0.1,
            "top_p": 1.0,
            "max_output_tokens": 8_192,
        },
    }
    config = SimpleNamespace(
        id="config_1",
        status="active",
        config_contract_version="ai-config.v2",
        config_key="xray_anatomy_localization_cat",
        version="1.0.0",
        modality_type="xray",
        task_type="anatomy_localization",
        profile_key="xray_anatomy_localization_v1",
        config_sha256="2" * 64,
        release_fingerprint="3" * 64,
        prompt_content_sha256="4" * 64,
        model_snapshot_sha256="5" * 64,
        output_schema_sha256="6" * 64,
        compiled_pipeline_sha256="7" * 64,
        stage_registry_contract_version="stage-registry.v1",
        gateway_profile_json={
            "contract_version": "ai-gateway-profile.v1",
            "adapter_key": "openai-compatible",
            "provider_enabled": True,
            "qualification_status": "qualified",
            "streaming_mode": "json",
            "image_url_ttl_seconds": 300,
            "allowed_actual_models": ["provider-model"],
        },
        model_snapshot_json={"lanes": [lane]},
        budget_policy_json=budget,
    )
    snapshot = {
        "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
        "ai_config_id": config.id,
        "config_key": config.config_key,
        "config_version": config.version,
        "config_contract_version": config.config_contract_version,
        "config_sha256": config.config_sha256,
        "release_fingerprint": config.release_fingerprint,
        "prompt_content_sha256": config.prompt_content_sha256,
        "model_snapshot_sha256": config.model_snapshot_sha256,
        "output_schema_sha256": config.output_schema_sha256,
        "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
        "stage_registry_contract_version": config.stage_registry_contract_version,
        "series": [{"actual_image_count": 2}],
    }
    task = SimpleNamespace(
        id="task_1",
        ai_config_id=config.id,
        modality_type="xray",
        task_type="anatomy_localization",
        request_snapshot_json=snapshot,
        compiled_pipeline_sha256=config.compiled_pipeline_sha256,
        stage_registry_contract_version=config.stage_registry_contract_version,
        budget_snapshot_json=budget,
        budget_reserved_json={
            "contract_version": "task-budget-reservation.v1",
            "budget_policy_sha256": budget_sha,
            "reserved_call_units": 0,
            "reserved_attempts": 0,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
        attempt_no=1,
        cancel_requested_at=None,
        execution_status="running",
        state_version=1,
    )
    stage = SimpleNamespace(
        id="stage_2",
        task_id=task.id,
        retry_count=0,
        input_json={"manifest_sha256": "8" * 64},
        input_sha256="9" * 64,
    )

    class NestedTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class FakeDB:
        def begin_nested(self):
            return NestedTransaction()

    class FakeCallDal:
        def __init__(self) -> None:
            self.db = FakeDB()
            self.created: list[Any] = []
            self.by_logical_key: dict[str, Any] = {}

        async def get_by_logical_key_for_update(self, logical_call_key: str):
            return self.by_logical_key.get(logical_call_key)

        async def create_data(self, values: dict[str, Any], *, v_return_obj: bool):
            assert v_return_obj is True
            item = SimpleNamespace(
                **values,
                state_version=1,
                winner_attempt_id=None,
                error_code=None,
                parsed_result_json=None,
            )
            self.created.append(item)
            self.by_logical_key[item.logical_call_key] = item
            return item

        async def get_by_id_for_update(self, call_id: str):
            return next((item for item in self.created if item.id == call_id), None)

    class FakeTaskDal:
        async def get_by_id(self, task_id: str):
            return task if task_id == task.id else None

        async def get_by_id_for_update(self, task_id: str):
            return task if task_id == task.id else None

        async def cas_update(self, **kwargs):
            assert kwargs["task_id"] == task.id
            task.budget_reserved_json = kwargs["values"]["budget_reserved_json"]
            task.state_version += 1
            return task

    class FakeAttemptDal:
        def __init__(self) -> None:
            self.created: list[Any] = []

        async def get_by_call_attempt_no(self, *, ai_call_id: str, attempt_no: int):
            return next(
                (
                    item
                    for item in self.created
                    if item.ai_call_id == ai_call_id and item.attempt_no == attempt_no
                ),
                None,
            )

        async def create_idempotent(self, values: dict[str, Any]):
            item = SimpleNamespace(**values, error_code=None)
            self.created.append(item)
            return item

        async def get_count(self, *, ai_call_id: str):
            return sum(item.ai_call_id == ai_call_id for item in self.created)

    call_dal = FakeCallDal()
    attempt_dal = FakeAttemptDal()
    service = object.__new__(AIRequestService)
    service.call_dal = call_dal
    service.attempt_dal = attempt_dal
    service.task_dal = FakeTaskDal()

    async def get_stage(stage_id: str):
        return stage if stage_id == stage.id else None

    async def get_config(config_id: str):
        return config if config_id == config.id else None

    service.stage_dal = SimpleNamespace(get_by_id=get_stage)
    service.config_dal = SimpleNamespace(get_by_id=get_config)
    service.config_compiler = SimpleNamespace(
        verify_frozen_integrity=lambda _config: None
    )
    service._runtime_gate_allows = lambda: True
    service._render_v2_messages = lambda **_kwargs: (
        SimpleNamespace(
            rendered_text="localization prompt",
            rendered_prompt_sha256="a" * 64,
            context_sha256="b" * 64,
        ),
        SimpleNamespace(messages_json=[], messages_sha256="c" * 64),
        {},
    )
    service._build_v2_request_facts = lambda **_kwargs: (
        {},
        "d" * 64,
        "logical-localization-1",
    )
    prompt_command = SimpleNamespace(prompt_kind="anatomy_localization")

    first = await service.prepare_structured_call(
        task_id=task.id,
        stage_checkpoint_id=stage.id,
        prompt_command=prompt_command,
        trace_id="trace_1",
        request_id="request_1",
    )
    second = await service.prepare_structured_call(
        task_id=task.id,
        stage_checkpoint_id=stage.id,
        prompt_command=prompt_command,
        trace_id="trace_1",
        request_id="request_1",
    )

    assert first["call_id"] == second["call_id"]
    assert first["attempt_id"] == second["attempt_id"]
    assert first["network_required"] is True
    assert len(call_dal.created) == 1
    assert len(attempt_dal.created) == 1
    call = call_dal.created[0]
    attempt = attempt_dal.created[0]
    assert call.execution_mode == "single"
    assert call.attempt_count == 1
    assert call.budget_reservation_json["reserved_call_units"] == 1
    assert call.budget_reservation_json["reserved_attempts"] == 1
    assert lane["lane_key"] == "primary"
    assert lane["max_attempts"] == 1
    assert attempt.ai_call_id == call.id
    assert attempt.attempt_no == 1

    with pytest.raises(
        AIRequestStateConflict,
        match="ai_call_attempt_budget_exceeded",
    ):
        await service.prepare_retry_attempt(
            call_id=call.id,
            trace_id="trace_retry",
            request_id="request_retry",
        )
    assert len(attempt_dal.created) == 1


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[-0.1, 0.2, 0.8, 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[0.1, 0.2, 1.1, 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[float("nan"), 0.2, 0.8, 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[0.1, 0.2, float("inf"), 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[0.1, 0.2, 0.1, 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[0.1, 0.9, 0.8, 0.2]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                bbox=[0.8, 0.2, 0.1, 0.9]
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(label="unknown"),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"][0].update(
                system="respiratory"
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result["images"][0]["organs"].append(
                deepcopy(result["images"][0]["organs"][0])
            ),
            "anatomy_localization_organ_invalid",
        ),
        (
            lambda result: result.update(result_status="partial"),
            "anatomy_localization_result_status_invalid",
        ),
    ),
)
def test_anatomy_localization_validator_rejects_bbox_label_and_status_drift(
    mutation,
    error_code: str,
) -> None:
    from apps.backend.core.ai.anatomy_localization_contract import (
        AnatomyLocalizationContractError,
        validate_anatomy_localization_result_contract,
    )

    result = _anatomy_localization_result()
    mutation(result)
    with pytest.raises(AnatomyLocalizationContractError, match=error_code):
        validate_anatomy_localization_result_contract(
            result=result,
            schema_contract_version="xray-anatomy-localization.v1",
            image_receipt=_anatomy_localization_receipt(),
            expected_species="cat",
        )


@pytest.mark.parametrize(
    ("image_ordinal", "field_name", "invalid_value"),
    (
        (1, "image_id", "wrong-image"),
        (1, "series_id", "wrong-series"),
        (1, "sequence_no", 99),
        (2, "projection", "DV"),
        (1, "series_manifest_sha256", "f" * 64),
    ),
)
def test_anatomy_localization_validator_reports_exact_lineage_mismatch(
    image_ordinal: int,
    field_name: str,
    invalid_value: Any,
) -> None:
    from apps.backend.core.ai.anatomy_localization_contract import (
        AnatomyLocalizationContractError,
        validate_anatomy_localization_result_contract,
    )

    result = _anatomy_localization_result()
    result["images"][image_ordinal - 1][field_name] = invalid_value
    expected_error = f"anatomy_localization_image_{image_ordinal}_{field_name}_mismatch"
    with pytest.raises(
        AnatomyLocalizationContractError,
        match=expected_error,
    ) as raised:
        validate_anatomy_localization_result_contract(
            result=result,
            schema_contract_version="xray-anatomy-localization.v1",
            image_receipt=_anatomy_localization_receipt(),
            expected_species="cat",
        )

    assert str(raised.value) == expected_error
    assert len(expected_error) <= 80


@pytest.mark.parametrize(
    "mutation",
    (
        lambda receipt: (
            receipt["images"].pop(),
            receipt.update(image_count=1),
        ),
        lambda receipt: (
            receipt["images"].append(
                {
                    **deepcopy(receipt["images"][-1]),
                    "sequence_no": 3,
                    "series_sequence_no": 3,
                    "image_id": "image_3",
                    "logical_image_key": "logical_3",
                    "sha256": "3" * 64,
                }
            ),
            receipt.update(image_count=3),
        ),
        lambda receipt: receipt["images"].__setitem__(
            1, deepcopy(receipt["images"][0])
        ),
        lambda receipt: receipt["images"].reverse(),
        lambda receipt: receipt["images"][0].update(projection="DV"),
    ),
)
def test_anatomy_localization_receipt_must_exactly_match_frozen_snapshot(
    mutation,
) -> None:
    from apps.backend.core.ai.anatomy_localization_contract import (
        AnatomyLocalizationContractError,
        validate_anatomy_localization_receipt_against_snapshot,
    )

    _service, facts = _anatomy_localization_query_facts()
    receipt = deepcopy(facts["call"].image_receipt_json)
    mutation(receipt)
    with pytest.raises(
        AnatomyLocalizationContractError,
        match="anatomy_localization_snapshot_receipt_mismatch",
    ):
        validate_anatomy_localization_receipt_against_snapshot(
            snapshot=facts["task"].request_snapshot_json,
            image_receipt=receipt,
        )


@pytest.mark.parametrize(
    ("schema_contract_version", "expected_species", "result_species", "error_code"),
    (
        (
            None,
            "cat",
            "cat",
            "provider_result_contract_version_unsupported",
        ),
        (
            "unknown-contract.v1",
            "cat",
            "cat",
            "provider_result_contract_version_unsupported",
        ),
        (
            "xray-anatomy-localization.v1",
            "hamster",
            "cat",
            "anatomy_localization_expected_species_invalid",
        ),
        (
            "xray-anatomy-localization.v1",
            "cat",
            "dog",
            "anatomy_localization_result_identity_invalid",
        ),
    ),
)
def test_anatomy_localization_validator_rejects_unfrozen_identity(
    schema_contract_version: str | None,
    expected_species: str,
    result_species: str,
    error_code: str,
) -> None:
    from apps.backend.core.ai.anatomy_localization_contract import (
        AnatomyLocalizationContractError,
        validate_anatomy_localization_result_contract,
    )

    with pytest.raises(AnatomyLocalizationContractError, match=error_code):
        validate_anatomy_localization_result_contract(
            result=_anatomy_localization_result(species=result_species),
            schema_contract_version=schema_contract_version,
            image_receipt=_anatomy_localization_receipt(),
            expected_species=expected_species,
        )


def test_anatomy_localization_validator_accepts_partial_and_unavailable() -> None:
    from apps.backend.core.ai.anatomy_localization_contract import (
        validate_anatomy_localization_result_contract,
    )

    partial = _anatomy_localization_result()
    partial["images"][1].update(
        status="not_localized",
        reason_code="insufficient_localization_evidence",
        organs=[],
    )
    partial["result_status"] = "partial"
    assert (
        validate_anatomy_localization_result_contract(
            result=partial,
            schema_contract_version="xray-anatomy-localization.v1",
            image_receipt=_anatomy_localization_receipt(),
            expected_species="cat",
        )
        == partial
    )

    unavailable = deepcopy(partial)
    unavailable["images"][0].update(
        status="not_localized",
        reason_code="no_supported_anatomy_visible",
        organs=[],
    )
    unavailable["result_status"] = "unavailable"
    assert (
        validate_anatomy_localization_result_contract(
            result=unavailable,
            schema_contract_version="xray-anatomy-localization.v1",
            image_receipt=_anatomy_localization_receipt(),
            expected_species="cat",
        )
        == unavailable
    )


@pytest.mark.anyio
async def test_network_localization_lineage_rejection_preserves_provider_summary() -> (
    None
):
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )

    receipt = _anatomy_localization_receipt()
    rejected_result = _anatomy_localization_result()
    rejected_result["images"][1]["projection"] = "DV"
    provider_body = {
        "choices": [{"message": {"content": json.dumps(rejected_result)}}],
        "model": "provider-model",
        "usage": {"total_tokens": 23},
    }

    class Signer:
        async def sign(self, **_kwargs):
            return [
                GatewayImageInput(
                    sequence_no=item["sequence_no"],
                    mime_type=item["mime_type"],
                    signed_url=(
                        f"https://bucket.example/{item['image_id']}.jpg?signature=x"
                    ),
                )
                for item in receipt["images"]
            ]

    class Gateway:
        async def chat_completions(self, *_args, **_kwargs):
            return {
                "request_id": "provider-request-1",
                "body": provider_body,
            }

    with pytest.raises(GatewayDefiniteResponseError) as raised:
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(
                response_schema=AIConfigCompiler._output_schema(
                    profile_key="xray_anatomy_localization_v1"
                ),
                image_count_requested=2,
                image_inputs=tuple(receipt["images"]),
                snapshot_contract_version=TASK_REQUEST_SNAPSHOT_V3,
                xray_image_contract_required=True,
                expected_species="cat",
            ),
            gateway_client=Gateway(),
            image_signer=Signer(),
        )

    assert str(raised.value) == "anatomy_localization_image_2_projection_mismatch"
    assert raised.value.provider_request_id == "provider-request-1"
    assert raised.value.actual_model == "provider-model"
    assert raised.value.usage_json == {"total_tokens": 23}
    assert raised.value.response_sha256 == response_sha256(provider_body)


@pytest.mark.anyio
async def test_network_dispatches_localization_by_frozen_schema_contract() -> None:
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )

    receipt = _anatomy_localization_receipt()
    result = _anatomy_localization_result()

    class Signer:
        async def sign(self, **_kwargs):
            return [
                GatewayImageInput(
                    sequence_no=item["sequence_no"],
                    mime_type=item["mime_type"],
                    signed_url=(
                        f"https://bucket.example/{item['image_id']}.jpg?signature=x"
                    ),
                )
                for item in receipt["images"]
            ]

    class Gateway:
        async def chat_completions(self, *_args, **_kwargs):
            return {
                "request_id": "provider-request-1",
                "body": {
                    "choices": [{"message": {"content": json.dumps(result)}}],
                    "model": "provider-model",
                },
            }

    response = await AIRequestService.execute_gateway_attempt_network(
        network_plan=_network_plan(
            response_schema=AIConfigCompiler._output_schema(
                profile_key="xray_anatomy_localization_v1"
            ),
            image_count_requested=2,
            image_inputs=tuple(receipt["images"]),
            snapshot_contract_version=TASK_REQUEST_SNAPSHOT_V3,
            xray_image_contract_required=True,
            expected_species="cat",
        ),
        gateway_client=Gateway(),
        image_signer=Signer(),
    )
    assert response["execution"].parsed_result_json == result

    class EmptySigner:
        async def sign(self, **_kwargs):
            return []

    class GenericGateway:
        async def chat_completions(self, *_args, **_kwargs):
            return {
                "request_id": "provider-request-2",
                "body": {
                    "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
                    "model": "provider-model",
                },
            }

    with pytest.raises(
        GatewayContractError,
        match="provider_result_contract_version_unsupported",
    ):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(
                response_schema=SCHEMA,
                image_count_requested=0,
            ),
            gateway_client=GenericGateway(),
            image_signer=EmptySigner(),
        )


def _study_screening_receipt() -> dict[str, Any]:
    return {
        "contract_version": AI_IMAGE_RECEIPT_V2,
        "image_count": 2,
        "images": [
            {
                "sequence_no": 1,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "series_sequence_no": 1,
                "image_id": "image_1",
                "logical_image_key": "logical_1",
                "image_version_no": 1,
                "projection": "VD",
                "projection_provenance": {
                    "source": "caller_declared",
                    "schema_version": "xray-projection.v1",
                },
                "sha256": "a" * 64,
                "size_bytes": 10,
                "mime_type": "image/jpeg",
            },
            {
                "sequence_no": 2,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "series_sequence_no": 2,
                "image_id": "image_2",
                "logical_image_key": "logical_2",
                "image_version_no": 1,
                "projection": "Lateral",
                "projection_provenance": {
                    "source": "caller_declared",
                    "schema_version": "xray-projection.v1",
                },
                "sha256": "b" * 64,
                "size_bytes": 20,
                "mime_type": "image/jpeg",
            },
        ],
    }


def _study_screening_result() -> dict[str, Any]:
    return {
        "contract_version": "xray-study-screening.v1",
        "species": "cat",
        "study_quality_status": "diagnostic",
        "coverage_summary": {
            "view_adequacy": "adequate",
            "summary": "Two frozen source images were screened.",
            "assessed_families": ["thoracic"],
        },
        "technical_limitations": [],
        "emergency_signals": [],
        "screening_findings": [],
        "families_requiring_analysis": ["thoracic"],
        "families_not_assessed": [],
        "source_refs": [
            {
                "source_ref_id": "source_1",
                "image_id": "image_1",
                "sequence_no": 1,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "projection": "VD",
            },
            {
                "source_ref_id": "source_2",
                "image_id": "image_2",
                "sequence_no": 2,
                "series_id": "series_1",
                "series_manifest_sha256": "1" * 64,
                "projection": "Lateral",
            },
        ],
    }


def test_task_create_quality_review_reference_is_screening_bound() -> None:
    from apps.backend.schemas.task import TaskCreate

    payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_1",
        task_type="diagnose",
        species="cat",
        quality_review_task_id=" quality_task_1 ",
        trace_id="trace_1",
    )
    assert payload.quality_review_task_id == "quality_task_1"

    screening_payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_2",
        task_type="xray_study_screening",
        species="cat",
        quality_review_task_id=" quality_task_1 ",
        trace_id="trace_2",
    )
    assert screening_payload.quality_review_task_id == "quality_task_1"

    with pytest.raises(
        ValidationError,
        match="task_species_required_for_xray_study_screening",
    ):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_3",
            task_type="xray_study_screening",
            quality_review_task_id="quality_task_1",
            trace_id="trace_3",
        )

    with pytest.raises(
        ValidationError,
        match="task_quality_review_reference_diagnose_only",
    ):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_4",
            task_type="xray_quality_control",
            species="cat",
            quality_review_task_id="quality_task_1",
            trace_id="trace_4",
        )


def test_study_screening_v2_task_type_uses_isolated_config_slot() -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging.xray_contract import (
        XRAY_STUDY_SCREENING_TASK_TYPE,
        requires_xray_runtime_image_contract,
    )
    from apps.backend.core.pipeline import XRAY_STUDY_SCREENING_PROFILE_V2
    from apps.backend.services.runtime.service.task_service import TaskService

    assert TaskService.TASK_PROFILES[XRAY_STUDY_SCREENING_TASK_TYPE] == frozenset(
        {XRAY_STUDY_SCREENING_PROFILE_V2}
    )
    assert (
        TaskService._config_key_for_task(
            task_type=XRAY_STUDY_SCREENING_TASK_TYPE,
            species="cat",
        )
        == "xray_study_screening_cat"
    )
    TaskService._validate_species_config_binding(
        config=SimpleNamespace(
            config_key="xray_study_screening_cat",
            prompt_key="xray_cat_study_screening",
            profile_key=XRAY_STUDY_SCREENING_PROFILE_V2,
        ),
        task_type=XRAY_STUDY_SCREENING_TASK_TYPE,
        species="cat",
    )
    assert requires_xray_runtime_image_contract(
        modality_type="xray",
        task_type=XRAY_STUDY_SCREENING_TASK_TYPE,
        profile_key=XRAY_STUDY_SCREENING_PROFILE_V2,
    )


def test_diagnose_full_chain_uses_xray_image_contract() -> None:
    from apps.backend.core.imaging.xray_contract import (
        requires_exact_xray_five_image_config_contract,
        requires_xray_runtime_image_contract,
    )
    from apps.backend.core.pipeline import XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1

    assert requires_xray_runtime_image_contract(
        modality_type="xray",
        task_type="diagnose",
        profile_key=XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    )
    assert requires_exact_xray_five_image_config_contract(
        modality_type="xray",
        task_type="diagnose",
        profile_key=XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    )


@pytest.mark.anyio
async def test_study_screening_stage_builds_quality_bound_request_and_consumes_it() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import manifest_sha256
    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.study_screening import (
        StudyScreeningStageHandler,
    )

    ordered_images = [
        {
            "image_id": f"image_{index}",
            "series_id": "series_1",
            "logical_image_key": f"logical_{index}",
            "image_version_no": 1,
            "sequence_no": index,
            "image_role": "original",
            "image_kind": "instance",
            "file_format": "jpg",
            "projection": "VD" if index == 1 else "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
            "storage_profile": "primary",
            "object_key": f"objects/{index}.jpg",
            "object_version_id": None,
            "sha256": ("a" if index == 1 else "b") * 64,
            "size_bytes": index * 10,
            "content_type": "image/jpeg",
        }
        for index in (1, 2)
    ]
    series_manifest = manifest_sha256(ordered_images).sha256
    study_manifest = manifest_sha256(
        [
            {
                "series_id": "series_1",
                "series_key": "series-key-1",
                "series_no": 1,
                "actual_image_count": 2,
                "manifest_sha256": series_manifest,
            }
        ]
    ).sha256
    quality_result = {"contract_version": "xray-image-quality.v1", "images": []}
    context = StageExecutionContext(
        task=SimpleNamespace(
            id="task_1",
            request_snapshot_json={
                "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
                "species": "cat",
                "resolved_manifest_sha256": study_manifest,
                "quality_review": {"result": quality_result},
                "series": [
                    {
                        "series_id": "series_1",
                        "series_key": "series-key-1",
                        "series_no": 1,
                        "manifest_contract_version": "series-image-manifest.v2",
                        "manifest_sha256": series_manifest,
                        "actual_image_count": 2,
                        "ordered_images": ordered_images,
                    }
                ],
            },
        ),
        stage=SimpleNamespace(
            stage_key="study_screening",
            input_json={"study_revision_id": "revision_1"},
        ),
    )
    handler = StudyScreeningStageHandler()
    plan = await handler.execute(context)
    assert plan.completed_result is None
    assert plan.ai_request is not None
    command = plan.ai_request.prompt_command
    assert command.prompt_kind == "study_screening"
    assert command.quality_results == quality_result
    assert command.safe_context["task_id"] == "task_1"
    assert command.safe_context["study_revision_id"] == "revision_1"
    assert command.safe_context["species"] == "cat"
    assert command.safe_context["resolved_manifest_sha256"] == study_manifest
    assert len(command.safe_context["ordered_image_refs"]) == 2

    variables = AIRequestService._v2_safe_variables(
        config=SimpleNamespace(
            prompt_variables_json={
                "contract_version": "prompt-variables.v1",
                "required": [
                    "SAFE_STUDY_CONTEXT_JSON",
                    "QUALITY_RESULTS_JSON",
                    "OUTPUT_SCHEMA_JSON",
                ],
                "optional": [],
            },
            output_schema_json={"type": "object"},
        ),
        prompt_command=command,
    )
    assert variables == {
        "SAFE_STUDY_CONTEXT_JSON": command.safe_context,
        "QUALITY_RESULTS_JSON": quality_result,
        "OUTPUT_SCHEMA_JSON": {"type": "object"},
    }

    result = _study_screening_result()
    consumed = handler.consume_ai_call(
        context,
        {
            "call_id": "call_1",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": result,
        },
    )
    assert consumed.status == "completed"
    assert consumed.output == {
        "source_call_id": "call_1",
        "study_screening_result": result,
    }


@pytest.mark.anyio
async def test_study_screening_stage_config_binding_is_resolved_and_validated() -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.services.runtime.service.ai_request_service import (
        AIRequestStateConflict,
    )

    budget = {
        "contract_version": "ai-budget-policy.v1",
        "max_prompt_chars": 120000,
        "max_input_images": 5,
        "max_total_calls": 2,
        "max_total_attempts": 2,
        "task_deadline_ms": 120000,
        "reserve_before_send": True,
    }
    stage_config = SimpleNamespace(
        id="stage_config_1",
        config_key="xray_study_screening_cat",
        version="1.0.0",
        profile_key="xray_study_screening_v1",
        prompt_key="xray_cat_study_screening",
        activation_scope="global",
        scope_key="global",
        config_sha256="1" * 64,
        release_fingerprint="2" * 64,
        prompt_content_sha256="3" * 64,
        model_snapshot_sha256="4" * 64,
        output_schema_sha256="5" * 64,
        compiled_pipeline_sha256="6" * 64,
        stage_registry_contract_version="stage-registry.v1",
        budget_policy_json=budget,
        task_type="diagnose",
    )
    binding = {
        "ai_config_id": stage_config.id,
        "config_key": stage_config.config_key,
        "config_version": stage_config.version,
        "profile_key": stage_config.profile_key,
        "prompt_key": stage_config.prompt_key,
        "activation_scope": stage_config.activation_scope,
        "scope_key": stage_config.scope_key,
        "config_sha256": stage_config.config_sha256,
        "release_fingerprint": stage_config.release_fingerprint,
        "prompt_content_sha256": stage_config.prompt_content_sha256,
        "model_snapshot_sha256": stage_config.model_snapshot_sha256,
        "output_schema_sha256": stage_config.output_schema_sha256,
        "compiled_pipeline_sha256": stage_config.compiled_pipeline_sha256,
        "stage_registry_contract_version": (
            stage_config.stage_registry_contract_version
        ),
        "budget_policy_sha256": sha256_json(budget),
    }
    root_pipeline_sha = "7" * 64
    snapshot = {
        "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
        "profile_key": "xray_diagnose_study_screening_v1",
        "species": "cat",
        "compiled_pipeline_sha256": root_pipeline_sha,
        "stage_registry_contract_version": "stage-registry.v1",
        "stage_ai_config_bindings": {"study_screening": binding},
    }
    task = SimpleNamespace(
        ai_config_id="root_config_1",
        task_type="diagnose",
        request_snapshot_json=snapshot,
        budget_snapshot_json=budget,
        budget_reserved_json={"budget_policy_sha256": sha256_json(budget)},
        compiled_pipeline_sha256=root_pipeline_sha,
        stage_registry_contract_version="stage-registry.v1",
    )
    stage = SimpleNamespace(stage_key="study_screening")

    class FakeConfigDal:
        async def get_by_id(self, config_id: str):
            return stage_config if config_id == stage_config.id else None

    service = object.__new__(AIRequestService)
    service.config_dal = FakeConfigDal()
    assert await service._resolve_task_stage_config(task=task, stage=stage) is (
        stage_config
    )
    service._validate_v2_task_config_snapshot(
        task=task,
        stage=stage,
        config=stage_config,
    )

    snapshot["stage_ai_config_bindings"]["study_screening"] = {
        **binding,
        "prompt_content_sha256": "f" * 64,
    }
    with pytest.raises(AIRequestStateConflict, match="task_config_snapshot_mismatch"):
        service._validate_v2_task_config_snapshot(
            task=task,
            stage=stage,
            config=stage_config,
        )


@pytest.mark.anyio
async def test_ai_request_config_resolution_preserves_historical_root_binding() -> None:
    from types import SimpleNamespace

    root_config = SimpleNamespace(id="root_config_1")
    task = SimpleNamespace(
        ai_config_id=root_config.id,
        request_snapshot_json={},
    )
    stage = SimpleNamespace(stage_key="joint_primary_reader")

    class FakeConfigDal:
        async def get_by_id(self, config_id: str):
            return root_config if config_id == root_config.id else None

    service = object.__new__(AIRequestService)
    service.config_dal = FakeConfigDal()
    assert await service._resolve_task_stage_config(task=task, stage=stage) is (
        root_config
    )


def test_study_screening_validator_enforces_frozen_source_lineage() -> None:
    from apps.backend.core.ai.study_screening_contract import (
        XRayStudyScreeningContractError,
        validate_xray_study_screening_result_contract,
    )

    result = _study_screening_result()
    assert (
        validate_xray_study_screening_result_contract(
            result=result,
            schema_contract_version="xray-study-screening.v1",
            image_receipt=_study_screening_receipt(),
            expected_species="cat",
        )
        == result
    )

    drifted = deepcopy(result)
    drifted["source_refs"][0]["projection"] = "DV"
    with pytest.raises(
        XRayStudyScreeningContractError,
        match="study_screening_source_projection_mismatch",
    ):
        validate_xray_study_screening_result_contract(
            result=drifted,
            schema_contract_version="xray-study-screening.v1",
            image_receipt=_study_screening_receipt(),
            expected_species="cat",
        )


def _study_screening_provider_v2_result() -> dict[str, Any]:
    result = _study_screening_result()
    result["contract_version"] = "xray-study-screening-provider.v2"
    result["source_refs"] = [
        {
            "source_ref_id": item["source_ref_id"],
            "image_id": item["image_id"],
        }
        for item in result["source_refs"]
    ]
    return result


def test_study_screening_v2_canonicalizes_only_receipt_owned_lineage() -> None:
    from apps.backend.core.ai.study_screening_contract import (
        XRAY_STUDY_SCREENING_CANONICAL_CONTRACT_V2,
        XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
        canonicalize_xray_study_screening_result,
        validate_xray_study_screening_provider_result_contract,
    )

    provider_result = _study_screening_provider_v2_result()
    provider_before = deepcopy(provider_result)
    receipt = _study_screening_receipt()
    receipt["images"][0]["projection"] = "UNKNOWN"

    validated = validate_xray_study_screening_provider_result_contract(
        result=provider_result,
        schema_contract_version=XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
        image_receipt=receipt,
        expected_species="cat",
    )
    canonical = canonicalize_xray_study_screening_result(
        provider_result=provider_result,
        schema_contract_version=XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
        image_receipt=receipt,
        expected_species="cat",
    )

    assert validated == provider_before
    assert provider_result == provider_before
    assert canonical["contract_version"] == (XRAY_STUDY_SCREENING_CANONICAL_CONTRACT_V2)
    assert canonical["source_refs"] == [
        {
            "source_ref_id": "source_1",
            "image_id": "image_1",
            "sequence_no": 1,
            "series_id": "series_1",
            "series_manifest_sha256": "1" * 64,
            "projection": "UNKNOWN",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
        },
        {
            "source_ref_id": "source_2",
            "image_id": "image_2",
            "sequence_no": 2,
            "series_id": "series_1",
            "series_manifest_sha256": "1" * 64,
            "projection": "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
        },
    ]
    assert canonical["coverage_summary"] == provider_before["coverage_summary"]
    assert canonical["screening_findings"] == provider_before["screening_findings"]


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("duplicate_image", "study_screening_source_ref_invalid"),
        ("unknown_image", "study_screening_source_image_not_sent"),
        ("incomplete_coverage", "study_screening_source_coverage_mismatch"),
        ("unknown_cross_reference", "study_screening_cross_reference_invalid"),
        ("provider_projection_override", "study_screening_source_ref_invalid"),
    ],
)
def test_study_screening_v2_provider_anchor_fail_closed(
    case: str,
    error_code: str,
) -> None:
    from apps.backend.core.ai.study_screening_contract import (
        XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
        XRayStudyScreeningContractError,
        validate_xray_study_screening_provider_result_contract,
    )

    result = _study_screening_provider_v2_result()
    if case == "duplicate_image":
        result["source_refs"][1]["image_id"] = "image_1"
    elif case == "unknown_image":
        result["source_refs"][1]["image_id"] = "image_missing"
    elif case == "incomplete_coverage":
        result["source_refs"] = result["source_refs"][:1]
    elif case == "unknown_cross_reference":
        result["screening_findings"] = [
            {
                "finding_id": "finding_1",
                "family_key": "thoracic",
                "label": "screening signal",
                "description": "requires analysis",
                "screening_disposition": "requires_analysis",
                "source_ref_ids": ["source_missing"],
            }
        ]
    elif case == "provider_projection_override":
        result["source_refs"][0]["projection"] = "DV"
    else:  # pragma: no cover - protects the parametrized fixture itself.
        raise AssertionError(case)

    with pytest.raises(XRayStudyScreeningContractError, match=error_code):
        validate_xray_study_screening_provider_result_contract(
            result=result,
            schema_contract_version=XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
            image_receipt=_study_screening_receipt(),
            expected_species="cat",
        )


def test_study_screening_v2_stage_outputs_canonical_result_and_requires_receipt() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.registry import resolve_stage_handler

    provider_result = _study_screening_provider_v2_result()
    context = StageExecutionContext(
        task=SimpleNamespace(request_snapshot_json={"species": "cat"}),
        stage=SimpleNamespace(stage_key="study_screening"),
    )
    handler = resolve_stage_handler(
        handler_key="study_screening",
        handler_version="v2",
    )

    completed = handler.consume_ai_call(
        context,
        {
            "call_id": "call_v2",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": provider_result,
            "image_receipt_json": _study_screening_receipt(),
        },
    )
    assert completed.status == "completed"
    assert completed.output["source_call_id"] == "call_v2"
    assert completed.output["study_screening_result"]["contract_version"] == (
        "xray-study-screening.v2"
    )
    assert (
        completed.output["study_screening_result"]["source_refs"][0]["projection"]
        == "VD"
    )
    assert provider_result == _study_screening_provider_v2_result()

    failed = handler.consume_ai_call(
        context,
        {
            "call_id": "call_without_receipt",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": provider_result,
        },
    )
    assert failed.status == "failed"
    assert failed.error_code == "study_screening_source_receipt_invalid"
    assert "study_screening_result" not in failed.output


def test_internal_ai_call_responses_include_frozen_image_receipt() -> None:
    from types import SimpleNamespace

    receipt = _study_screening_receipt()
    call = SimpleNamespace(
        id="call_1",
        status="succeeded",
        result_disposition="accepted",
        winner_attempt_id="attempt_1",
        error_code=None,
        parsed_result_json=_study_screening_provider_v2_result(),
        image_receipt_json=receipt,
        rendered_prompt_sha256="1" * 64,
        schema_sha256="2" * 64,
    )
    attempt = SimpleNamespace(id="attempt_1", status="succeeded", error_code=None)

    structured = AIRequestService._structured_call_response(
        call=call,
        attempt=attempt,
        winner=True,
    )
    replayed = AIRequestService._call_response(call)

    assert structured["image_receipt_json"] == receipt
    assert replayed["image_receipt_json"] == receipt
    assert structured["parsed_result_json"] == call.parsed_result_json
    assert replayed["parsed_result_json"] == call.parsed_result_json


def _system_analysis_result() -> dict[str, Any]:
    families = (
        "thoracic",
        "abdominal",
        "axial_orthopedic",
        "appendicular_orthopedic",
        "head_neck",
    )
    systems = []
    for family in families:
        systems.append(
            {
                "family_key": family,
                "assessment_status": "assessed",
                "visible_structures": [f"{family} visible structure"],
                "findings": (
                    [
                        {
                            "finding_id": "finding_thoracic_1",
                            "label": "localized opacity",
                            "description": "A localized opacity requires review.",
                            "certainty": "low",
                            "alternative_explanations": ["positioning effect"],
                            "source_ref_ids": ["source_1"],
                        }
                    ]
                    if family == "thoracic"
                    else []
                ),
                "normal_counterevidence": [
                    {
                        "evidence_id": f"evidence_{family}_1",
                        "description": f"No additional {family} signal identified.",
                        "source_ref_ids": ["source_1", "source_2"],
                    }
                ],
                "limitations": [],
                "source_ref_ids": ["source_1", "source_2"],
            }
        )
    return {
        "contract_version": "xray-system-analysis.v1",
        "species": "cat",
        "systems": systems,
        "cross_system_patterns": [],
        "unresolved_conflicts": [],
        "source_refs": [
            {"source_ref_id": "source_1", "image_id": "image_1"},
            {"source_ref_id": "source_2", "image_id": "image_2"},
        ],
    }


def test_system_analysis_task_type_uses_quality_bound_isolated_config() -> None:
    from types import SimpleNamespace

    from apps.backend.core.imaging.xray_contract import (
        XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
        requires_exact_xray_five_image_config_contract,
        requires_xray_runtime_image_contract,
    )
    from apps.backend.core.pipeline import XRAY_SYSTEM_ANALYSIS_PROFILE_V1
    from apps.backend.schemas.task import TaskCreate
    from apps.backend.services.runtime.service.task_service import TaskService

    payload = TaskCreate(
        study_id="study_1",
        study_revision_id="revision_1",
        request_id="request_system_analysis_1",
        task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
        species="cat",
        quality_review_task_id=" quality_task_1 ",
        trace_id="trace_system_analysis_1",
    )
    assert payload.quality_review_task_id == "quality_task_1"
    with pytest.raises(
        ValidationError,
        match="task_species_required_for_xray_system_analysis",
    ):
        TaskCreate(
            study_id="study_1",
            study_revision_id="revision_1",
            request_id="request_system_analysis_2",
            task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
            quality_review_task_id="quality_task_1",
            trace_id="trace_system_analysis_2",
        )

    assert TaskService.TASK_PROFILES[XRAY_SYSTEM_ANALYSIS_TASK_TYPE] == frozenset(
        {XRAY_SYSTEM_ANALYSIS_PROFILE_V1}
    )
    assert (
        TaskService._config_key_for_task(
            task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
            species="cat",
        )
        == "xray_system_analysis_cat"
    )
    TaskService._validate_species_config_binding(
        config=SimpleNamespace(
            config_key="xray_system_analysis_cat",
            prompt_key="xray_cat_system_analysis",
            profile_key=XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
        ),
        task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
        species="cat",
    )
    assert requires_xray_runtime_image_contract(
        modality_type="xray",
        task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
        profile_key=XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
    )
    assert requires_exact_xray_five_image_config_contract(
        modality_type="xray",
        task_type=XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
        profile_key=XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
    )


@pytest.mark.anyio
async def test_system_analysis_stage_uses_frozen_quality_and_consumes_accepted_result() -> (
    None
):
    from types import SimpleNamespace

    from apps.backend.core.imaging.manifest import manifest_sha256
    from apps.backend.services.runtime.stages.contracts import StageExecutionContext
    from apps.backend.services.runtime.stages.xray.system_analysis import (
        SystemAnalysisStageHandler,
    )

    ordered_images = [
        {
            "image_id": f"image_{index}",
            "series_id": "series_1",
            "logical_image_key": f"logical_{index}",
            "image_version_no": 1,
            "sequence_no": index,
            "image_role": "original",
            "image_kind": "instance",
            "file_format": "jpg",
            "projection": "VD" if index == 1 else "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
            "storage_profile": "primary",
            "object_key": f"objects/{index}.jpg",
            "object_version_id": None,
            "sha256": ("a" if index == 1 else "b") * 64,
            "size_bytes": index * 10,
            "content_type": "image/jpeg",
        }
        for index in (1, 2)
    ]
    series_manifest = manifest_sha256(ordered_images).sha256
    study_manifest = manifest_sha256(
        [
            {
                "series_id": "series_1",
                "series_key": "series-key-1",
                "series_no": 1,
                "actual_image_count": 2,
                "manifest_sha256": series_manifest,
            }
        ]
    ).sha256
    quality_result = {
        "contract_version": "xray-image-quality.v1",
        "species": "cat",
        "images": [],
    }
    context = StageExecutionContext(
        task=SimpleNamespace(
            id="task_system_analysis_1",
            request_snapshot_json={
                "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
                "species": "cat",
                "resolved_manifest_sha256": study_manifest,
                "quality_review": {"result": quality_result},
                "series": [
                    {
                        "series_id": "series_1",
                        "series_key": "series-key-1",
                        "series_no": 1,
                        "manifest_contract_version": "series-image-manifest.v2",
                        "manifest_sha256": series_manifest,
                        "actual_image_count": 2,
                        "ordered_images": ordered_images,
                    }
                ],
            },
        ),
        stage=SimpleNamespace(
            stage_key="system_analysis",
            input_json={"study_revision_id": "revision_1"},
        ),
    )
    handler = SystemAnalysisStageHandler()
    plan = await handler.execute(context)
    assert plan.completed_result is None
    assert plan.ai_request is not None
    command = plan.ai_request.prompt_command
    assert command.prompt_kind == "system_analysis"
    assert command.quality_results == quality_result
    assert command.safe_context["task_id"] == "task_system_analysis_1"
    assert command.safe_context["species"] == "cat"
    assert command.safe_context["resolved_manifest_sha256"] == study_manifest
    assert len(command.safe_context["ordered_image_refs"]) == 2

    variables = AIRequestService._v2_safe_variables(
        config=SimpleNamespace(
            prompt_variables_json={
                "contract_version": "prompt-variables.v1",
                "required": [
                    "SAFE_STUDY_CONTEXT_JSON",
                    "QUALITY_RESULTS_JSON",
                    "OUTPUT_SCHEMA_JSON",
                ],
                "optional": [],
            },
            output_schema_json={"type": "object"},
        ),
        prompt_command=command,
    )
    assert variables == {
        "SAFE_STUDY_CONTEXT_JSON": command.safe_context,
        "QUALITY_RESULTS_JSON": quality_result,
        "OUTPUT_SCHEMA_JSON": {"type": "object"},
    }

    result = _system_analysis_result()
    consumed = handler.consume_ai_call(
        context,
        {
            "call_id": "call_system_analysis_1",
            "status": "succeeded",
            "result_disposition": "accepted",
            "parsed_result_json": result,
        },
    )
    assert consumed.status == "completed"
    assert consumed.output == {
        "source_call_id": "call_system_analysis_1",
        "system_analysis_result": result,
    }


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("duplicate_source_id", "system_analysis_source_ref_invalid"),
        ("duplicate_image", "system_analysis_source_ref_invalid"),
        ("unknown_image", "system_analysis_source_image_not_sent"),
        ("incomplete_coverage", "system_analysis_source_coverage_mismatch"),
        ("unknown_nested_source", "system_analysis_cross_reference_invalid"),
        ("missing_family", "system_analysis_family_coverage_invalid"),
        ("duplicate_family", "system_analysis_family_coverage_invalid"),
        ("invalid_not_assessed", "system_analysis_assessment_status_invalid"),
        ("invalid_family_reference", "system_analysis_family_reference_invalid"),
        ("duplicate_item_id", "system_analysis_item_id_invalid"),
    ],
)
def test_system_analysis_validator_fails_closed(
    case: str,
    error_code: str,
) -> None:
    from apps.backend.core.ai.system_analysis_contract import (
        XRAY_SYSTEM_ANALYSIS_CONTRACT_V1,
        XRaySystemAnalysisContractError,
        validate_xray_system_analysis_result_contract,
    )

    result = _system_analysis_result()
    if case == "duplicate_source_id":
        result["source_refs"][1]["source_ref_id"] = "source_1"
    elif case == "duplicate_image":
        result["source_refs"][1]["image_id"] = "image_1"
    elif case == "unknown_image":
        result["source_refs"][1]["image_id"] = "image_missing"
    elif case == "incomplete_coverage":
        result["source_refs"] = result["source_refs"][:1]
    elif case == "unknown_nested_source":
        result["systems"][0]["findings"][0]["source_ref_ids"] = ["source_missing"]
    elif case == "missing_family":
        result["systems"] = result["systems"][:-1]
    elif case == "duplicate_family":
        result["systems"][-1]["family_key"] = "thoracic"
    elif case == "invalid_not_assessed":
        result["systems"][0]["assessment_status"] = "not_assessed"
    elif case == "invalid_family_reference":
        result["cross_system_patterns"] = [
            {
                "pattern_id": "pattern_1",
                "description": "cross-system pattern",
                "interpretation": "requires review",
                "family_keys": ["thoracic", "unknown_family"],
                "source_ref_ids": ["source_1"],
            }
        ]
    elif case == "duplicate_item_id":
        finding = deepcopy(result["systems"][0]["findings"][0])
        result["systems"][0]["findings"].append(finding)
    else:  # pragma: no cover - protects the parametrized fixture itself.
        raise AssertionError(case)

    with pytest.raises(XRaySystemAnalysisContractError, match=error_code):
        validate_xray_system_analysis_result_contract(
            result=result,
            schema_contract_version=XRAY_SYSTEM_ANALYSIS_CONTRACT_V1,
            image_receipt=_study_screening_receipt(),
            expected_species="cat",
        )


@pytest.mark.anyio
async def test_network_dispatches_system_analysis_by_frozen_schema_contract() -> None:
    from apps.backend.core.pipeline import XRAY_SYSTEM_ANALYSIS_PROFILE_V1
    from apps.backend.services.ai_control.service.config_compiler import (
        AIConfigCompiler,
    )

    receipt = _study_screening_receipt()
    result = _system_analysis_result()

    class Signer:
        async def sign(self, **_kwargs):
            return [
                GatewayImageInput(
                    sequence_no=item["sequence_no"],
                    mime_type=item["mime_type"],
                    signed_url=(
                        f"https://bucket.example/{item['image_id']}.jpg?signature=x"
                    ),
                )
                for item in receipt["images"]
            ]

    class Gateway:
        async def chat_completions(self, *_args, **_kwargs):
            return {
                "request_id": "provider-request-system-analysis-1",
                "body": {
                    "choices": [{"message": {"content": json.dumps(result)}}],
                    "model": "provider-model",
                },
            }

    response = await AIRequestService.execute_gateway_attempt_network(
        network_plan=_network_plan(
            response_schema=AIConfigCompiler._output_schema(
                profile_key=XRAY_SYSTEM_ANALYSIS_PROFILE_V1
            ),
            image_count_requested=2,
            image_inputs=tuple(receipt["images"]),
            snapshot_contract_version=TASK_REQUEST_SNAPSHOT_V3,
            xray_image_contract_required=True,
            expected_species="cat",
        ),
        gateway_client=Gateway(),
        image_signer=Signer(),
    )
    assert response["execution"].parsed_result_json == result
    assert response["image_receipt"] == receipt


def test_full_chain_primary_consumes_frozen_quality_screening_and_system_lineage() -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting import PromptContractError
    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.core.imaging.manifest import manifest_sha256
    from apps.backend.core.pipeline import XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
    from apps.backend.services.runtime.stages.xray.prompt_commands import (
        build_primary_ai_request_command,
    )

    quality_result = {"contract_version": "xray-image-quality.v1", "images": []}
    ordered_images = [
        {
            "image_id": f"image_{index}",
            "series_id": "series_1",
            "logical_image_key": f"logical_{index}",
            "image_version_no": 1,
            "sequence_no": index,
            "image_role": "original",
            "image_kind": "instance",
            "file_format": "jpg",
            "projection": "VD" if index == 1 else "Lateral",
            "projection_provenance": {
                "source": "caller_declared",
                "schema_version": "xray-projection.v1",
            },
            "storage_profile": "primary",
            "object_key": f"objects/{index}.jpg",
            "object_version_id": None,
            "sha256": ("a" if index == 1 else "b") * 64,
            "size_bytes": index * 10,
            "content_type": "image/jpeg",
        }
        for index in (1, 2)
    ]
    series_manifest = manifest_sha256(ordered_images).sha256
    frozen_series = [
        {
            "series_id": "series_1",
            "series_key": "series-key-1",
            "series_no": 1,
            "manifest_contract_version": "series-image-manifest.v2",
            "manifest_sha256": series_manifest,
            "actual_image_count": 2,
            "ordered_images": ordered_images,
        }
    ]
    study_manifest = manifest_sha256(
        [
            {
                "series_id": "series_1",
                "series_key": "series-key-1",
                "series_no": 1,
                "actual_image_count": 2,
                "manifest_sha256": series_manifest,
            }
        ]
    ).sha256
    screening_output = {"study_screening_result": {"screening": "accepted"}}
    system_output = {"system_analysis_result": {"analysis": "accepted"}}
    upstream_results = {
        "study_screening": {
            "source_stage_id": "screening_stage_1",
            "source_output_sha256": sha256_json(screening_output),
            "result": screening_output,
        },
        "system_analysis": {
            "source_stage_id": "system_stage_1",
            "source_output_sha256": sha256_json(system_output),
            "result": system_output,
        },
    }
    task = SimpleNamespace(
        id="diagnose_task_1",
        request_snapshot_json={
            "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
            "profile_key": XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
            "species": "cat",
            "quality_review": {"result": quality_result},
            "resolved_manifest_sha256": study_manifest,
            "series": frozen_series,
        },
    )
    stage = SimpleNamespace(
        stage_key="joint_primary_reader",
        input_json={
            "study_revision_id": "revision_1",
            "upstream_results": upstream_results,
        },
    )

    command = build_primary_ai_request_command(task=task, stage=stage)

    assert command.prompt_kind == "primary"
    assert command.quality_results == quality_result
    assert command.safe_context["targeted_focus_options"]["thoracic"] == [
        "lung_pattern",
        "cardiovascular_contour",
    ]
    assert command.study_screening_result == screening_output[
        "study_screening_result"
    ]
    assert command.system_analysis_result == system_output[
        "system_analysis_result"
    ]

    tampered = deepcopy(upstream_results)
    tampered["system_analysis"]["result"]["system_analysis_result"] = {
        "analysis": "tampered"
    }
    stage.input_json["upstream_results"] = tampered
    with pytest.raises(
        PromptContractError,
        match="primary_adjudication_upstream_lineage_invalid",
    ):
        build_primary_ai_request_command(task=task, stage=stage)


def test_report_generation_is_zero_image_and_preserves_frozen_medical_truth() -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.core.ai.report_generation_contract import (
        XRayReportGenerationContractError,
        validate_xray_report_generation_result_contract,
    )
    from apps.backend.core.pipeline import XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
    from apps.backend.services.runtime.stages.xray.prompt_commands import (
        build_report_generation_ai_request_command,
    )

    complete_result = _complete_medical_result_v2()
    decision_output = {
        "medical_status": "produced",
        "complete_medical_result": complete_result,
        "source_call_id": "decision_source_call_1",
    }
    task = SimpleNamespace(
        id="diagnose_task_1",
        request_snapshot_json={
            "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V3,
            "profile_key": XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
            "species": "cat",
            "quality_review": {
                "result": {
                    "contract_version": "xray-image-quality.v1",
                    "images": [],
                }
            },
            "series": [{"actual_image_count": 2}],
        },
    )
    stage = SimpleNamespace(
        stage_key="report_generation",
        input_json={
            "study_revision_id": "revision_1",
            "previous_output": decision_output,
            "previous_output_sha256": sha256_json(decision_output),
        },
    )
    command = build_report_generation_ai_request_command(task=task, stage=stage)

    assert AIRequestService._v2_image_count(task=task, stage=stage) == 0
    AIRequestService._require_xray_image_count(
        config=SimpleNamespace(
            modality_type="xray",
            task_type="diagnose",
            profile_key="xray_report_generation_v1",
        ),
        task=task,
        stage=stage,
        image_count=0,
    )
    assert command.final_medical_result == {
        "source_result_sha256": sha256_json(decision_output),
        "final_medical_result": complete_result,
    }

    provider_result = {
        "result_schema_version": "xray-final-report.v1",
        "source_result_sha256": sha256_json(decision_output),
        "medical_status": complete_result["medical_status"],
        "final_medical_result": deepcopy(complete_result),
        "report": {"summary": "format-only report"},
    }
    accepted = validate_xray_report_generation_result_contract(
        result=provider_result,
        schema_contract_version="xray-final-report.v1",
        expected_source_result_sha256=sha256_json(decision_output),
        expected_final_medical_result=complete_result,
    )
    assert accepted["final_medical_result"] == complete_result

    rewritten = deepcopy(provider_result)
    rewritten["final_medical_result"]["summary"] = "rewritten diagnosis"
    with pytest.raises(
        XRayReportGenerationContractError,
        match="report_generation_medical_result_rewritten",
    ):
        validate_xray_report_generation_result_contract(
            result=rewritten,
            schema_contract_version="xray-final-report.v1",
            expected_source_result_sha256=sha256_json(decision_output),
            expected_final_medical_result=complete_result,
        )


@pytest.mark.anyio
async def test_full_chain_decision_schedules_report_generation_without_early_report(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.ai.prompting.contracts import sha256_json
    from apps.backend.core.pipeline import (
        StageResult,
        XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
        build_default_registry,
        compile_profile_contract,
    )
    from apps.backend.services.runtime.service import imaging_execution_service
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    contract, pipeline_sha = compile_profile_contract(
        XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
        build_default_registry(),
    )
    task = SimpleNamespace(
        id="diagnose_task_1",
        study_revision_id="revision_1",
        compiled_pipeline_sha256=pipeline_sha,
        attempt_no=1,
        state_version=9,
        trace_id="trace_1",
        cancel_requested_at=None,
        execution_status="running",
        request_snapshot_json={
            "profile_key": XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
            "resolved_manifest_sha256": "a" * 64,
            "compiled_profile": contract,
        },
    )
    stage = SimpleNamespace(
        id="decision_stage_1",
        task_id=task.id,
        stage_key="decision_finalization",
        stage_no=7,
        state_version=3,
        lease_generation=1,
        input_json={"upstream_results": {}},
    )
    output = {
        "medical_status": "produced",
        "complete_medical_result": _complete_medical_result_v2(),
        "source_call_id": "primary_call_1",
    }
    captured: dict[str, Any] = {}

    class FakeStageDal:
        async def finish_with_lease(self, **kwargs):
            return SimpleNamespace(**{**stage.__dict__, **kwargs["values"]})

        async def create_idempotent(self, values):
            captured["next_stage"] = values
            return SimpleNamespace(**values)

    class FakeOutboxDal:
        async def create_idempotent(self, values):
            captured["event"] = values
            return SimpleNamespace(**values)

    class FakeTaskDal:
        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    class RejectReportService:
        def __init__(self, _db):
            raise AssertionError("DecisionFinalization must not persist the report")

    monkeypatch.setattr(
        imaging_execution_service,
        "ReportService",
        RejectReportService,
    )
    service = object.__new__(ImagingExecutionService)
    service.stage_dal = FakeStageDal()
    service.outbox_dal = FakeOutboxDal()
    service.task_dal = FakeTaskDal()

    result = await service._apply_stage_result(
        task=task,
        stage=stage,
        owner_id="worker_1",
        result=StageResult(status="completed", output=output),
    )

    assert result == output
    assert captured["next_stage"]["stage_key"] == "report_generation"
    assert captured["next_stage"]["handler_version"] == "v1"
    assert captured["next_stage"]["input_json"]["previous_output"] == output
    assert captured["next_stage"]["input_json"]["previous_output_sha256"] == (
        sha256_json(output)
    )
    assert captured["next_stage"]["input_json"]["upstream_results"][
        "decision_finalization"
    ]["source_output_sha256"] == sha256_json(output)
    assert captured["task_values"] == {
        "execution_status": "queued",
        "ai_medical_status": "not_produced",
    }


@pytest.mark.anyio
async def test_report_generation_acceptance_persists_one_report_and_failure_persists_none(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from apps.backend.core.pipeline import StageResult, XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
    from apps.backend.services.runtime.service import imaging_execution_service
    from apps.backend.services.runtime.service.imaging_execution_service import (
        ImagingExecutionService,
    )

    complete_result = _complete_medical_result_v2()
    task = SimpleNamespace(
        id="diagnose_task_1",
        state_version=11,
        cancel_requested_at=None,
        execution_status="running",
        request_snapshot_json={"profile_key": XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1},
    )
    stage = SimpleNamespace(
        id="report_stage_1",
        task_id=task.id,
        stage_key="report_generation",
        state_version=4,
        lease_generation=2,
        input_json={},
    )
    accepted_output = {
        "source_call_id": "report_call_1",
        "medical_status": "produced",
        "complete_medical_result": complete_result,
        "report_generation_result": {
            "result_schema_version": "xray-final-report.v1",
            "final_medical_result": deepcopy(complete_result),
        },
    }
    captured: dict[str, Any] = {"reports": []}

    class FakeStageDal:
        async def finish_with_lease(self, **kwargs):
            captured["stage_values"] = kwargs["values"]
            return SimpleNamespace(**{**stage.__dict__, **kwargs["values"]})

    class FakeTaskDal:
        async def get_by_id_for_update(self, task_id):
            assert task_id == task.id
            return task

        async def cas_update(self, **kwargs):
            captured["task_values"] = kwargs["values"]
            return SimpleNamespace(**{**task.__dict__, **kwargs["values"]})

    class FakeReportService:
        def __init__(self, db):
            assert db == "db"

        async def finalize(self, **kwargs):
            captured["reports"].append(kwargs)
            return SimpleNamespace(id="report_1")

    monkeypatch.setattr(
        imaging_execution_service,
        "ReportService",
        FakeReportService,
    )
    service = object.__new__(ImagingExecutionService)
    service.outbox_dal = SimpleNamespace(db="db")
    service.stage_dal = FakeStageDal()
    service.task_dal = FakeTaskDal()

    result = await service._apply_stage_result(
        task=task,
        stage=stage,
        owner_id="worker_1",
        result=StageResult(status="completed", output=accepted_output),
    )

    assert result == accepted_output
    assert len(captured["reports"]) == 1
    assert captured["reports"][0]["finalization_stage_id"] == stage.id
    assert captured["reports"][0]["source_call_id"] == "report_call_1"
    assert (
        captured["reports"][0]["content"]["complete_medical_result"]
        == complete_result
    )

    captured["reports"].clear()
    failed_output = {"source_call_id": "report_call_2", "error_code": "provider_500"}
    failed = await service._apply_stage_result(
        task=task,
        stage=stage,
        owner_id="worker_1",
        result=StageResult(
            status="failed",
            output=failed_output,
            error_code="provider_500",
        ),
    )

    assert failed == failed_output
    assert captured["reports"] == []
    assert captured["task_values"]["execution_status"] == "failed"
    assert captured["task_values"]["ai_medical_status"] == "not_produced"
