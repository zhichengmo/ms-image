"""OSS-backed object storage seam for worker-only image bytes."""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import oss2
import pydicom
from PIL import Image
from pydicom.pixels import apply_voi_lut

from app.core.config import Settings, settings


_OBJECT_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_MAX_IMAGE_BYTES = 64 * 1024 * 1024
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


def validate_object_key(object_key: str) -> str:
    if not isinstance(object_key, str) or not _OBJECT_KEY.fullmatch(object_key):
        raise ObjectStoreError("object_key_invalid")
    if ".." in object_key.split("/"):
        raise ObjectStoreError("object_key_path_invalid")
    return object_key


class OSSObjectStore:
    def __init__(self, config: Settings = settings):
        self.access_key_id = config.OSS_ACCESS_KEY_ID.strip()
        self.access_key_secret = config.OSS_ACCESS_KEY_SECRET.strip()
        self.bucket_name = config.OSS_BUCKET_NAME.strip()
        self.endpoint = (config.OSS_ENDPOINT or config.OSS_UPLOAD_ENDPOINT).strip()
        if not all((self.access_key_id, self.access_key_secret, self.bucket_name, self.endpoint)):
            raise ObjectStoreError("object_store_not_configured")
        self._auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self._bucket = oss2.Bucket(self._auth, self.endpoint, self.bucket_name)

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
        if len(content) > _MAX_IMAGE_BYTES:
            raise ObjectStoreError("image_content_too_large")
        normalized_mime = mime_type.casefold().strip()
        if normalized_mime not in {
            "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp",
            "application/dicom",
        }:
            raise ObjectStoreError("image_mime_invalid")

        def _put() -> None:
            result = self._bucket.put_object(
                object_key, content, headers={"Content-Type": normalized_mime}
            )
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_upload_failed")

        await asyncio.to_thread(_put)

    async def get_bytes(self, *, object_key: str) -> bytes:
        validate_object_key(object_key)

        def _get() -> bytes:
            result = self._bucket.get_object(object_key)
            if getattr(result, "status", 500) >= 400:
                raise ObjectStoreError("object_store_download_failed")
            declared_length = getattr(result, "content_length", None)
            if isinstance(declared_length, int) and declared_length > _MAX_IMAGE_BYTES:
                raise ObjectStoreError("image_content_too_large")
            content = result.read(_MAX_IMAGE_BYTES + 1)
            if len(content) > _MAX_IMAGE_BYTES:
                raise ObjectStoreError("image_content_too_large")
            return content

        content = await asyncio.to_thread(_get)
        if not content:
            raise ObjectStoreError("object_content_empty")
        return content

    async def sign_download_url(self, *, object_key: str, expires_seconds: int = 300) -> str:
        validate_object_key(object_key)
        if expires_seconds <= 0 or expires_seconds > 900:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        return await asyncio.to_thread(self._bucket.sign_url, "GET", object_key, expires_seconds)


def inspect_image_bytes(content: bytes, declared_mime: str | None = None) -> ImageInspection:
    if not content:
        raise ObjectStoreError("image_content_empty")
    if len(content) > _MAX_IMAGE_BYTES:
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
    "OSSObjectStore",
    "ObjectStoreError",
    "dicom_to_png",
    "inspect_image_bytes",
    "validate_object_key",
]
