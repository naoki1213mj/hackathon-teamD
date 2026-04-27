"""request identity の信頼境界テスト。"""

import base64
import json

import pytest
from starlette.requests import Request

from src import config as config_module
from src.request_identity import RequestIdentityError, extract_request_identity


def _make_bearer_token(payload: dict[str, object]) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8")).decode("utf-8").rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{header}.{body}."


def _make_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
        }
    )


def _reset_identity_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, "_get_azd_env_values", lambda: {})
    for key in (
        "ENVIRONMENT",
        "TRUST_AUTH_HEADER_CLAIMS",
        "TRUSTED_AUTH_HEADER_NAME",
        "TRUSTED_AUTH_HEADER_VALUE",
        "REQUIRE_AUTHENTICATED_OWNER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_untrusted_bearer_claims_are_anonymous_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """開発環境では未検証 bearer claims を owner として信頼しない。"""
    _reset_identity_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    token = _make_bearer_token({"oid": "oid-123", "tid": "tid-123"})

    identity = extract_request_identity(_make_request({"Authorization": f"Bearer {token}"}))

    assert identity["auth_mode"] == "anonymous"
    assert identity["auth_error"] == "untrusted_token"
    assert identity["oid"] == ""


def test_owner_boundary_allows_anonymous_in_production_without_auth_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """本番でも明示フラグなしなら未検証 bearer claims は匿名として扱う。"""
    _reset_identity_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    token = _make_bearer_token({"oid": "oid-123", "tid": "tid-123"})

    identity = extract_request_identity(
        _make_request({"Authorization": f"Bearer {token}"}),
        enforce_owner_boundary=True,
    )

    assert identity["auth_mode"] == "anonymous"
    assert identity["auth_error"] == "untrusted_token"


def test_owner_boundary_rejects_untrusted_bearer_when_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """明示的に owner 認証必須にした場合は未検証 bearer claims を fail-closed で拒否する。"""
    _reset_identity_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_OWNER", "true")
    token = _make_bearer_token({"oid": "oid-123", "tid": "tid-123"})

    with pytest.raises(RequestIdentityError) as exc_info:
        extract_request_identity(
            _make_request({"Authorization": f"Bearer {token}"}),
            enforce_owner_boundary=True,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "AUTH_HEADER_UNTRUSTED"


def test_explicit_trust_flag_accepts_bearer_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    """運用側が明示的に信頼した bearer claims だけ delegated identity にする。"""
    _reset_identity_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TRUST_AUTH_HEADER_CLAIMS", "true")
    token = _make_bearer_token({"oid": "oid-123", "tid": "tid-123", "preferred_username": "user@example.com"})

    identity = extract_request_identity(
        _make_request({"Authorization": f"Bearer {token}"}),
        enforce_owner_boundary=True,
    )

    assert identity["auth_mode"] == "delegated"
    assert identity["oid"] == "oid-123"
    assert identity["tid"] == "tid-123"
    assert identity["upn"] == "user@example.com"


def test_trusted_upstream_header_accepts_bearer_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    """設定済み upstream 検証ヘッダーがある場合だけ bearer claims を使う。"""
    _reset_identity_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TRUSTED_AUTH_HEADER_NAME", "X-Auth-Validated")
    monkeypatch.setenv("TRUSTED_AUTH_HEADER_VALUE", "true")
    token = _make_bearer_token({"oid": "oid-123", "tid": "tid-123"})

    identity = extract_request_identity(
        _make_request({"Authorization": f"Bearer {token}", "X-Auth-Validated": "true"}),
        enforce_owner_boundary=True,
    )

    assert identity["auth_mode"] == "delegated"
    assert identity["auth_error"] is None
