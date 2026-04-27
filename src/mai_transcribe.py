"""MAI-Transcribe-1 の安全なアダプター抽象。"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping, TypedDict
from urllib.parse import urlparse

import httpx
from azure.core.exceptions import AzureError

from src.config import AppSettings, get_settings
from src.http_client import get_http_client
from src.model_deployments import parse_bool_setting
from src.tool_telemetry import redact_sensitive_text

logger = logging.getLogger(__name__)

_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
_MAX_AUDIO_URL_LENGTH = 2048
_MAX_FILENAME_LENGTH = 200
_MAX_CONTENT_TYPE_LENGTH = 100
_MAX_LANGUAGE_LENGTH = 20
_MAX_TRANSCRIPT_LENGTH = 20_000
_TRANSCRIBE_TIMEOUT_SECONDS = 120.0
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class MaiTranscribeAvailability(TypedDict):
    """MAI Transcribe adapter の公開可能な可用性。"""

    available: bool
    configured: bool
    reason: str


@dataclass(frozen=True)
class MaiTranscribeRequest:
    """raw audio を保持せず、短命 HTTPS URI だけを渡す文字起こし要求。"""

    audio_url: str
    filename: str | None = None
    content_type: str | None = None
    duration_seconds: float | None = None
    language: str | None = None


@dataclass(frozen=True)
class MaiTranscribeResult:
    """アプリが保持してよい正規化済み文字起こし結果。"""

    transcript: str
    language: str | None = None
    duration_seconds: float | None = None
    confidence: float | None = None
    metadata: Mapping[str, str | int | float | bool | None] | None = None


class MaiTranscribeUnavailableError(RuntimeError):
    """設定不足または feature flag 無効でアダプターが使えない。"""


class MaiTranscribeAdapterNotImplementedError(MaiTranscribeUnavailableError):
    """REST contract 未確定のため呼び出せない。"""


class MaiTranscribeRequestError(ValueError):
    """文字起こし要求の入力が不正。"""


class MaiTranscribeAdapterError(RuntimeError):
    """MAI Transcribe 呼び出しに失敗。"""


def _clean_text(value: str | None, *, max_length: int) -> str:
    normalized = _CONTROL_CHARS_RE.sub("", str(value or "")).strip()
    return normalized[:max_length]


def _has_value(value: str | None) -> bool:
    return bool((value or "").strip())


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def get_mai_transcribe_availability(settings: AppSettings | None = None) -> MaiTranscribeAvailability:
    """feature flag と endpoint / deployment / API path の設定状態を返す。"""
    resolved = settings or get_settings()
    enabled = parse_bool_setting(resolved["enable_mai_transcribe_1"])
    has_endpoint = _has_value(resolved["mai_transcribe_1_endpoint"])
    has_deployment = _has_value(resolved["mai_transcribe_1_deployment_name"])
    has_api_path = _has_value(resolved["mai_transcribe_1_api_path"])
    configured = enabled or has_endpoint or has_deployment or has_api_path
    if not enabled:
        reason = "feature_disabled"
    elif not has_endpoint:
        reason = "missing_endpoint"
    elif not has_deployment:
        reason = "missing_deployment"
    elif not has_api_path:
        reason = "missing_api_path"
    else:
        reason = "available"
    return {
        "available": reason == "available",
        "configured": configured,
        "reason": reason,
    }


def validate_transcribe_request(request: MaiTranscribeRequest) -> MaiTranscribeRequest:
    """音声 URI と任意メタデータを検証・正規化する。"""
    audio_url = _clean_text(request.audio_url, max_length=_MAX_AUDIO_URL_LENGTH)
    if not audio_url:
        raise MaiTranscribeRequestError("audio_url is required")
    if not _is_https_url(audio_url):
        raise MaiTranscribeRequestError("audio_url must be an HTTPS URL without userinfo")
    duration_seconds = request.duration_seconds
    if duration_seconds is not None and duration_seconds < 0:
        raise MaiTranscribeRequestError("duration_seconds must be non-negative")
    return MaiTranscribeRequest(
        audio_url=audio_url,
        filename=_clean_text(request.filename, max_length=_MAX_FILENAME_LENGTH) or None,
        content_type=_clean_text(request.content_type, max_length=_MAX_CONTENT_TYPE_LENGTH) or None,
        duration_seconds=duration_seconds,
        language=_clean_text(request.language, max_length=_MAX_LANGUAGE_LENGTH) or None,
    )


def _join_endpoint_and_path(endpoint: str, api_path: str) -> str:
    clean_endpoint = endpoint.strip().rstrip("/")
    clean_path = api_path.strip().lstrip("/")
    if not clean_endpoint or not clean_path:
        raise MaiTranscribeAdapterNotImplementedError("MAI Transcribe API endpoint/path is not configured")
    if not _is_https_url(clean_endpoint):
        raise MaiTranscribeAdapterNotImplementedError("MAI Transcribe endpoint must be HTTPS")
    return f"{clean_endpoint}/{clean_path}"


async def _get_access_token() -> str:
    """DefaultAzureCredential で Cognitive Services 用 token を取得する。"""
    try:
        from src.agent_client import get_shared_credential

        token = await asyncio.to_thread(get_shared_credential().get_token, _COGNITIVE_SERVICES_SCOPE)
    except AzureError as exc:
        raise MaiTranscribeAdapterError("MAI Transcribe authentication failed") from exc
    return token.token


def _extract_transcript(payload: Mapping[str, Any]) -> str:
    for key in ("text", "transcript", "displayText"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value, max_length=_MAX_TRANSCRIPT_LENGTH)
    segments = payload.get("segments")
    if isinstance(segments, list):
        texts = [item.get("text", "") for item in segments if isinstance(item, Mapping)]
        combined = " ".join(text.strip() for text in texts if isinstance(text, str) and text.strip())
        if combined:
            return _clean_text(combined, max_length=_MAX_TRANSCRIPT_LENGTH)
    return ""


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _redacted_message(message: str) -> str:
    return redact_sensitive_text(message)[:500]


async def transcribe_audio(
    request: MaiTranscribeRequest,
    *,
    settings: AppSettings | None = None,
    http_client: httpx.AsyncClient | None = None,
    bearer_token: str | None = None,
) -> MaiTranscribeResult:
    """MAI-Transcribe-1 で音声 URI を文字起こしする。

    API path は環境変数で明示設定された場合だけ使用する。未確認の REST path を
    推測して呼ばないため、未設定時は unavailable として扱う。
    """
    resolved = settings or get_settings()
    availability = get_mai_transcribe_availability(resolved)
    if not availability["available"]:
        if availability["reason"] == "missing_api_path":
            raise MaiTranscribeAdapterNotImplementedError("MAI Transcribe API path is not configured")
        raise MaiTranscribeUnavailableError(f"MAI Transcribe unavailable: {availability['reason']}")

    validated = validate_transcribe_request(request)
    api_url = _join_endpoint_and_path(resolved["mai_transcribe_1_endpoint"], resolved["mai_transcribe_1_api_path"])
    token = bearer_token or await _get_access_token()
    client = http_client or get_http_client()
    payload: dict[str, str | float] = {
        "model": resolved["mai_transcribe_1_deployment_name"].strip(),
        "audio_url": validated.audio_url,
    }
    if validated.language:
        payload["language"] = validated.language
    if validated.content_type:
        payload["content_type"] = validated.content_type
    if validated.filename:
        payload["filename"] = validated.filename
    if validated.duration_seconds is not None:
        payload["duration_seconds"] = validated.duration_seconds

    try:
        response = await client.post(
            api_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=_TRANSCRIBE_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise MaiTranscribeAdapterError("MAI Transcribe request timed out") from exc
    except httpx.HTTPError as exc:
        raise MaiTranscribeAdapterError(_redacted_message(f"MAI Transcribe request failed: {exc}")) from exc

    if response.status_code in {404, 405}:
        raise MaiTranscribeAdapterNotImplementedError("MAI Transcribe API path is not accepted by the endpoint")
    if response.status_code >= 400:
        raise MaiTranscribeAdapterError(f"MAI Transcribe API returned HTTP {response.status_code}")

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise MaiTranscribeAdapterError("MAI Transcribe returned invalid JSON") from exc
    if not isinstance(response_payload, Mapping):
        raise MaiTranscribeAdapterError("MAI Transcribe returned an unexpected payload")

    transcript = _extract_transcript(response_payload)
    if not transcript:
        raise MaiTranscribeAdapterError("MAI Transcribe returned no transcript text")

    logger.info("MAI Transcribe succeeded: duration_configured=%s", validated.duration_seconds is not None)
    return MaiTranscribeResult(
        transcript=transcript,
        language=response_payload.get("language") if isinstance(response_payload.get("language"), str) else None,
        duration_seconds=_optional_float(response_payload.get("duration_seconds") or response_payload.get("duration")),
        confidence=_optional_float(response_payload.get("confidence")),
        metadata={"provider": "mai_transcribe_1"},
    )
