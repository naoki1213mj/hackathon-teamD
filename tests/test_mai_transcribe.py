"""MAI Transcribe adapter の安全性テスト。"""

import httpx
import pytest

from src import config as config_module
from src.mai_transcribe import (
    MaiTranscribeAdapterError,
    MaiTranscribeRequest,
    MaiTranscribeRequestError,
    get_mai_transcribe_availability,
    transcribe_audio,
    validate_transcribe_request,
)


def _disable_azd_env(monkeypatch) -> None:
    """テスト中は実マシンの azd env を参照しない。"""
    monkeypatch.setattr(config_module, "_get_azd_env_values", lambda: {})


def _configure_transcribe(monkeypatch) -> None:
    _disable_azd_env(monkeypatch)
    monkeypatch.setenv("ENABLE_MAI_TRANSCRIBE_1", "true")
    monkeypatch.setenv("MAI_TRANSCRIBE_1_ENDPOINT", "https://transcribe.example")
    monkeypatch.setenv("MAI_TRANSCRIBE_1_DEPLOYMENT_NAME", "mai-transcribe-1")
    monkeypatch.setenv("MAI_TRANSCRIBE_1_API_PATH", "/mai/v1/audio/transcriptions")


def test_mai_transcribe_is_unavailable_by_default(monkeypatch):
    """明示 opt-in と接続情報がない限り available にしない。"""
    _disable_azd_env(monkeypatch)
    for key in [
        "ENABLE_MAI_TRANSCRIBE_1",
        "MAI_TRANSCRIBE_1_ENDPOINT",
        "MAI_TRANSCRIBE_1_DEPLOYMENT_NAME",
        "MAI_TRANSCRIBE_1_API_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)

    availability = get_mai_transcribe_availability()

    assert availability == {"available": False, "configured": False, "reason": "feature_disabled"}


def test_validate_transcribe_request_rejects_non_https_audio_url():
    """短命 URI でも HTTPS 以外や userinfo 付き URL は拒否する。"""
    with pytest.raises(MaiTranscribeRequestError):
        validate_transcribe_request(MaiTranscribeRequest(audio_url="http://storage.example/audio.wav"))
    with pytest.raises(MaiTranscribeRequestError):
        validate_transcribe_request(MaiTranscribeRequest(audio_url="https://user:pass@storage.example/audio.wav"))


@pytest.mark.asyncio
async def test_transcribe_audio_posts_to_configured_api(monkeypatch):
    """設定済み adapter は bearer token で JSON contract を呼び、結果を正規化する。"""
    _configure_transcribe(monkeypatch)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"text": "沖縄の自然体験を訴求する。", "language": "ja-JP", "confidence": 0.92})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await transcribe_audio(
            MaiTranscribeRequest(
                audio_url="https://storage.example/audio.wav?sig=secret",
                filename="memo.wav",
                content_type="audio/wav",
                duration_seconds=10,
                language="ja-JP",
            ),
            http_client=client,
            bearer_token="token",
        )

    assert captured["url"] == "https://transcribe.example/mai/v1/audio/transcriptions"
    assert captured["authorization"] == "Bearer token"
    assert '"model":"mai-transcribe-1"' in str(captured["payload"]).replace(" ", "")
    assert result.transcript == "沖縄の自然体験を訴求する。"
    assert result.language == "ja-JP"
    assert result.confidence == 0.92


@pytest.mark.asyncio
async def test_transcribe_audio_redacts_http_error_details(monkeypatch):
    """HTTP エラー時も音声 URI や transcript を例外メッセージへ含めない。"""
    _configure_transcribe(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, text="failed for https://storage.example/audio.wav?sig=secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MaiTranscribeAdapterError) as exc_info:
            await transcribe_audio(
                MaiTranscribeRequest(audio_url="https://storage.example/audio.wav?sig=secret"),
                http_client=client,
                bearer_token="token",
            )

    assert "sig=secret" not in str(exc_info.value)
    assert "https://storage.example" not in str(exc_info.value)
