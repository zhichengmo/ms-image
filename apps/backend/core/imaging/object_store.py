"""OSS-backed object storage seam for worker-only image bytes."""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Protocol, Sequence

import numpy as np
import oss2
import pydicom
from PIL import Image
from pydicom.pixels import apply_voi_lut

from apps.backend.core.config import Settings, settings


_OBJECT_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
MAX_IMAGE_BYTES = 64 * 1024 * 1024
_MAX_IMAGE_DIMENSION = 16384
_MAX_IMAGE_PIXELS = 100_000_000


class ObjectStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageInspection:
    mime_type: str
    byte_size: int
    pixel_width: int
    pixel_height: int
    orientation: str | None = None


@dataclass(frozen=True)
class ObjectHead:
    storage_profile: str
    object_key: str
    object_version_id: str | None
    size_bytes: int
    content_type: str | None
    etag: str | None
    kms_key_version: str | None
    server_side_encryption: str | None = None


@dataclass(frozen=True)
class ObjectRef:
    storage_profile: str
    object_key: str
    object_version_id: str | None
    sha256: str
    size_bytes: int
    content_type: str
    kms_key_version: str | None


@dataclass(frozen=True)
class UploadGrant:
    storage_profile: str
    object_key: str
    upload_mode: str
    expires_seconds: int
    required_headers: dict[str, str]
    signed_url: str = field(repr=False)
    upload_session_ref: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class MultipartPart:
    part_number: int
    etag: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class ObjectValidation:
    object_ref: ObjectRef
    inspection: ImageInspection


class ObjectStorageGateway(Protocol):
    storage_profile: str

    async def prepare_direct_upload(
        self, *, object_key: str, content_type: str, expires_seconds: int | None = None
    ) -> UploadGrant: ...

    async def initiate_multipart_upload(
        self, *, object_key: str, content_type: str, expires_seconds: int | None = None
    ) -> UploadGrant: ...

    async def sign_multipart_parts(
        self,
        *,
        object_key: str,
        upload_session_ref: str,
        part_numbers: Sequence[int],
        expires_seconds: int | None = None,
    ) -> dict[int, str]: ...

    async def list_multipart_parts(
        self, *, object_key: str, upload_session_ref: str
    ) -> list[MultipartPart]: ...

    async def complete_multipart_upload(
        self,
        *,
        object_key: str,
        upload_session_ref: str,
        parts: Sequence[MultipartPart],
    ) -> ObjectHead: ...

    async def abort_multipart_upload(
        self, *, object_key: str, upload_session_ref: str
    ) -> None: ...

    async def put_bytes(
        self, *, object_key: str, content: bytes, mime_type: str
    ) -> None: ...

    async def put_encrypted_bytes(
        self,
        *,
        object_key: str,
        content: bytes,
        mime_type: str,
        encryption_algorithm: str,
        kms_key_id: str | None = None,
    ) -> None: ...

    async def head_object(self, *, object_key: str) -> ObjectHead: ...

    async def get_bytes(self, *, object_key: str) -> bytes: ...

    async def delete_object(self, *, object_key: str) -> None: ...

    async def validate_image_object(
        self,
        *,
        object_key: str,
        file_format: str,
        declared_content_type: str | None,
        expected_sha256: str | None,
        expected_size_bytes: int | None,
        expected_object_version_id: str | None = None,
    ) -> ObjectValidation: ...

    async def sign_download_url(
        self,
        *,
        object_key: str,
        expires_seconds: int = 300,
        object_version_id: str | None = None,
    ) -> str: ...


def validate_object_key(object_key: str) -> str:
    if not isinstance(object_key, str) or not _OBJECT_KEY.fullmatch(object_key):
        raise ObjectStoreError("object_key_invalid")
    if object_key.startswith("/") or "://" in object_key or ".." in object_key.split("/"):
        raise ObjectStoreError("object_key_path_invalid")
    return object_key


