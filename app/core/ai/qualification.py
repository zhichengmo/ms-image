"""Safe helpers for one-shot real Provider image qualification."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import struct
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from PIL import Image
from io import BytesIO

from .contracts import (
    ProviderImageInput,
    ordered_image_identity_sha256,
    ordered_image_sha256,
    sha256_bytes,
)
from .egress_proof import adapter_egress_proof_is_valid


MAX_QUALIFICATION_IMAGES = 16
MAX_QUALIFICATION_IMAGE_BYTES = 20 * 1024 * 1024
MAX_QUALIFICATION_TOTAL_BYTES = 64 * 1024 * 1024
ARTIFACT_SIGNATURE_ALGORITHM = "hmac-sha256"


def load_qualification_images(paths: Iterable[str]) -> tuple[ProviderImageInput, ...]:
    """Load operator-approved local images without exposing filesystem paths."""
    normalized = [Path(item).expanduser().resolve() for item in paths if item.strip()]
    if not normalized:
        raise ValueError("qualification_images_not_configured")
    if len(normalized) > MAX_QUALIFICATION_IMAGES:
        raise ValueError("qualification_image_count_exceeded")

    images: list[ProviderImageInput] = []
    total_bytes = 0
    for source_index, path in enumerate(normalized):
        if not path.is_file():
            raise ValueError("qualification_image_unavailable")
        content = path.read_bytes()
        if not content or len(content) > MAX_QUALIFICATION_IMAGE_BYTES:
            raise ValueError("qualification_image_size_invalid")
        total_bytes += len(content)
        if total_bytes > MAX_QUALIFICATION_TOTAL_BYTES:
            raise ValueError("qualification_total_image_size_exceeded")
        mime_type, width, height = _image_metadata(content)
        digest = sha256_bytes(content)
        images.append(
            ProviderImageInput(
                source_index=source_index,
                source_image_ref=f"qualification-image-{source_index}-{digest[:16]}",
                mime_type=mime_type,
                content=content,
                pixel_width=width,
                pixel_height=height,
                sent_sha256=digest,
            )
        )
    return tuple(images)


def qualification_fingerprint(
    *,
    provider_kind: str,
    base_url: str,
    model: str,
    key_fingerprint: str,
    prompt_checksum: str,
    schema_checksum: str,
    images: tuple[ProviderImageInput, ...],
) -> str:
    payload = {
        "provider_kind": provider_kind,
        "endpoint_sha256": hashlib.sha256(base_url.encode("utf-8")).hexdigest(),
        "model": model,
        "key_fingerprint": key_fingerprint,
        "prompt_checksum": prompt_checksum,
        "schema_checksum": schema_checksum,
        "image_count": len(images),
        "image_ordered_sha256": ordered_image_sha256(images),
        "receipt_contract": "provider-image-receipt.v1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def secret_fingerprint(secret: str) -> str:
    """Return a stable key fingerprint without returning the secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def endpoint_fingerprint(base_url: str) -> str:
    return hashlib.sha256(base_url.encode("utf-8")).hexdigest()


def openai_compatible_endpoint_fingerprint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    endpoint = (
        normalized
        if normalized.endswith("/chat/completions")
        else f"{normalized}/chat/completions"
    )
    return endpoint_fingerprint(endpoint)


def safe_image_manifest(images: tuple[ProviderImageInput, ...]) -> list[dict[str, Any]]:
    return [image.receipt_identity() for image in images]


