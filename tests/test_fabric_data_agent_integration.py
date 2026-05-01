"""Fabric Data Agent integration smoke (opt-in).

Runs only when both ``FABRIC_DATA_AGENT_URL`` (または ``FABRIC_DATA_AGENT_URL_V2``)
と Azure CLI ログイン (またはサービスプリンシパル via DefaultAzureCredential) が
利用可能な場合にだけ実行される。CI では gated に呼び出され、ローカルでは:

    uv run pytest tests/test_fabric_data_agent_integration.py -v

で手動検証できる。

ゴール:
1. Fabric Data Agent v2 の OpenAI-compatible endpoint が応答すること
2. 1 つ以上のシンプルプロンプトで NL2Ontology grounding が成立し、
   `_STRONG_DATA_AGENT_FAILURE_PATTERNS` のいずれにも該当しないこと
"""

from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

from src.agents.data_search import _STRONG_DATA_AGENT_FAILURE_PATTERNS

_FABRIC_URL_ENV = ("FABRIC_DATA_AGENT_URL_V2", "FABRIC_DATA_AGENT_URL")
_TOKEN_AUDIENCE = "https://analysis.windows.net/powerbi/api/.default"
_API_VERSION = "2024-05-01-preview"
_PROBE_PROMPT = "ハワイの売上を教えてください"
_TIMEOUT_S = 60.0
_POLL_INTERVAL_S = 2.0


def _get_fabric_url() -> str | None:
    for name in _FABRIC_URL_ENV:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _try_get_token() -> str | None:
    """DefaultAzureCredential or AzureCliCredential で Fabric audience のトークンを取る。"""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:  # pragma: no cover - azure-identity は必須依存
        return None

    try:
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        token = cred.get_token(_TOKEN_AUDIENCE)
        return token.token
    except Exception:
        return None


_FABRIC_URL = _get_fabric_url()
_TOKEN = _try_get_token() if _FABRIC_URL else None

skip_unless_configured = pytest.mark.skipif(
    not (_FABRIC_URL and _TOKEN),
    reason="FABRIC_DATA_AGENT_URL[_V2] と Azure 認証 (DefaultAzureCredential) の両方が必要",
)


@skip_unless_configured
def test_fabric_data_agent_responds_without_strong_failure() -> None:
    """シンプルプロンプトで Fabric Data Agent が grounded 応答を返すこと。

    `_STRONG_DATA_AGENT_FAILURE_PATTERNS` に該当する文言が応答に含まれた場合は
    NL2Ontology grounding が壊れた疑いがあるため失敗扱いとする。
    """
    assert _FABRIC_URL is not None  # for type checker
    assert _TOKEN is not None

    activity_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {_TOKEN}",
        "ActivityId": activity_id,
        "x-ms-workload-resource-moniker": activity_id,
        "x-ms-ai-assistant-scenario": "aiskill",
        "x-ms-ai-aiskill-stage": "production",
        "Content-Type": "application/json",
    }
    base = _FABRIC_URL.rstrip("/")

    with httpx.Client(timeout=_TIMEOUT_S) as client:
        # 1) Assistant
        r = client.post(
            f"{base}/assistants?api-version={_API_VERSION}",
            headers=headers,
            json={"model": "not used"},
        )
        assert r.status_code == 200, f"create assistant failed: {r.status_code} {r.text[:300]}"
        assistant_id = r.json()["id"]

        # 2) Thread
        r = client.post(
            f"{base}/threads?api-version={_API_VERSION}",
            headers=headers,
            json={},
        )
        assert r.status_code == 200, f"create thread failed: {r.status_code} {r.text[:300]}"
        thread_id = r.json()["id"]

        # 3) Message
        r = client.post(
            f"{base}/threads/{thread_id}/messages?api-version={_API_VERSION}",
            headers=headers,
            json={"role": "user", "content": _PROBE_PROMPT},
        )
        assert r.status_code == 200

        # 4) Run + poll
        r = client.post(
            f"{base}/threads/{thread_id}/runs?api-version={_API_VERSION}",
            headers=headers,
            json={"assistant_id": assistant_id},
        )
        assert r.status_code == 200
        run_id = r.json()["id"]

        deadline = time.monotonic() + _TIMEOUT_S
        status = ""
        while time.monotonic() < deadline:
            r = client.get(
                f"{base}/threads/{thread_id}/runs/{run_id}?api-version={_API_VERSION}",
                headers=headers,
            )
            assert r.status_code == 200
            status = r.json().get("status", "")
            if status in {"completed", "failed", "expired", "cancelled"}:
                break
            time.sleep(_POLL_INTERVAL_S)

        assert status == "completed", f"run did not complete (status={status})"

        # 5) Read assistant message
        r = client.get(
            f"{base}/threads/{thread_id}/messages?api-version={_API_VERSION}",
            headers=headers,
        )
        assert r.status_code == 200
        messages = r.json().get("data", [])
        # Newest first
        assistant_text = ""
        for m in messages:
            if m.get("role") == "assistant":
                for part in m.get("content", []):
                    if part.get("type") == "text":
                        assistant_text += part.get("text", {}).get("value", "")
                break

        assert assistant_text, "assistant returned empty text"

        for pattern in _STRONG_DATA_AGENT_FAILURE_PATTERNS:
            assert pattern not in assistant_text, (
                f"Fabric Data Agent fell back ('{pattern}' detected)\n"
                f"Response:\n{assistant_text[:1000]}"
            )
