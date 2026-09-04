import jwt
import os
import rsa
import base64
import json
from dataclasses import dataclass
from datetime import datetime
from fastapi import Depends, Header, HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import TYPE_CHECKING, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.async_db import get_async_session, get_explicit_transaction_session
from apps.backend.core.imaging.object_store import (
    OSSObjectStore,
    ObjectStorageGateway,
)
from apps.backend.core.contexts import CallerContext, ControlPlaneContext

if TYPE_CHECKING:
    from apps.backend.services.runtime.service.image_service import ImageService
    from apps.backend.services.runtime.service.task_service import TaskService


auth_domain = os.getenv('AUTH_DOMAIN')
http_bearer = HTTPBearer(auto_error=False)
admin_http_bearer = HTTPBearer(auto_error=False)
_PLACEHOLDER_JWT_SECRETS = frozenset(
    {
        "replace-with-a-secret-managed-outside-git",
        "your_secret_key",
        "change-me",
        "password",
    }
)


def control_plane_jwt_readiness() -> tuple[bool, str | None]:
    """Validate the static verifier contract without accepting a token."""

    secret = settings.ADMIN_SECRET_KEY.strip()
    if settings.ADMIN_ALGORITHM != "HS256":
        return False, "control_plane_jwt_algorithm_invalid"
    if not secret or secret in _PLACEHOLDER_JWT_SECRETS:
        return False, "control_plane_jwt_key_unavailable"
    if not settings.ADMIN_JWT_ISSUER.strip() or not settings.ADMIN_JWT_AUDIENCE.strip():
        return False, "control_plane_jwt_claim_contract_invalid"
    if not settings.ADMIN_REQUIRED_WRITE_SCOPE.strip():
        return False, "control_plane_jwt_scope_contract_invalid"
    return True, None


def _unauthorized(detail: str = "Invalid bearer token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_token(
        token: str,
        *,
        key: str,
        algorithm: str,
        issuer: str,
        audience: str,
) -> dict:
    if not key or key.strip() in _PLACEHOLDER_JWT_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT verification is not configured",
        )
    if algorithm not in {"RS256", "HS256"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT algorithm is not configured",
        )
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError:
        raise _unauthorized()
    if not isinstance(payload, dict):
        raise _unauthorized()
    return payload


def get_jwt_data(
    data: Optional[HTTPAuthorizationCredentials] = Security(http_bearer)
) -> dict:
    if data is None:
        raise _unauthorized("Missing bearer token")
    return _decode_token(
        data.credentials,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )


def get_admin_jwt_data(
    data: Optional[HTTPAuthorizationCredentials] = Security(admin_http_bearer),
) -> dict:
    """Decode an administrator JWT with an isolated key and claim contract."""

    if data is None:
        raise _unauthorized("Missing bearer token")
    if settings.ADMIN_ALGORITHM != "HS256":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin JWT algorithm is not configured",
        )
    payload = _decode_token(
        data.credentials,
        key=settings.ADMIN_SECRET_KEY,
        algorithm="HS256",
        issuer=settings.ADMIN_JWT_ISSUER,
        audience=settings.ADMIN_JWT_AUDIENCE,
    )
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise _unauthorized()
    return payload


def _scopes(payload: dict) -> set[str]:
    granted: set[str] = set()
    scope = payload.get("scope")
    if isinstance(scope, str):
        granted.update(item for item in scope.split() if item)
    scopes = payload.get("scopes")
    if isinstance(scopes, list) and all(isinstance(item, str) for item in scopes):
        granted.update(item for item in scopes if item)
    return granted


def require_admin_scope(*required_scopes: str):
    """Return a FastAPI dependency enforcing admin JWT scopes."""

    scopes = tuple(required_scopes) or (settings.ADMIN_REQUIRED_SCOPE,)

    def dependency(payload: dict = Depends(get_admin_jwt_data)) -> dict:
        granted = _scopes(payload)
        if not set(scopes).issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient admin scope",
            )
        return {"subject": payload["sub"], "scopes": sorted(granted)}

    return dependency