def safe_provider_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Project a Provider receipt to an artifact-safe, bounded shape."""
    result: dict[str, Any] = {
        "receipt_capability_version": receipt.get("receipt_capability_version"),
        "actual_model": receipt.get("actual_model"),
        "status": receipt.get("status"),
        "full_sent": receipt.get("full_sent"),
        "image_count_received": receipt.get("image_count_received"),
        "image_ordered_sha256": receipt.get("image_ordered_sha256"),
        "request_nonce_sha256": receipt.get("request_nonce_sha256"),
        "received_at": receipt.get("received_at"),
        "receipt_signature_verified": receipt.get("receipt_signature_verified"),
    }
    provider_request_id_sha256 = receipt.get("provider_request_id_sha256")
    if (
        isinstance(provider_request_id_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", provider_request_id_sha256)
    ):
        result["provider_request_id_sha256"] = provider_request_id_sha256
    else:
        provider_request_id = receipt.get("provider_request_id")
        if isinstance(provider_request_id, str) and provider_request_id:
            result["provider_request_id_sha256"] = hashlib.sha256(
                provider_request_id.encode("utf-8")
            ).hexdigest()
    receipts = receipt.get("image_receipts")
    if isinstance(receipts, list):
        result["image_receipts"] = [
            {
                "source_index": item.get("source_index"),
                "sent_sha256": item.get("sent_sha256"),
                "status": item.get("status"),
            }
            for item in receipts[:MAX_QUALIFICATION_IMAGES]
            if isinstance(item, dict)
        ]
    usage = receipt.get("usage")
    if isinstance(usage, dict):
        result["usage"] = {
            key: value
            for key, value in usage.items()
            if key in {
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "input_tokens",
                "output_tokens",
            }
            and isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= 10**9
        }
    proof = receipt.get("adapter_egress_proof")
    if isinstance(proof, dict):
        # The proof is already an allowlisted, signed projection. Copy only
        # its bounded evidence; never copy request payloads or provider text.
        result["adapter_egress_proof"] = proof
    return result


def _canonical_unsigned_artifact(artifact: dict[str, Any]) -> bytes:
    unsigned = {
        key: value for key, value in artifact.items() if key != "artifact_signature"
    }
    return json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _artifact_signature(artifact: dict[str, Any], signing_key: str) -> str:
    return hmac.new(
        signing_key.encode("utf-8"),
        _canonical_unsigned_artifact(artifact),
        hashlib.sha256,
    ).hexdigest()


def write_qualification_artifact(
    path: str | Path,
    artifact: dict[str, Any],
    *,
    signing_key: str = "",
) -> None:
    payload = dict(artifact)
    if signing_key:
        payload["artifact_signature"] = {
            "algorithm": ARTIFACT_SIGNATURE_ALGORITHM,
            "value": _artifact_signature(payload, signing_key),
        }
    elif payload.get("status") == "qualified":
        raise ValueError("qualification_artifact_signing_key_missing")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        target.chmod(0o600)
    except OSError:
        # Artifact creation must remain portable; deployment can enforce the
        # directory policy when chmod is unavailable.
        pass


def artifact_signature_is_valid(artifact: Any, *, signing_key: str) -> bool:
    """Check only the envelope signature; this does not grant readiness."""
    if not signing_key or not isinstance(artifact, dict):
        return False
    signature = artifact.get("artifact_signature")
    return bool(
        isinstance(signature, dict)
        and signature.get("algorithm") == ARTIFACT_SIGNATURE_ALGORITHM
        and isinstance(signature.get("value"), str)
        and re.fullmatch(r"[0-9a-f]{64}", signature["value"])
        and hmac.compare_digest(
            signature["value"], _artifact_signature(artifact, signing_key)
        )
    )


def qualification_artifact_is_current(
    path: str | Path,
    *,
    base_url: str,
    model: str,
    api_key: str,
    api_keys: tuple[str, ...] | None = None,
    prompt_key: str | None = None,
    prompt_version: str | None = None,
    prompt_checksum: str | None = None,
    schema_key: str | None = None,
    schema_checksum: str | None = None,
    signing_key: str = "",
) -> bool:
    """Require a matching, successful artifact before enabling real calls."""
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        provider = artifact["provider"]
        receipt = artifact["receipt"]
        images = artifact["images"]
        manifest = images["manifest"]
        if artifact.get("schema") != "ai-provider-qualification.v1":
            return False
        if artifact.get("status") != "qualified":
            return False
        signature = artifact.get("artifact_signature")
        if (
            not signing_key
            or not isinstance(signature, dict)
            or signature.get("algorithm") != ARTIFACT_SIGNATURE_ALGORITHM
            or not isinstance(signature.get("value"), str)
            or not hmac.compare_digest(
                signature["value"], _artifact_signature(artifact, signing_key)
            )
        ):
            return False
        if provider.get("endpoint_sha256") != endpoint_fingerprint(base_url):
            return False
        valid_key_fingerprints = {
            secret_fingerprint(item)
            for item in (api_keys or (api_key,))
            if isinstance(item, str) and item
        }
        if provider.get("model") != model or provider.get("key_fingerprint") not in valid_key_fingerprints:
            return False
        if provider.get("actual_model") != model:
            return False
        prompt = artifact.get("prompt")
        if any(value is not None for value in (prompt_key, prompt_version, prompt_checksum)):
            if not isinstance(prompt, dict):
                return False
            if (
                prompt.get("prompt_key") != prompt_key
                or prompt.get("prompt_version") != prompt_version
                or prompt.get("prompt_checksum") != prompt_checksum
            ):
                return False
        if any(value is not None for value in (schema_key, schema_checksum)):
            if not isinstance(prompt, dict):
                return False
            if prompt.get("schema_key") != schema_key or prompt.get("schema_sha256") != schema_checksum:
                return False
        if receipt.get("receipt_capability_version") != "provider-image-receipt.v1":
            return False
        if receipt.get("status") != "confirmed":
            return False
        if receipt.get("full_sent") != "confirmed":
            return False
        if receipt.get("receipt_signature_verified") is not True:
            return False
        if not isinstance(receipt.get("received_at"), str) or not receipt["received_at"].strip():
            return False
        if re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("request_nonce_sha256") or "")) is None:
            return False
        if re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("provider_request_id_sha256") or "")) is None:
            return False
        image_count = receipt.get("image_count_received")
        image_receipts = receipt.get("image_receipts")
        ordered_sha = images.get("ordered_sha256")
        if (
            not isinstance(manifest, list)
            or len(manifest) > MAX_QUALIFICATION_IMAGES
            or type(images.get("count")) is not int
            or images.get("count") != len(manifest)
        ):
            return False
        if not isinstance(image_receipts, list):
            return False
        expected: list[tuple[int, str]] = []
        for expected_index, item in enumerate(manifest):
            if not isinstance(item, dict):
                return False
            source_index = item.get("source_index")
            sent_sha256 = item.get("sent_sha256")
            if (
                type(source_index) is not int
                or source_index != expected_index
                or not isinstance(sent_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", sent_sha256) is None
            ):
                return False
            expected.append((source_index, sent_sha256))
        received: list[tuple[int, str]] = []
        for expected_index, item in enumerate(image_receipts):
            if not isinstance(item, dict) or item.get("status") != "confirmed":
                return False
            source_index = item.get("source_index")
            sent_sha256 = item.get("sent_sha256")
            if (
                type(source_index) is not int
                or source_index != expected_index
                or not isinstance(sent_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", sent_sha256) is None
            ):
                return False
            received.append((source_index, sent_sha256))
        computed_ordered_sha = ordered_image_identity_sha256(expected)
        qualification_payload = {
            "provider_kind": provider.get("kind"),
            "endpoint_sha256": endpoint_fingerprint(base_url),
            "model": model,
            "key_fingerprint": provider.get("key_fingerprint"),
            "prompt_checksum": prompt.get("prompt_checksum") if isinstance(prompt, dict) else None,
            "schema_checksum": prompt.get("schema_sha256") if isinstance(prompt, dict) else None,
            "image_count": images.get("count"),
            "image_ordered_sha256": ordered_sha,
            "receipt_contract": "provider-image-receipt.v1",
        }
        expected_qualification_fingerprint = hashlib.sha256(
            json.dumps(
                qualification_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return (
            type(image_count) is int
            and image_count > 0
            and len(image_receipts) == image_count
            and image_count == len(manifest)
            and isinstance(ordered_sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", ordered_sha) is not None
            and computed_ordered_sha == ordered_sha
            and receipt.get("image_ordered_sha256") == ordered_sha
            and received == expected
            and artifact.get("qualification_fingerprint")
            == expected_qualification_fingerprint
            and urlsplit(base_url).scheme == "https"
            and bool(urlsplit(base_url).netloc)
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return False


def transport_qualification_artifact_is_current(
    path: str | Path,
    *,
    base_url: str,
    model: str,
    api_key: str,
    api_keys: tuple[str, ...] | None = None,
    prompt_key: str | None = None,
    prompt_version: str | None = None,
    prompt_checksum: str | None = None,
    schema_key: str | None = None,
    schema_checksum: str | None = None,
    artifact_signing_key: str = "",
    egress_signing_key: str = "",
) -> bool:
    """Verify G1-T without promoting Provider receipt or medical readiness."""

    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            artifact.get("schema")
            != "ai-provider-transport-qualification.v1"
            or artifact.get("status") != "qualified"
            or artifact.get("transport_status") != "qualified"
            or artifact.get("coverage_status") != "egress_proven"
            or artifact.get("receipt_status") not in {"unsupported", "qualified"}
            or artifact.get("medical_verdict_produced") is not False
        ):
            return False
        signature = artifact.get("artifact_signature")
        if (
            not artifact_signing_key
            or not isinstance(signature, dict)
            or signature.get("algorithm") != ARTIFACT_SIGNATURE_ALGORITHM
            or not isinstance(signature.get("value"), str)
            or not hmac.compare_digest(
                signature["value"],
                _artifact_signature(artifact, artifact_signing_key),
            )
        ):
            return False
        provider = artifact.get("provider")
        prompt = artifact.get("prompt")
        images = artifact.get("images")
        if not all(isinstance(item, dict) for item in (provider, prompt, images)):
            return False
        valid_key_fingerprints = {
            secret_fingerprint(item)
            for item in (api_keys or (api_key,))
            if isinstance(item, str) and item
        }
        endpoint_sha256 = openai_compatible_endpoint_fingerprint(base_url)
        if (
            provider.get("endpoint_sha256") != endpoint_sha256
            or provider.get("model") != model
            or provider.get("actual_model") != model
            or provider.get("key_fingerprint") not in valid_key_fingerprints
        ):
            return False
        if any(value is not None for value in (prompt_key, prompt_version, prompt_checksum)) and (
            prompt.get("prompt_key") != prompt_key
            or prompt.get("prompt_version") != prompt_version
            or prompt.get("prompt_checksum") != prompt_checksum
        ):
            return False
        if any(value is not None for value in (schema_key, schema_checksum)) and (
            prompt.get("schema_key") != schema_key
            or prompt.get("schema_sha256") != schema_checksum
        ):
            return False
        manifest = images.get("manifest")
        if (
            not isinstance(manifest, list)
            or not manifest
            or len(manifest) > MAX_QUALIFICATION_IMAGES
            or images.get("count") != len(manifest)
        ):
            return False
        normalized_manifest: list[dict[str, Any]] = []
        expected_identities: list[tuple[int, str]] = []
        for expected_index, item in enumerate(manifest):
            if (
                not isinstance(item, dict)
                or set(item) != {"source_index", "sent_sha256"}
                or item.get("source_index") != expected_index
                or re.fullmatch(r"[0-9a-f]{64}", str(item.get("sent_sha256") or "")) is None
            ):
                return False
            normalized_manifest.append(dict(item))
            expected_identities.append((expected_index, item["sent_sha256"]))
        ordered_sha = ordered_image_identity_sha256(expected_identities)
        if images.get("ordered_sha256") != ordered_sha:
            return False
        proof = artifact.get("adapter_egress_proof")
        if not adapter_egress_proof_is_valid(
            proof,
            signing_key=egress_signing_key,
            expected_transport_status="qualified",
            expected_endpoint_sha256=endpoint_sha256,
            expected_key_fingerprint=provider.get("key_fingerprint"),
            expected_model=model,
            expected_prompt_sha256=prompt.get("prompt_checksum"),
            expected_rendered_sha256=prompt.get("rendered_sha256"),
            expected_schema_sha256=prompt.get("schema_sha256"),
            expected_image_ordered_sha256=ordered_sha,
            expected_images=normalized_manifest,
        ):
            return False
        return (
            proof.get("actual_model") == model
            and proof.get("provider_request_id_sha256")
            == provider.get("provider_request_id_sha256")
            and proof.get("medical_verdict_produced") is False
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return False


def _image_metadata(content: bytes) -> tuple[str, int, int]:
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        width, height = struct.unpack(">II", content[16:24])
        if width > 0 and height > 0:
            return "image/png", width, height
    if content.startswith(b"\xff\xd8"):
        dimensions = _jpeg_dimensions(content)
        if dimensions is not None:
            return "image/jpeg", dimensions[0], dimensions[1]
    # Keep qualification and runtime image contracts aligned.  Pillow gives
    # us bounded format validation for WebP/GIF/BMP without persisting bytes.
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            mime_type = Image.MIME.get(image.format, "").casefold()
            if mime_type in {"image/webp", "image/gif", "image/bmp"}:
                width, height = int(image.width), int(image.height)
                if width > 0 and height > 0:
                    return mime_type, width, height
    except Exception:  # noqa: BLE001 - map all decoder failures to stable class
        pass
    raise ValueError("qualification_image_format_not_supported")


def _jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    index = 2
    while index + 9 < len(content):
        if content[index] != 0xFF:
            index += 1
            continue
        marker = content[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(content):
            return None
        segment_length = int.from_bytes(content[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(content):
            return None
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }:
            height = int.from_bytes(content[index + 3:index + 5], "big")
            width = int.from_bytes(content[index + 5:index + 7], "big")
            if width > 0 and height > 0:
                return width, height
            return None
        index += segment_length
    return None


__all__ = [
    "ARTIFACT_SIGNATURE_ALGORITHM",
    "artifact_signature_is_valid",
    "load_qualification_images",
    "endpoint_fingerprint",
    "openai_compatible_endpoint_fingerprint",
    "qualification_fingerprint",
    "safe_image_manifest",
    "safe_provider_receipt",
    "qualification_artifact_is_current",
    "transport_qualification_artifact_is_current",
    "secret_fingerprint",
    "write_qualification_artifact",
]
