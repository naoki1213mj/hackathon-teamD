"""リクエストから会話所有者識別子を導出する。"""

import base64
import hashlib
import hmac
import json
from typing import Literal, TypedDict

from fastapi import Request

from src.config import AppSettings, get_settings, is_production_environment

IdentityErrorCode = Literal["missing_token", "invalid_token", "identity_mismatch", "untrusted_token"]
_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled"}


class RequestIdentity(TypedDict):
    """リクエスト単位の呼び出し元情報。"""

    user_id: str
    auth_mode: Literal["delegated", "anonymous"]
    oid: str
    tid: str
    upn: str
    auth_error: IdentityErrorCode | None


class RequestIdentityError(Exception):
    """owner 境界で認証済み identity が必要なときのエラー。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _sanitize_text(value: object) -> str:
    """ヘッダー・claim 由来文字列を軽量に正規化する。"""
    return str(value).strip() if value is not None else ""


def _build_user_id(oid: str, tid: str) -> str:
    """oid/tid 由来の安定した user_id を返す。"""
    digest = hashlib.sha256(f"{tid}:{oid}".encode("utf-8")).hexdigest()[:32]
    return f"user-{digest}"


def _build_anonymous_user_id(request: Request) -> str:
    """認証なしリクエスト向けの匿名 user_id を返す。"""
    forwarded_for = _sanitize_text(request.headers.get("x-forwarded-for"))
    client_host = _sanitize_text(getattr(request.client, "host", ""))
    user_agent = _sanitize_text(request.headers.get("user-agent"))
    accept_language = _sanitize_text(request.headers.get("accept-language"))
    fingerprint = "|".join(value for value in (forwarded_for, client_host, user_agent, accept_language) if value)
    if not fingerprint:
        fingerprint = "anonymous"
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
    return f"anon-{digest}"


def _decode_jwt_payload(token: str) -> dict[str, object]:
    """署名検証済み前提の JWT payload をデコードする。"""
    parts = token.split(".")
    if len(parts) != 3:
        return {}

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}".encode("utf-8")).decode("utf-8")
        data = json.loads(decoded)
    except (ValueError, TypeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_bool_setting(value: str | None) -> bool:
    """環境変数由来の文字列を bool として解釈する。"""
    return (value or "").strip().lower() in _TRUE_VALUES


def _setting(settings: AppSettings, key: str) -> str:
    """TypedDict の追加設定をテスト用部分 dict でも安全に読む。"""
    return str(settings.get(key, ""))


def owner_authentication_required(settings: AppSettings | None = None) -> bool:
    """owner-scoped API で認証済み identity が必要かを返す。"""
    resolved = settings or get_settings()
    return is_production_environment() or _parse_bool_setting(_setting(resolved, "require_authenticated_owner"))


def _has_trusted_auth_boundary(request: Request, settings: AppSettings) -> bool:
    """署名検証済み bearer claims として扱える運用境界かを判定する。"""
    if _parse_bool_setting(_setting(settings, "trust_auth_header_claims")):
        return True

    header_name = _sanitize_text(_setting(settings, "trusted_auth_header_name"))
    if not header_name:
        return False

    actual_value = _sanitize_text(request.headers.get(header_name))
    if not actual_value:
        return False

    expected_value = _sanitize_text(_setting(settings, "trusted_auth_header_value"))
    if expected_value:
        return hmac.compare_digest(actual_value, expected_value)
    return True


def _raise_owner_boundary_error(auth_error: IdentityErrorCode) -> None:
    """owner 境界違反を HTTP レイヤーで扱える例外へ変換する。"""
    if auth_error == "identity_mismatch":
        raise RequestIdentityError(403, "IDENTITY_MISMATCH", "認証されたユーザーの tenant が一致しません")
    if auth_error == "invalid_token":
        raise RequestIdentityError(401, "INVALID_AUTH_TOKEN", "有効な認証トークンが必要です")
    if auth_error == "untrusted_token":
        raise RequestIdentityError(
            401,
            "AUTH_HEADER_UNTRUSTED",
            "Authorization claims are not trusted by the configured authentication boundary",
        )
    raise RequestIdentityError(401, "AUTHENTICATION_REQUIRED", "認証が必要です")


def request_has_bearer_token(request: Request) -> bool:
    """Authorization Bearer の有無を返す。"""
    authorization = _sanitize_text(request.headers.get("authorization"))
    return authorization.lower().startswith("bearer ")


def extract_request_identity(
    request: Request,
    *,
    expected_tenant_id: str = "",
    enforce_owner_boundary: bool = False,
) -> RequestIdentity:
    """Bearer token または匿名フォールバックから呼び出し元を解決する。"""
    settings = get_settings()
    require_owner_identity = enforce_owner_boundary and owner_authentication_required(settings)
    anonymous_identity: RequestIdentity = {
        "user_id": _build_anonymous_user_id(request),
        "auth_mode": "anonymous",
        "oid": "",
        "tid": "",
        "upn": "",
        "auth_error": "missing_token",
    }

    if not request_has_bearer_token(request):
        if require_owner_identity:
            _raise_owner_boundary_error("missing_token")
        return anonymous_identity

    if not _has_trusted_auth_boundary(request, settings):
        untrusted_identity: RequestIdentity = {**anonymous_identity, "auth_error": "untrusted_token"}
        if require_owner_identity:
            _raise_owner_boundary_error("untrusted_token")
        return untrusted_identity

    authorization = _sanitize_text(request.headers.get("authorization"))
    token = authorization.split(" ", 1)[1] if " " in authorization else ""
    claims = _decode_jwt_payload(token)
    oid = _sanitize_text(claims.get("oid"))
    tid = _sanitize_text(claims.get("tid"))
    upn = _sanitize_text(claims.get("preferred_username") or claims.get("upn") or claims.get("email"))

    if expected_tenant_id and tid and tid != expected_tenant_id:
        if require_owner_identity:
            _raise_owner_boundary_error("identity_mismatch")
        return {**anonymous_identity, "auth_error": "identity_mismatch"}

    if not oid or not tid:
        if require_owner_identity:
            _raise_owner_boundary_error("invalid_token")
        return {**anonymous_identity, "auth_error": "invalid_token"}

    return {
        "user_id": _build_user_id(oid, tid),
        "auth_mode": "delegated",
        "oid": oid,
        "tid": tid,
        "upn": upn,
        "auth_error": None,
    }