def get_admin_tenant_context(
    jwt_data: dict = Depends(get_admin_jwt_data),
) -> dict:
    """Return admin subject, scopes, and immutable tenant claim for control reads."""
    subject = jwt_data.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized("Subject is required")
    return {
        "subject": subject.strip(),
        "tenant_id": _tenant_id(jwt_data),
        "scopes": sorted(_scopes(jwt_data)),
    }


def require_admin_tenant_scope(*required_scopes: str):
    """Require admin JWT scope and tenant claim before control-plane access."""
    scopes = tuple(required_scopes) or (settings.ADMIN_REQUIRED_SCOPE,)

    def dependency(context: dict = Depends(get_admin_tenant_context)) -> dict:
        if not set(scopes).issubset(set(context["scopes"])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient admin scope",
            )
        return context

    return dependency


def _tenant_id(payload: dict) -> str:
    """Extract one tenant from a verified token; request data cannot override it."""
    tenant = payload.get(settings.TENANT_CLAIM)
    if not isinstance(tenant, str) or not tenant.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope is required",
        )
    return tenant.strip()


def get_tenant_context(
    jwt_data: dict = Depends(get_jwt_data),
) -> dict:
    """Return the authenticated subject and immutable tenant scope.

    New XRay endpoints must use this dependency rather than trusting a tenant
    query parameter or request-body field.
    """
    subject = jwt_data.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized("Subject is required")
    return {
        "subject": subject.strip(),
        "tenant_id": _tenant_id(jwt_data),
        "scopes": sorted(_scopes(jwt_data)),
    }


def require_tenant_scope(*required_scopes: str):
    """Require a verified user token and optional user scope for XRay APIs."""
    scopes = tuple(required_scopes)

    def dependency(context: dict = Depends(get_tenant_context)) -> dict:
        if scopes and not set(scopes).issubset(set(context["scopes"])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient tenant scope",
            )
        return context

    return dependency


def get_resource_context(jwt_data: dict = Depends(get_jwt_data)) -> dict:
    """Return verified identity/scope without persisting the legacy tenant claim."""
    subject = jwt_data.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized("Subject is required")
    return {
        "subject": subject.strip(),
        "scopes": sorted(_scopes(jwt_data)),
    }


def get_caller_context(jwt_data: dict = Depends(get_jwt_data)) -> CallerContext:
    subject = jwt_data.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized("Subject is required")
    return CallerContext(subject_id=subject.strip(), scopes=frozenset(_scopes(jwt_data)))


