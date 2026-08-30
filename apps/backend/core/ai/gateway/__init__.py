"""Image-runtime contracts around the ms-ai-fast-compatible AI request path."""

from .attempt_lookup import (
    AttemptLookupError,
    AttemptLookupResult,
    ProviderAttemptLookup,
    UnsupportedProviderAttemptLookup,
)
from .contracts import (
    AI_IMAGE_RECEIPT_V1,
    AI_IMAGE_RECEIPT_V2,
    GATEWAY_PROFILE_V1,
    GatewayContractError,
    GatewayDefiniteResponseError,
    GatewayExecutionResult,
    GatewayImageInput,
    GatewayRejectedError,
    GatewayRequest,
    GatewayUnknownDeliveryError,
    canonical_user_context,
    normalize_gateway_profile,
    response_sha256,
    schema_validate_result,
    validate_signed_image_url,
)
from .image_signer import (
    AttemptImageSigner,
    ImageSigningError,
    OSSAttemptImageSigner,
    build_oss_attempt_image_signer,
)

__all__ = [
    "AI_IMAGE_RECEIPT_V1",
    "AI_IMAGE_RECEIPT_V2",
    "AttemptImageSigner",
    "AttemptLookupError",
    "AttemptLookupResult",
    "GATEWAY_PROFILE_V1",
    "GatewayContractError",
    "GatewayDefiniteResponseError",
    "GatewayExecutionResult",
    "GatewayImageInput",
    "GatewayRejectedError",
    "GatewayRequest",
    "GatewayUnknownDeliveryError",
    "ImageSigningError",
    "OSSAttemptImageSigner",
    "ProviderAttemptLookup",
    "UnsupportedProviderAttemptLookup",
    "build_oss_attempt_image_signer",
    "canonical_user_context",
    "normalize_gateway_profile",
    "response_sha256",
    "schema_validate_result",
    "validate_signed_image_url",
]
