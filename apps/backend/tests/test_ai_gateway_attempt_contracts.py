"""Offline Gateway adapter and Attempt request contracts (no real network)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    GatewayImageInput,
    GatewayRejectedError,
    GatewayRequest,
    GatewayUnknownDeliveryError,
    normalize_gateway_profile,
    response_sha256,
    schema_validate_result,
    validate_signed_image_url,
)
from apps.backend.core.ai.gateway_client import GatewayClient
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


@pytest.fixture
def anyio_backend() -> str:
    """Run async Gateway tests on the asyncio backend only."""
    return "asyncio"


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
        "response_schema": SCHEMA,
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
async def test_ai_request_network_builds_strict_payload_and_persists_only_audit_facts() -> None:
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
    assert captured["payload"]["strategy"] == "single"
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

    with pytest.raises(GatewayRejectedError, match="provider_http_401"):
        await AIRequestService.execute_gateway_attempt_network(
            network_plan=_network_plan(),
            gateway_client=FakeGateway(),
            image_signer=FakeSigner(),
        )


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
    from apps.backend.core.pipeline import build_default_registry, compile_profile_contract

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

    assert calls == [
        ("head_object", "image/image_1/1/source.dcm")
    ]
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
                    "choices": [
                        {"message": {"content": json.dumps({"result": "ok"})}}
                    ],
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
    assert (
        await dal.claim_reconcile_candidate(
            attempt_id="attempt_due",
            expected_version=7,
            now=now,
            lease_expires_at=lease_expires_at,
        )
        is None
    )
    claim = captured["claim"]
    assert claim["data_id"] == "attempt_due"
    assert claim["expected_version"] == 7
    assert claim["data"] == {"next_reconcile_at": lease_expires_at}
    claim_where = claim["v_where"]
    assert claim_where[0].right.value == "unknown"
    assert claim_where[1].operator is operators.is_not
    assert claim_where[2].operator is operators.le
    assert claim_where[2].right.value == now


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
    }
    calls: list[str] = []

    async def list_due(self, **kwargs):
        calls.append("list")
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
    ).run_once(limit=10, lease_seconds=120, retry_seconds=300)

    assert outcomes["claimed"] == 1
    assert outcomes[expected_counter] == 1
    assert outcomes["stage_pending"] == expected_stage_pending
    if lookup_status in {"unknown", "unsupported"}:
        assert calls == ["list", "claim", "lookup", "reschedule"]
    else:
        assert calls == ["list", "claim", "lookup", "apply"]


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
    ).run_once(limit=10, lease_seconds=120, retry_seconds=300)
    assert outcomes["claimed"] == 0
    assert outcomes["conflicted"] == 1


@pytest.mark.anyio
async def test_ai_attempt_reconcile_rejects_incomplete_success() -> None:
    from datetime import datetime

    from apps.backend.core.ai.gateway.attempt_lookup import AttemptLookupResult
    from apps.backend.services.runtime.service.ai_attempt_reconcile_service import (
        AIAttemptReconcileError,
        AIAttemptReconcileService,
    )

    service = object.__new__(AIAttemptReconcileService)
    with pytest.raises(AIAttemptReconcileError, match="ai_attempt_lookup_result_invalid"):
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
async def test_ai_attempt_reconcile_repeated_success_does_not_refinalize_stage() -> None:
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
async def test_xray_family_routing_only_returns_primary_final_and_preserves_primary_result() -> None:
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
async def test_ai_request_rejects_cancelled_task_before_call_or_retry_creation() -> None:
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
async def test_late_attempt_success_is_audited_but_cannot_win_cancelled_task() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from apps.backend.services.runtime.service.ai_request_service import AIRequestService

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
    content_sha = __import__("hashlib").sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
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