def require_caller_scope(*required_scopes: str):
    scopes = frozenset(required_scopes)

    def dependency(context: CallerContext = Depends(get_caller_context)) -> CallerContext:
        if scopes and not scopes.issubset(context.scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient caller scope")
        return context

    return dependency


def get_control_plane_context(payload: dict = Depends(get_admin_jwt_data)) -> ControlPlaneContext:
    return ControlPlaneContext(subject_id=payload["sub"], scopes=frozenset(_scopes(payload)))


def require_control_plane_scope(*required_scopes: str):
    scopes = frozenset(required_scopes) or frozenset({settings.ADMIN_REQUIRED_WRITE_SCOPE})

    def dependency(context: ControlPlaneContext = Depends(get_control_plane_context)) -> ControlPlaneContext:
        if not scopes.issubset(context.scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient control-plane scope")
        return context

    return dependency


def require_control_plane_any_scope(*allowed_scopes: str):
    scopes = frozenset(scope for scope in allowed_scopes if scope)
    if not scopes:
        raise ValueError("control_plane_scope_required")

    def dependency(context: ControlPlaneContext = Depends(get_control_plane_context)) -> ControlPlaneContext:
        if context.scopes.isdisjoint(scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient control-plane scope")
        return context

    return dependency


def require_resource_scope(*required_scopes: str):
    scopes = tuple(required_scopes)

    def dependency(context: dict = Depends(get_resource_context)) -> dict:
        if scopes and not set(scopes).issubset(set(context["scopes"])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient resource scope",
            )
        return context

    return dependency


async def get_session_service(db=Depends(get_async_session)):
    from apps.backend.services.runtime.service.session_service import SessionService

    return SessionService(db)


async def get_study_service(db=Depends(get_async_session)):
    from apps.backend.services.runtime.service.study_service import StudyService

    return StudyService(db)


async def get_image_service(db=Depends(get_async_session)):
    from apps.backend.services.runtime.service.image_service import ImageService

    return ImageService(db)


async def get_pet_profile_service(db=Depends(get_async_session)):
    from apps.backend.services.runtime.service.pet_profile_service import PetProfileService

    return PetProfileService(db)


async def get_pet_info_service(db=Depends(get_async_session)):
    from apps.backend.services.runtime.service.pet_info_service import PetInfoService

    return PetInfoService(db)


@dataclass(frozen=True)
class ImageStorageDependencies:
    db: AsyncSession
    service: "ImageService"
    gateway_factory: Callable[[], ObjectStorageGateway]


async def get_image_storage_dependencies(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> ImageStorageDependencies:
    from apps.backend.services.runtime.service.image_service import ImageService

    return ImageStorageDependencies(
        db=db,
        service=ImageService(db),
        gateway_factory=OSSObjectStore,
    )


@dataclass(frozen=True)
class AnatomyLocalizationDisplayDependencies:
    db: AsyncSession
    service: "TaskService"
    gateway_factory: Callable[[], ObjectStorageGateway]


async def get_anatomy_localization_display_dependencies(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> AnatomyLocalizationDisplayDependencies:
    from apps.backend.services.runtime.service.task_service import TaskService

    return AnatomyLocalizationDisplayDependencies(
        db=db,
        service=TaskService(db),
        gateway_factory=OSSObjectStore,
    )




def authorized_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> str:
    try:
        # 根据JWT token格式提取用户ID
        if 'sub' in jwt_data and isinstance(jwt_data['sub'], dict):
            user_uuid = jwt_data['sub'].get('id')
        elif 'identity' in jwt_data:
            identity = jwt_data['identity']
            user_uuid = identity.get('id') if isinstance(identity, dict) else identity
        else:
            user_uuid = jwt_data.get('sub')

        if not user_uuid:
            raise ValueError("User ID not found in JWT token")

        # 确保返回字符串类型
        return str(user_uuid)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failed to extract user ID from JWT"
        )


def is_internal_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> bool:
    identity = jwt_data.get("identity", jwt_data.get("sub"))
    if not isinstance(identity, dict) or not identity.get("is_internal"):
        raise HTTPException(
            status_code=403,
            detail='You are not internal user'
        )
    return bool(identity["is_internal"])


def is_tester_user(
    jwt_data: dict = Depends(get_jwt_data)
) -> bool:
    identity = jwt_data.get("sub")
    return bool(identity.get("is_tester")) if isinstance(identity, dict) else False


def ms_api_key_verified(
    authorization: Optional[str] = Header(None)
):
    if not authorization:
        raise HTTPException(
            status_code=400,
            detail='Missing authorization headers.'
        )
    try:
        private_key = rsa.PrivateKey.load_pkcs1(settings.API_PRIVATE_KEY)
        decrypted_data = rsa.decrypt(base64.b64decode(authorization), private_key).decode()
        decrypted_json = json.loads(decrypted_data)
        key_time = int(decrypted_json['timestamp'])
    except Exception:
        raise HTTPException(
            status_code=401,
            detail='Invalid API key'
        )
    now_time = int(datetime.utcnow().timestamp())
    # APi KEY过期时间五分钟
    # Reject future-dated credentials as well as credentials older than the
    # five-minute window.  Without the lower bound, an attacker could submit
    # an arbitrarily future timestamp and keep the credential valid forever.
    if 0 <= now_time - key_time <= 300:
        return True
    else:
        raise HTTPException(
            status_code=401,
            detail='The API key is expired.'
        )