class OSSObjectStore:
    def __init__(self, config: Settings = settings):
        self.access_key_id = config.OSS_ACCESS_KEY_ID.strip()
        self.access_key_secret = config.OSS_ACCESS_KEY_SECRET.strip()
        self.bucket_name = config.OSS_BUCKET_NAME.strip()
        endpoint_value = (config.OSS_ENDPOINT or config.OSS_UPLOAD_ENDPOINT).strip()
        # OSS SDK download signing must yield an HTTPS URL. Deployment commonly
        # supplies a host-only endpoint, so normalize only that form before the
        # SDK receives it; explicitly configured schemes remain unchanged.
        self.endpoint = (
            endpoint_value
            if not endpoint_value or "://" in endpoint_value
            else f"https://{endpoint_value}"
        )
        self.storage_profile = config.OSS_STORAGE_PROFILE.strip() or "default"
        self.signed_url_ttl_seconds = int(config.OSS_SIGNED_URL_TTL_SECONDS)
        if not all((self.access_key_id, self.access_key_secret, self.bucket_name, self.endpoint)):
            raise ObjectStoreError("object_store_not_configured")
        self._auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self._bucket = oss2.Bucket(self._auth, self.endpoint, self.bucket_name)

    @staticmethod
    def new_image_object_key(
        *, image_id: str, generation: int, file_format: str
    ) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", image_id):
            raise ObjectStoreError("image_id_invalid")
        if generation < 1:
            raise ObjectStoreError("image_generation_invalid")
        suffix = file_format.strip().lower().lstrip(".")
        if not re.fullmatch(r"[a-z0-9]{1,16}", suffix):
            raise ObjectStoreError("image_format_invalid")
        return validate_object_key(
            f"image/{image_id}/{generation}/source.{suffix}"
        )

    @staticmethod
    def new_object_key(
        *,
        tenant_id: str,
        study_revision_id: str,
        source_index: int,
        suffix: str,
        content_sha256: str,
    ) -> str:
        safe_tenant = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]
        safe_revision = hashlib.sha256(study_revision_id.encode("utf-8")).hexdigest()[:32]
        suffix = suffix.lstrip(".").lower() or "bin"
        if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise ObjectStoreError("object_content_hash_invalid")
        return validate_object_key(
            f"xray-images/{safe_tenant}/{safe_revision}/{source_index}-{content_sha256}.{suffix}"
        )

    @staticmethod
    def expected_object_prefix(
        *, tenant_id: str, study_revision_id: str, source_index: int
    ) -> str:
        safe_tenant = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]
        safe_revision = hashlib.sha256(study_revision_id.encode("utf-8")).hexdigest()[:32]
        return f"xray-images/{safe_tenant}/{safe_revision}/{source_index}-"

    async def put_bytes(self, *, object_key: str, content: bytes, mime_type: str) -> None:
        validate_object_key(object_key)
        if not content:
            raise ObjectStoreError("object_content_empty")
        if len(content) > MAX_IMAGE_BYTES:
            raise ObjectStoreError("image_content_too_large")
        normalized_mime = mime_type.casefold().strip()
        if normalized_mime not in {
            "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp",
            "application/dicom", "application/json",
        }:
            raise ObjectStoreError("image_mime_invalid")

        def _put() -> None:
            result = self._bucket.put_object(
                object_key, content, headers={"Content-Type": normalized_mime}
            )
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_upload_failed")

        await asyncio.to_thread(_put)

    async def put_encrypted_bytes(
        self,
        *,
        object_key: str,
        content: bytes,
        mime_type: str,
        encryption_algorithm: str,
        kms_key_id: str | None = None,
    ) -> None:
        object_key = validate_object_key(object_key)
        if not isinstance(content, bytes) or not content:
            raise ObjectStoreError("object_content_empty")
        if len(content) > MAX_IMAGE_BYTES:
            raise ObjectStoreError("object_content_too_large")
        normalized_mime = _normalize_content_type(mime_type)
        algorithm = str(encryption_algorithm or "").strip().upper()
        normalized_key_id = str(kms_key_id or "").strip() or None
        if algorithm not in {"AES256", "KMS"}:
            raise ObjectStoreError("object_encryption_algorithm_invalid")
        if algorithm == "KMS" and not normalized_key_id:
            raise ObjectStoreError("object_encryption_kms_key_missing")
        if algorithm == "AES256" and normalized_key_id:
            raise ObjectStoreError("object_encryption_kms_key_unexpected")
        headers = {
            "Content-Type": normalized_mime,
            "x-oss-server-side-encryption": algorithm,
        }
        if normalized_key_id:
            headers["x-oss-server-side-encryption-key-id"] = normalized_key_id

        def _put() -> None:
            try:
                result = self._bucket.put_object(object_key, content, headers=headers)
            except oss2.exceptions.OssError as exc:
                raise ObjectStoreError("object_store_encrypted_upload_failed") from exc
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_encrypted_upload_failed")

        await asyncio.to_thread(_put)

    def _ttl(self, value: int | None) -> int:
        ttl = self.signed_url_ttl_seconds if value is None else int(value)
        if ttl <= 0 or ttl > 900:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        return ttl

    async def prepare_direct_upload(
        self, *, object_key: str, content_type: str, expires_seconds: int | None = None
    ) -> UploadGrant:
        object_key = validate_object_key(object_key)
        content_type = _normalize_content_type(content_type)
        ttl = self._ttl(expires_seconds)
        headers = {"Content-Type": content_type}
        signed_url = await asyncio.to_thread(
            self._bucket.sign_url,
            "PUT",
            object_key,
            ttl,
            headers,
        )
        return UploadGrant(
            storage_profile=self.storage_profile,
            object_key=object_key,
            upload_mode="direct_put",
            expires_seconds=ttl,
            required_headers=headers,
            signed_url=signed_url,
        )

    async def initiate_multipart_upload(
        self, *, object_key: str, content_type: str, expires_seconds: int | None = None
    ) -> UploadGrant:
        object_key = validate_object_key(object_key)
        content_type = _normalize_content_type(content_type)
        ttl = self._ttl(expires_seconds)

        def _initiate():
            result = self._bucket.init_multipart_upload(
                object_key, headers={"Content-Type": content_type}
            )
            upload_id = str(getattr(result, "upload_id", "") or "").strip()
            if not upload_id:
                raise ObjectStoreError("multipart_init_failed")
            return upload_id

        upload_id = await asyncio.to_thread(_initiate)
        return UploadGrant(
            storage_profile=self.storage_profile,
            object_key=object_key,
            upload_mode="multipart",
            expires_seconds=ttl,
            required_headers={"Content-Type": content_type},
            signed_url="",
            upload_session_ref=upload_id,
        )

    async def sign_multipart_parts(
        self,
        *,
        object_key: str,
        upload_session_ref: str,
        part_numbers: Sequence[int],
        expires_seconds: int | None = None,
    ) -> dict[int, str]:
        object_key = validate_object_key(object_key)
        upload_id = _validate_upload_session_ref(upload_session_ref)
        normalized_parts = sorted(set(int(number) for number in part_numbers))
        if not normalized_parts or any(number < 1 or number > 10_000 for number in normalized_parts):
            raise ObjectStoreError("multipart_part_number_invalid")
        ttl = self._ttl(expires_seconds)
        signed: dict[int, str] = {}
        for part_number in normalized_parts:
            signed[part_number] = await asyncio.to_thread(
                self._bucket.sign_url,
                "PUT",
                object_key,
                ttl,
                None,
                {"uploadId": upload_id, "partNumber": str(part_number)},
            )
        return signed

    async def list_multipart_parts(
        self, *, object_key: str, upload_session_ref: str
    ) -> list[MultipartPart]:
        object_key = validate_object_key(object_key)
        upload_id = _validate_upload_session_ref(upload_session_ref)

        def _list() -> list[MultipartPart]:
            result = self._bucket.list_parts(object_key, upload_id)
            return [
                MultipartPart(
                    part_number=int(part.part_number),
                    etag=_normalize_etag(part.etag),
                    size_bytes=int(getattr(part, "size", 0) or 0) or None,
                )
                for part in result.parts
            ]

        return await asyncio.to_thread(_list)

    async def complete_multipart_upload(
        self,
        *,
        object_key: str,
        upload_session_ref: str,
        parts: Sequence[MultipartPart],
    ) -> ObjectHead:
        object_key = validate_object_key(object_key)
        upload_id = _validate_upload_session_ref(upload_session_ref)
        requested = sorted(
            (MultipartPart(int(p.part_number), _normalize_etag(p.etag), p.size_bytes) for p in parts),
            key=lambda part: part.part_number,
        )
        if not requested or len({part.part_number for part in requested}) != len(requested):
            raise ObjectStoreError("multipart_part_manifest_invalid")
        actual = await self.list_multipart_parts(
            object_key=object_key, upload_session_ref=upload_id
        )
        actual_pairs = [(part.part_number, part.etag) for part in actual]
        if [(part.part_number, part.etag) for part in requested] != actual_pairs:
            raise ObjectStoreError("multipart_part_manifest_mismatch")

        def _complete() -> None:
            result = self._bucket.complete_multipart_upload(
                object_key,
                upload_id,
                [oss2.models.PartInfo(part.part_number, part.etag) for part in requested],
            )
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("multipart_complete_failed")

        await asyncio.to_thread(_complete)
        return await self.head_object(object_key=object_key)

    async def abort_multipart_upload(
        self, *, object_key: str, upload_session_ref: str
    ) -> None:
        object_key = validate_object_key(object_key)
        upload_id = _validate_upload_session_ref(upload_session_ref)

        def _abort() -> None:
            try:
                self._bucket.abort_multipart_upload(object_key, upload_id)
            except oss2.exceptions.NoSuchUpload:
                return
            except oss2.exceptions.OssError as exc:
                raise ObjectStoreError("multipart_abort_failed") from exc

        await asyncio.to_thread(_abort)

    async def head_object(self, *, object_key: str) -> ObjectHead:
        object_key = validate_object_key(object_key)

        def _head() -> ObjectHead:
            try:
                # ``get_object_meta`` is an OSS ``?objectMeta`` request.  It
                # deliberately returns only basic metadata and omits MIME/SSE
                # response facts on some OSS deployments, so it cannot prove
                # the encrypted-response storage contract.  Use HEAD instead:
                # the SDK's HeadObjectResult exposes Content-Type and the OSS
                # server-side-encryption headers needed by the fail-closed
                # Gateway response store.
                result = self._bucket.head_object(object_key)
            except (oss2.exceptions.NoSuchKey, oss2.exceptions.NotFound) as exc:
                raise ObjectStoreError("object_not_found") from exc
            except oss2.exceptions.OssError as exc:
                raise ObjectStoreError("object_store_head_failed") from exc
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_head_failed")
            size = int(getattr(result, "content_length", -1))
            if size < 0:
                raise ObjectStoreError("object_size_invalid")
            headers = getattr(result, "headers", {}) or {}
            return ObjectHead(
                storage_profile=self.storage_profile,
                object_key=object_key,
                object_version_id=_header(headers, "x-oss-version-id"),
                size_bytes=size,
                content_type=(
                    getattr(result, "content_type", None)
                    or _header(headers, "content-type")
                    or None
                ),
                etag=_normalize_optional_etag(getattr(result, "etag", None)),
                kms_key_version=_header(
                    headers, "x-oss-server-side-encryption-key-id"
                ),
                server_side_encryption=_header(
                    headers, "x-oss-server-side-encryption"
                ),
            )

        return await asyncio.to_thread(_head)

    async def get_bytes(self, *, object_key: str) -> bytes:
        validate_object_key(object_key)

        def _get() -> bytes:
            result = self._bucket.get_object(object_key)
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_download_failed")
            declared_length = getattr(result, "content_length", None)
            if isinstance(declared_length, int) and declared_length > MAX_IMAGE_BYTES:
                raise ObjectStoreError("image_content_too_large")
            content = result.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ObjectStoreError("image_content_too_large")
            return content

        content = await asyncio.to_thread(_get)
        if not content:
            raise ObjectStoreError("object_content_empty")
        return content

    async def delete_object(self, *, object_key: str) -> None:
        object_key = validate_object_key(object_key)

        def _delete() -> None:
            result = self._bucket.delete_object(object_key)
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_delete_failed")

        await asyncio.to_thread(_delete)

    async def validate_image_object(
        self,
        *,
        object_key: str,
        file_format: str,
        declared_content_type: str | None,
        expected_sha256: str | None,
        expected_size_bytes: int | None,
        expected_object_version_id: str | None = None,
    ) -> ObjectValidation:
        object_key = validate_object_key(object_key)
        before = await self.head_object(object_key=object_key)
        if expected_size_bytes is not None and before.size_bytes != expected_size_bytes:
            raise ObjectStoreError("object_size_mismatch")
        if before.size_bytes > MAX_IMAGE_BYTES:
            raise ObjectStoreError("image_content_too_large")
        if expected_object_version_id and before.object_version_id != expected_object_version_id:
            raise ObjectStoreError("object_version_mismatch")

        def _stream() -> tuple[bytes, str, str | None]:
            result = self._bucket.get_object(object_key)
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_download_failed")
            digest = hashlib.sha256()
            content = bytearray()
            while True:
                chunk = result.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                content.extend(chunk)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ObjectStoreError("image_content_too_large")
            headers = getattr(result, "headers", {}) or {}
            return bytes(content), digest.hexdigest(), _header(headers, "x-oss-version-id")

        content, digest, read_version_id = await asyncio.to_thread(_stream)
        if len(content) != before.size_bytes:
            raise ObjectStoreError("object_size_changed")
        if expected_sha256 and digest != expected_sha256:
            raise ObjectStoreError("object_sha256_mismatch")
        inspection = inspect_image_bytes(content, declared_content_type or before.content_type)
        _validate_file_format(file_format, inspection.mime_type)
        after = await self.head_object(object_key=object_key)
        if (
            before.size_bytes != after.size_bytes
            or before.etag != after.etag
            or before.object_version_id != after.object_version_id
        ):
            raise ObjectStoreError("object_changed_during_validation")
        version_id = read_version_id or after.object_version_id
        if expected_object_version_id and version_id != expected_object_version_id:
            raise ObjectStoreError("object_version_mismatch")
        return ObjectValidation(
            object_ref=ObjectRef(
                storage_profile=self.storage_profile,
                object_key=object_key,
                object_version_id=version_id,
                sha256=digest,
                size_bytes=len(content),
                content_type=inspection.mime_type,
                kms_key_version=after.kms_key_version,
            ),
            inspection=inspection,
        )

    async def sign_download_url(
        self,
        *,
        object_key: str,
        expires_seconds: int = 300,
        object_version_id: str | None = None,
    ) -> str:
        object_key = validate_object_key(object_key)
        ttl = self._ttl(expires_seconds)
        params = None
        if object_version_id is not None:
            version_id = object_version_id.strip()
            if not version_id or len(version_id) > 160:
                raise ObjectStoreError("object_version_id_invalid")
            params = {"versionId": version_id}
        if params is None:
            return await asyncio.to_thread(
                self._bucket.sign_url,
                "GET",
                object_key,
                ttl,
            )
        return await asyncio.to_thread(
            self._bucket.sign_url,
            "GET",
            object_key,
            ttl,
            params=params,
        )


