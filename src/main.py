"""FastAPI エントリポイント。ルーター統合・CORS・静的ファイル配信を行う。"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.chat import router as chat_router
from src.api.health import router as health_router

logger = logging.getLogger(__name__)


def _configure_observability() -> None:
    """Application Insights の OpenTelemetry トレーシングを設定する"""
    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn_str:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING 未設定: Observability スキップ")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn_str)
        logger.info("Application Insights Observability 有効化")
    except ImportError:
        logger.warning("azure-monitor-opentelemetry 未インストール: Observability スキップ")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """アプリケーション起動・終了時のライフサイクル管理"""
    _configure_observability()
    yield


app = FastAPI(
    title="Travel Marketing AI Pipeline",
    description="旅行マーケティング AI マルチエージェントパイプライン",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 設定（開発時のみ Vite dev server を許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(health_router)
app.include_router(chat_router)

# 静的ファイル配信（本番: Docker マルチステージビルドで frontend/dist を配信）
if os.environ.get("SERVE_STATIC", "").lower() == "true":
    static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
