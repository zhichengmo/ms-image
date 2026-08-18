"""Provider-neutral image resolution contracts.

The resolver intentionally runs inside the Worker.  Broker messages and
persisted snapshots carry only opaque references and safe metadata; image
bytes never cross that boundary.
"""

from .contracts import (
    FailClosedImageResolver,
    ImageResolver,
    ImageResolverError,
)
from .object_store import (
    ImageInspection,
    MAX_IMAGE_BYTES,
    MultipartPart,
    OSSObjectStore,
    ObjectHead,
    ObjectRef,
    ObjectStorageGateway,
    ObjectStoreError,
    ObjectValidation,
    UploadGrant,
    dicom_to_png,
    inspect_image_bytes,
)
from .manifest import (
    CanonicalManifest,
    EMPTY_MANIFEST,
    ManifestContractError,
    build_series_manifest,
    build_study_manifest,
)
from .oss_resolver import XRayOSSImageResolver
from .ingest import (
    ApprovedManifestSourceImageFetcher,
    FailClosedSourceImageFetcher,
    SourceImageFetcher,
    XRayImageIngestService,
)

__all__ = [
    "FailClosedImageResolver",
    "ImageResolver",
    "ImageResolverError",
    "ImageInspection",
    "MAX_IMAGE_BYTES",
    "MultipartPart",
    "OSSObjectStore",
    "ObjectHead",
    "ObjectRef",
    "ObjectStorageGateway",
    "ObjectStoreError",
    "ObjectValidation",
    "UploadGrant",
    "CanonicalManifest",
    "EMPTY_MANIFEST",
    "ManifestContractError",
    "build_series_manifest",
    "build_study_manifest",
    "dicom_to_png",
    "XRayOSSImageResolver",
    "inspect_image_bytes",
    "FailClosedSourceImageFetcher",
    "ApprovedManifestSourceImageFetcher",
    "SourceImageFetcher",
    "XRayImageIngestService",
]