def _normalize_content_type(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized or len(normalized) > 128 or "/" not in normalized:
        raise ObjectStoreError("object_content_type_invalid")
    return normalized


def _validate_upload_session_ref(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 256 or any(char.isspace() for char in normalized):
        raise ObjectStoreError("multipart_upload_session_invalid")
    return normalized


def _normalize_etag(value: str) -> str:
    normalized = str(value or "").strip().strip('"')
    if not normalized or len(normalized) > 128:
        raise ObjectStoreError("multipart_etag_invalid")
    return normalized


def _normalize_optional_etag(value: str | None) -> str | None:
    return _normalize_etag(value) if value else None


def _header(headers: dict, name: str) -> str | None:
    value = headers.get(name) or headers.get(name.title())
    if value is None:
        normalized_name = name.casefold()
        for key, candidate in headers.items():
            if str(key).strip().casefold() == normalized_name:
                value = candidate
                break
    normalized = str(value or "").strip()
    return normalized or None


def _validate_file_format(file_format: str, mime_type: str) -> None:
    expected = {
        "dicom": "application/dicom",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }.get(file_format.strip().lower())
    if expected is not None and mime_type != expected:
        raise ObjectStoreError("image_format_mismatch")


def inspect_image_bytes(content: bytes, declared_mime: str | None = None) -> ImageInspection:
    if not content:
        raise ObjectStoreError("image_content_empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise ObjectStoreError("image_content_too_large")
    declared = (declared_mime or "").casefold().strip()
    if declared == "image/jpg":
        declared = "image/jpeg"
    if declared == "application/dicom+json":
        raise ObjectStoreError("image_mime_invalid")
    has_dicom_preamble = (
        len(content) >= 132 and content[128:132] == b"DICM"
    )
    if has_dicom_preamble and declared and declared != "application/dicom":
        raise ObjectStoreError("image_mime_mismatch")
    is_dicom = declared == "application/dicom" or has_dicom_preamble
    if is_dicom:
        try:
            dataset = pydicom.dcmread(BytesIO(content), force=False)
            width = int(dataset.Columns)
            height = int(dataset.Rows)
            if not getattr(dataset, "PixelData", None):
                raise ObjectStoreError("dicom_pixel_data_missing")
            _validate_dimensions(width, height)
            return ImageInspection(
                mime_type="application/dicom",
                byte_size=len(content),
                pixel_width=width,
                pixel_height=height,
                orientation=str(getattr(dataset, "PatientOrientation", ""))[:32] or None,
            )
        except ObjectStoreError:
            raise
        except Exception as exc:
            raise ObjectStoreError("dicom_decode_failed") from exc
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            mime_type = Image.MIME.get(image.format, "").casefold()
            if not mime_type.startswith("image/"):
                raise ObjectStoreError("image_mime_invalid")
            if declared and declared != mime_type:
                raise ObjectStoreError("image_mime_mismatch")
            _validate_dimensions(int(image.width), int(image.height))
            return ImageInspection(
                mime_type=mime_type,
                byte_size=len(content),
                pixel_width=int(image.width),
                pixel_height=int(image.height),
            )
    except ObjectStoreError:
        raise
    except Exception as exc:
        raise ObjectStoreError("image_decode_failed") from exc


def _validate_dimensions(width: int, height: int) -> None:
    if (
        width <= 0
        or height <= 0
        or width > _MAX_IMAGE_DIMENSION
        or height > _MAX_IMAGE_DIMENSION
        or width * height > _MAX_IMAGE_PIXELS
    ):
        raise ObjectStoreError("image_dimensions_invalid")


def dicom_to_png(content: bytes) -> tuple[bytes, ImageInspection]:
    """Convert a single-frame DICOM to an 8-bit PNG for Provider memory only.

    The original DICOM remains the persisted OSS object and keeps its original
    SHA256.  The returned PNG gets an independent sent SHA256 in ModelCall
    receipts, preserving source-to-sent lineage without overwriting the source.
    """
    try:
        dataset = pydicom.dcmread(BytesIO(content), force=False)
        frames = int(getattr(dataset, "NumberOfFrames", 1) or 1)
        if frames != 1:
            raise ObjectStoreError("dicom_multiframe_not_supported")
        _validate_dimensions(int(dataset.Columns), int(dataset.Rows))
        pixels = np.asarray(apply_voi_lut(dataset.pixel_array, dataset))
        if pixels.ndim == 3 and pixels.shape[-1] in {3, 4}:
            array = pixels[..., :3]
            if array.dtype != np.uint8:
                minimum = float(np.nanmin(array))
                maximum = float(np.nanmax(array))
                if not np.isfinite(minimum) or not np.isfinite(maximum) or maximum <= minimum:
                    raise ObjectStoreError("dicom_pixel_range_invalid")
                array = ((array - minimum) * (255.0 / (maximum - minimum))).clip(0, 255).astype(np.uint8)
            image = Image.fromarray(array, mode="RGB")
        elif pixels.ndim == 2:
            minimum = float(np.nanmin(pixels))
            maximum = float(np.nanmax(pixels))
            if not np.isfinite(minimum) or not np.isfinite(maximum) or maximum <= minimum:
                raise ObjectStoreError("dicom_pixel_range_invalid")
            array = ((pixels - minimum) * (255.0 / (maximum - minimum))).clip(0, 255).astype(np.uint8)
            if str(getattr(dataset, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
                array = 255 - array
            image = Image.fromarray(array, mode="L")
        else:
            raise ObjectStoreError("dicom_pixel_shape_invalid")
        _validate_dimensions(image.width, image.height)
        output = BytesIO()
        image.save(output, format="PNG", optimize=False)
        encoded = output.getvalue()
        return encoded, ImageInspection(
            mime_type="image/png",
            byte_size=len(encoded),
            pixel_width=image.width,
            pixel_height=image.height,
        )
    except ObjectStoreError:
        raise
    except Exception as exc:
        raise ObjectStoreError("dicom_decode_failed") from exc


__all__ = [
    "ImageInspection",
    "MultipartPart",
    "OSSObjectStore",
    "ObjectHead",
    "ObjectRef",
    "ObjectStorageGateway",
    "ObjectStoreError",
    "ObjectValidation",
    "UploadGrant",
    "dicom_to_png",
    "inspect_image_bytes",
    "validate_object_key",
]
