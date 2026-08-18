"""Secret-free, signed proof emitted at the controlled HTTP egress boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any


EGRESS_PROOF_SCHEMA = "adapter-egress-proof.v1"
EGRESS_PROOF_ISSUER = "ms-image-egress-adapter.v1"
EGRESS_PROOF_SIGNATURE_ALGORITHM = "hmac-sha256"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_TRANSPORT_STATES = frozenset({"qualified", "provider_error"})


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_unsigned(proof: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in proof.items() if key != "proof_signature"}
    return json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _signature(proof: dict[str, Any], signing_key: str) -> str:
    return hmac.new(
        signing_key.encode("utf-8"), _canonical_unsigned(proof), hashlib.sha256
    ).hexdigest()


def build_adapter_egress_proof(
    *,
    signing_key: str,
    transport_status: str,
    endpoint_sha256: str,
    key_fingerprint: str,
    requested_model: str,
    prompt_sha256: str,
    rendered_sha256: str,
    schema_sha256: str,
    request_nonce_sha256: str,
    image_ordered_sha256: str | None,
    images: list[dict[str, Any]],
    http_status: int,
    provider_request_id_sha256: str | None,
    actual_model: str | None,
    response_body_sha256: str,
    usage: dict[str, int] | None,
    finish_reason: str | None,
    latency_ms: int,
) -> dict[str, Any]:
    """Build a strictly bounded proof without endpoint, key, prompt or bytes."""

    if not signing_key:
        raise ValueError("egress_proof_signing_key_missing")
    proof: dict[str, Any] = {
        "schema": EGRESS_PROOF_SCHEMA,
        "proof_issuer": EGRESS_PROOF_ISSUER,
        "transport_status": transport_status,
        "endpoint_sha256": endpoint_sha256,
        "key_fingerprint": key_fingerprint,
        "requested_model": requested_model,
        "requested_model_sha256": sha256_text(requested_model),
        "prompt_sha256": prompt_sha256,
        "rendered_sha256": rendered_sha256,
        "schema_sha256": schema_sha256,
        "request_nonce_sha256": request_nonce_sha256,
        "image_count": len(images),
        "image_ordered_sha256": image_ordered_sha256,
        "images": [
            {
                "source_index": item["source_index"],
                "sent_sha256": item["sent_sha256"],
            }
            for item in images
        ],
        "http_status": http_status,
        "provider_request_id_sha256": provider_request_id_sha256,
        "actual_model": actual_model,
        "response_body_sha256": response_body_sha256,
        "usage": usage,
        "finish_reason": (finish_reason or "unknown")[:64],
        "latency_ms": max(0, int(latency_ms)),
        "medical_verdict_produced": False,
    }
    proof["proof_signature"] = {
        "algorithm": EGRESS_PROOF_SIGNATURE_ALGORITHM,
        "value": _signature(proof, signing_key),
    }
    return proof


def adapter_egress_proof_is_valid(
    proof: Any,
    *,
    signing_key: str,
    expected_transport_status: str | None = None,
    expected_endpoint_sha256: str | None = None,
    expected_key_fingerprint: str | None = None,
    expected_model: str | None = None,
    expected_prompt_sha256: str | None = None,
    expected_rendered_sha256: str | None = None,
    expected_schema_sha256: str | None = None,
    expected_request_nonce_sha256: str | None = None,
    expected_image_ordered_sha256: str | None = None,
    expected_images: list[dict[str, Any]] | None = None,
) -> bool:
    """Verify signature, shape and optional request bindings fail-closed."""

    if not signing_key or not isinstance(proof, dict):
        return False
    allowed_keys = {
        "schema",
        "proof_issuer",
        "transport_status",
        "endpoint_sha256",
        "key_fingerprint",
        "requested_model",
        "requested_model_sha256",
        "prompt_sha256",
        "rendered_sha256",
        "schema_sha256",
        "request_nonce_sha256",
        "image_count",
        "image_ordered_sha256",
        "images",
        "http_status",
        "provider_request_id_sha256",
        "actual_model",
        "response_body_sha256",
        "usage",
        "finish_reason",
        "latency_ms",
        "medical_verdict_produced",
        "proof_signature",
    }
    if set(proof) != allowed_keys:
        return False
    signature = proof.get("proof_signature")
    if (
        proof.get("schema") != EGRESS_PROOF_SCHEMA
        or proof.get("proof_issuer") != EGRESS_PROOF_ISSUER
        or proof.get("transport_status") not in _TRANSPORT_STATES
        or proof.get("medical_verdict_produced") is not False
        or not isinstance(signature, dict)
        or signature.get("algorithm") != EGRESS_PROOF_SIGNATURE_ALGORITHM
        or not isinstance(signature.get("value"), str)
        or _SHA256.fullmatch(signature["value"]) is None
        or not hmac.compare_digest(signature["value"], _signature(proof, signing_key))
    ):
        return False
    sha_fields = (
        "endpoint_sha256",
        "key_fingerprint",
        "requested_model_sha256",
        "prompt_sha256",
        "rendered_sha256",
        "schema_sha256",
        "request_nonce_sha256",
        "response_body_sha256",
    )
    if any(_SHA256.fullmatch(str(proof.get(key) or "")) is None for key in sha_fields):
        return False
    optional_sha_fields = ("image_ordered_sha256", "provider_request_id_sha256")
    if any(
        value is not None and _SHA256.fullmatch(str(value)) is None
        for value in (proof.get(key) for key in optional_sha_fields)
    ):
        return False
    if proof.get("requested_model_sha256") != sha256_text(str(proof.get("requested_model") or "")):
        return False
    images = proof.get("images")
    if (
        not isinstance(images, list)
        or type(proof.get("image_count")) is not int
        or proof["image_count"] != len(images)
        or proof["image_count"] > 512
        or type(proof.get("http_status")) is not int
        or not 100 <= proof["http_status"] <= 599
        or type(proof.get("latency_ms")) is not int
        or proof["latency_ms"] < 0
    ):
        return False
    normalized_images: list[dict[str, Any]] = []
    for expected_index, item in enumerate(images):
        if (
            not isinstance(item, dict)
            or set(item) != {"source_index", "sent_sha256"}
            or item.get("source_index") != expected_index
            or _SHA256.fullmatch(str(item.get("sent_sha256") or "")) is None
        ):
            return False
        normalized_images.append(dict(item))
    if proof["image_count"]:
        from .contracts import ordered_image_identity_sha256

        computed = ordered_image_identity_sha256(
            (item["source_index"], item["sent_sha256"]) for item in normalized_images
        )
        if proof.get("image_ordered_sha256") != computed:
            return False
    elif proof.get("image_ordered_sha256") is not None:
        return False
    usage = proof.get("usage")
    if usage is not None and (
        not isinstance(usage, dict)
        or any(
            key not in {
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "input_tokens",
                "output_tokens",
            }
            or not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 10**9
            for key, value in usage.items()
        )
    ):
        return False
    exact = {
        "transport_status": expected_transport_status,
        "endpoint_sha256": expected_endpoint_sha256,
        "key_fingerprint": expected_key_fingerprint,
        "requested_model": expected_model,
        "prompt_sha256": expected_prompt_sha256,
        "rendered_sha256": expected_rendered_sha256,
        "schema_sha256": expected_schema_sha256,
        "request_nonce_sha256": expected_request_nonce_sha256,
        "image_ordered_sha256": expected_image_ordered_sha256,
    }
    if any(expected is not None and proof.get(key) != expected for key, expected in exact.items()):
        return False
    if expected_images is not None and normalized_images != expected_images:
        return False
    if proof["transport_status"] == "qualified" and (
        not 200 <= proof["http_status"] < 300
        or not proof.get("provider_request_id_sha256")
        or not isinstance(proof.get("actual_model"), str)
        or not proof["actual_model"].strip()
    ):
        return False
    return True


__all__ = [
    "EGRESS_PROOF_ISSUER",
    "EGRESS_PROOF_SCHEMA",
    "adapter_egress_proof_is_valid",
    "build_adapter_egress_proof",
    "canonical_json_sha256",
    "sha256_text",
]
