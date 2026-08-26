"""Short-lived OSS image URL signing boundary for AI Gateway attempts."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from urllib.parse import urlsplit

from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    GatewayImageInput,
    validate_signed_image_url,
)
from apps.backend.core.config import Settings, settings
from apps.backend.core.imaging.object_store import (
    OSSObjectStore,
    ObjectStorageGateway,
    ObjectStoreError,
)

_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_IMAGE_MIME = {"application/dicom", "image/jpeg", "image/png"}


class ImageSigningError(RuntimeError):
    """An Attempt image cannot be signed into a short-lived HTTPS URL."""


class AttemptImageSigner(Protocol):
    async def sign(
        self,
        *,
        attempt_plan: Any,
        ttl_seconds: int,
    ) -> list[GatewayImageInput]:
        """Return ordered, request-scoped signed URLs for one Physical Attempt."""


class OSSAttemptImageSigner:
    """Revalidate immutable OSS image facts before producing read-only URLs."""

    def __init__(
        self,
        *,
        object_store: ObjectStorageGateway,
        allowed_signed_url_hosts: Sequence[str],
        max_ttl_seconds: int = 900,
    ) -> None:
        hosts = tuple(
            sorted({str(host).strip().casefold() for host in allowed_signed_url_hosts if host})
        )
        if not hosts:
            raise ImageSigningError("ai_gateway_image_signer_hosts_missing")
        if max_ttl_seconds < 30 or max_ttl_seconds > 900:
            raise ImageSigningError("ai_gateway_image_signer_ttl_invalid")
        self.object_store = object_store
        self.allowed_signed_url_hosts = hosts
        self.max_ttl_seconds = max_ttl_seconds

    async def sign(
        self,
        *,
        attempt_plan: Any,
        ttl_seconds: int,
    ) -> list[GatewayImageInput]:
        if not isinstance(attempt_plan, Mapping):
            raise ImageSigningError("ai_gateway_attempt_plan_invalid")
        attempt_id = str(attempt_plan.get("attempt_id") or "")
        if _OPAQUE_ID.fullmatch(attempt_id) is None:
            raise ImageSigningError("ai_gateway_attempt_id_invalid")
        if (
            not isinstance(ttl_seconds, int)
            or isinstance(ttl_seconds, bool)
            or ttl_seconds < 30
            or ttl_seconds > self.max_ttl_seconds
        ):
            raise ImageSigningError("ai_gateway_image_ttl_invalid")
        image_inputs = attempt_plan.get("image_inputs")
        expected_count = attempt_plan.get("image_count_requested")
        if not isinstance(image_inputs, (tuple, list)) or not isinstance(expected_count, int):
            raise ImageSigningError("ai_gateway_image_manifest_invalid")
        if expected_count < 0 or len(image_inputs) != expected_count:
            raise ImageSigningError("ai_gateway_image_count_mismatch")

        signed: list[GatewayImageInput] = []
        for expected_sequence, item in enumerate(image_inputs, start=1):
            if not isinstance(item, Mapping):
                raise ImageSigningError("ai_gateway_image_manifest_invalid")
            sequence_no = item.get("sequence_no")
            storage_profile = str(item.get("storage_profile") or "")
            object_key = str(item.get("object_key") or "")
            object_version_id = item.get("object_version_id")
            mime_type = str(item.get("mime_type") or "").strip().casefold()
            digest = str(item.get("sha256") or "").strip().casefold()
            size_bytes = item.get("size_bytes")
            if (
                sequence_no != expected_sequence
                or storage_profile != self.object_store.storage_profile
                or not object_key
                or (object_version_id is not None and not isinstance(object_version_id, str))
                or mime_type not in _SUPPORTED_IMAGE_MIME
                or _SHA256.fullmatch(digest) is None
                or not isinstance(size_bytes, int)
                or isinstance(size_bytes, bool)
                or size_bytes <= 0
            ):
                raise ImageSigningError("ai_gateway_image_manifest_invalid")
            try:
                validation = await self.object_store.validate_image_object(
                    object_key=object_key,
                    file_format={
                        "application/dicom": "dicom",
                        "image/jpeg": "jpeg",
                        "image/png": "png",
                    }[mime_type],
                    declared_content_type=mime_type,
                    expected_sha256=digest,
                    expected_size_bytes=size_bytes,
                    expected_object_version_id=object_version_id,
                )
                if (
                    validation.object_ref.storage_profile != storage_profile
                    or validation.object_ref.object_key != object_key
                    or validation.object_ref.sha256 != digest
                    or validation.object_ref.size_bytes != size_bytes
                    or validation.object_ref.content_type != mime_type
                    or (
                        object_version_id is not None
                        and validation.object_ref.object_version_id != object_version_id
                    )
                ):
                    raise ImageSigningError("ai_gateway_image_validation_mismatch")
                signed_url = await self.object_store.sign_download_url(
                    object_key=object_key,
                    expires_seconds=ttl_seconds,
                )
                signed_url = validate_signed_image_url(
                    signed_url,
                    allowed_hosts=self.allowed_signed_url_hosts,
                )
            except (ObjectStoreError, GatewayContractError) as exc:
                raise ImageSigningError(str(exc)) from exc
            signed.append(
                GatewayImageInput(
                    sequence_no=expected_sequence,
                    mime_type=mime_type,
                    signed_url=signed_url,
                )
            )
        return signed


def _oss_signed_url_hosts(*, endpoint: str, bucket_name: str) -> tuple[str, ...]:
    normalized_endpoint = endpoint.strip()
    if normalized_endpoint and "://" not in normalized_endpoint:
        normalized_endpoint = f"https://{normalized_endpoint}"
    parsed = urlsplit(normalized_endpoint)
    host = (parsed.hostname or "").strip().casefold()
    bucket = bucket_name.strip().casefold()
    if not host or not bucket:
        raise ImageSigningError("ai_gateway_image_signer_hosts_missing")
    hosts = {host}
    if not host.startswith(f"{bucket}."):
        hosts.add(f"{bucket}.{host}")
    return tuple(sorted(hosts))


def build_oss_attempt_image_signer(
    *, config: Settings = settings
) -> "OSSAttemptImageSigner":
    """Build the signer from the same OSS settings used by the image runtime."""
    try:
        object_store = OSSObjectStore(config)
        return OSSAttemptImageSigner(
            object_store=object_store,
            allowed_signed_url_hosts=_oss_signed_url_hosts(
                endpoint=object_store.endpoint,
                bucket_name=object_store.bucket_name,
            ),
            max_ttl_seconds=int(config.OSS_SIGNED_URL_TTL_SECONDS),
        )
    except ObjectStoreError as exc:
        raise ImageSigningError(str(exc)) from exc


__all__ = [
    "AttemptImageSigner",
    "ImageSigningError",
    "OSSAttemptImageSigner",
    "build_oss_attempt_image_signer",
]
