import jwt
import os
import rsa
import base64
import json
from datetime import datetime
from fastapi import Depends, Header, HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional

from app.core.config import settings
from app.core.async_db import get_async_session


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
    from app.service.session_service import SessionService

    return SessionService(db)


async def get_study_service(db=Depends(get_async_session)):
    from app.service.study_service import StudyService

    return StudyService(db)


async def get_image_service(db=Depends(get_async_session)):
    from app.service.image_service import ImageService

    return ImageService(db)


async def get_xray_run_service(
    db=Depends(get_async_session),
):
    """Expose the existing XRay service through API dependency injection."""
    from app.service.xray_accuracy import XRayRunService

    return XRayRunService(db)


async def get_xray_trace_service(
    db=Depends(get_async_session),
):
    """Expose the existing XRay trace service through API dependency injection."""
    from app.service.xray_accuracy import XRayTraceService

    return XRayTraceService(db)


async def get_xray_execution_service(
    db=Depends(get_async_session),
):
    """Expose the validation-only execution/result service via DI."""
    from app.service.xray_accuracy import XRayExecutionService

    return XRayExecutionService(db)


async def get_xray_lifecycle_service(
    db=Depends(get_async_session),
):
    """Expose Session/Study/Image lifecycle orchestration through DI."""
    from app.service.xray_accuracy import XRayLifecycleService

    return XRayLifecycleService(db)


async def get_xray_legacy_compat_service(
    db=Depends(get_async_session),
):
    """Expose legacy XRay V2 request semantics over the new fact model."""
    from app.service.xray_accuracy import XRayLegacyCompatService

    return XRayLegacyCompatService(db)


async def get_xray_provider_qualification_service(
    db=Depends(get_async_session),
):
    from app.service.xray_accuracy import XRayProviderQualificationService

    return XRayProviderQualificationService(db)


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
    except:
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
