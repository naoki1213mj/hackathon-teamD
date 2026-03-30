"""Voice Live トークンエンドポイント。フロントエンドの WebSocket 認証用。"""

import logging
import os

from azure.identity import DefaultAzureCredential
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["voice"])


@router.get("/voice-token")
async def get_voice_token() -> JSONResponse:
    """Voice Live API 接続用の AAD トークンを取得する。

    フロントエンドが WebSocket 接続時に使用する Bearer トークンを返す。
    scope は https://cognitiveservices.azure.com/.default
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")

        # Voice Live 接続情報も返す
        resource_name = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").split("//")[1].split(".")[0] if os.environ.get("AZURE_AI_PROJECT_ENDPOINT") else ""
        project_name = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/").split("/")[-1] if os.environ.get("AZURE_AI_PROJECT_ENDPOINT") else ""

        return JSONResponse(content={
            "token": token.token,
            "expires_on": token.expires_on,
            "resource_name": resource_name,
            "project_name": project_name,
            "endpoint": f"wss://{resource_name}.services.ai.azure.com/voice-live/realtime",
            "api_version": "2025-10-01",
        })
    except Exception as exc:
        logger.warning("Voice token 取得失敗: %s", exc)
        return JSONResponse(status_code=503, content={"error": "Voice token unavailable"})


@router.get("/voice-config")
async def get_voice_config() -> JSONResponse:
    """Voice Live の設定情報を返す。"""
    agent_name = os.environ.get("VOICE_AGENT_NAME", "travel-voice-orchestrator")

    return JSONResponse(content={
        "agent_name": agent_name,
        "voice": "ja-JP-NanamiNeural",
        "vad_type": "azure_semantic_vad",
    })
