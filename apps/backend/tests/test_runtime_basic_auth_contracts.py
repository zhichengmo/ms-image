from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasicCredentials
from pydantic import ValidationError

from apps.backend.core import dependencies
from apps.backend.core.config import Settings


def _configure_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies.settings, "BASIC_AUTH_USERNAME", "demo-user")
    monkeypatch.setattr(dependencies.settings, "BASIC_AUTH_PASSWORD", "demo-pass")
    monkeypatch.setattr(
        dependencies.settings,
        "BASIC_AUTH_SUBJECT",
        "xray-browser-user",
    )
    monkeypatch.setattr(dependencies.settings, "BASIC_AUTH_SCOPES", "imaging:run")


def test_runtime_accepts_configured_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_basic(monkeypatch)

    payload = dependencies.get_jwt_data(
        data=None,
        basic_credentials=HTTPBasicCredentials(
            username="demo-user",
            password="demo-pass",
        ),
    )

    assert payload == {
        "sub": "xray-browser-user",
        "scopes": ["imaging:run"],
    }


def test_runtime_rejects_incorrect_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_basic(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_jwt_data(
            data=None,
            basic_credentials=HTTPBasicCredentials(
                username="demo-user",
                password="wrong-password",
            ),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect username or password"
    assert exc_info.value.headers == {
        "WWW-Authenticate": 'Basic realm="ms-image-runtime"',
    }


def test_runtime_fails_closed_when_basic_auth_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dependencies.settings, "BASIC_AUTH_USERNAME", "")
    monkeypatch.setattr(dependencies.settings, "BASIC_AUTH_PASSWORD", "")

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_jwt_data(
            data=None,
            basic_credentials=HTTPBasicCredentials(
                username="demo-user",
                password="demo-pass",
            ),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Basic authentication is not configured"


def test_runtime_bearer_auth_remains_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "runtime-basic-auth-test-secret"
    monkeypatch.setattr(dependencies.settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(dependencies.settings, "SECRET_KEY", secret)
    monkeypatch.setattr(dependencies.settings, "JWT_ISSUER", "ms-image")
    monkeypatch.setattr(dependencies.settings, "JWT_AUDIENCE", "ms-image-api")
    token = jwt.encode(
        {
            "sub": "bearer-user",
            "scope": "imaging:run",
            "iss": "ms-image",
            "aud": "ms-image-api",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )

    payload = dependencies.get_jwt_data(
        data=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        basic_credentials=None,
    )

    assert payload["sub"] == "bearer-user"
    assert payload["scope"] == "imaging:run"


def test_runtime_missing_auth_advertises_basic_and_bearer() -> None:
    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_jwt_data(data=None, basic_credentials=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing authorization credentials"
    assert exc_info.value.headers == {
        "WWW-Authenticate": 'Basic realm="ms-image-runtime", Bearer',
    }


def test_admin_auth_remains_bearer_only() -> None:
    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_admin_jwt_data(data=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_basic_auth_settings_require_a_complete_credential_pair() -> None:
    with pytest.raises(ValidationError, match="必须成组配置"):
        Settings(
            _env_file=None,
            BASIC_AUTH_USERNAME="demo-user",
            BASIC_AUTH_PASSWORD="",
        )
