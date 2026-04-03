"""アプリケーション設定。TypedDict + load_settings パターンで環境変数をロードする。"""

import os
from typing import TypedDict

from dotenv import load_dotenv

# ローカル開発用に .env を読み込む
load_dotenv(override=False)


class AppSettings(TypedDict):
    """アプリケーションの環境変数設定"""

    project_endpoint: str
    model_name: str
    applicationinsights_connection_string: str
    environment: str
    cosmos_db_endpoint: str
    fabric_sql_endpoint: str
    allowed_origins: str
    content_understanding_endpoint: str
    speech_service_endpoint: str
    speech_service_region: str
    logic_app_callback_url: str
    fabric_data_agent_url: str


# 環境変数の優先順位。GA で一般化した FOUNDRY_* も受け付ける。
_ENV_CANDIDATES: dict[str, tuple[str, ...]] = {
    "project_endpoint": ("AZURE_AI_PROJECT_ENDPOINT", "FOUNDRY_PROJECT_ENDPOINT"),
    "model_name": ("MODEL_NAME", "FOUNDRY_MODEL"),
    "applicationinsights_connection_string": ("APPLICATIONINSIGHTS_CONNECTION_STRING",),
    "environment": ("ENVIRONMENT",),
    "cosmos_db_endpoint": ("COSMOS_DB_ENDPOINT",),
    "fabric_sql_endpoint": ("FABRIC_SQL_ENDPOINT",),
    "allowed_origins": ("ALLOWED_ORIGINS",),
    "content_understanding_endpoint": ("CONTENT_UNDERSTANDING_ENDPOINT",),
    "speech_service_endpoint": ("SPEECH_SERVICE_ENDPOINT",),
    "speech_service_region": ("SPEECH_SERVICE_REGION",),
    "logic_app_callback_url": ("LOGIC_APP_CALLBACK_URL",),
    "fabric_data_agent_url": ("FABRIC_DATA_AGENT_URL",),
}

# デフォルト値（オプショナルな設定のみ）
_DEFAULTS: dict[str, str] = {
    "model_name": "gpt-5-4-mini",
    "environment": "development",
    "allowed_origins": "http://localhost:5173",
}

_PRODUCTION_ENVIRONMENTS = {"production", "prod", "staging"}


def get_settings() -> AppSettings:
    """環境変数から AppSettings をロードする。未設定の必須項目は空文字列になる。"""
    settings: dict[str, str] = {}
    for setting_key, env_keys in _ENV_CANDIDATES.items():
        value = next((os.environ[name] for name in env_keys if os.environ.get(name)), _DEFAULTS.get(setting_key, ""))
        settings[setting_key] = value
    return AppSettings(**settings)  # type: ignore[typeddict-item]


def is_production_environment() -> bool:
    """本番相当環境かどうかを返す。"""
    environment = os.environ.get("ENVIRONMENT", _DEFAULTS["environment"]).lower()
    return environment in _PRODUCTION_ENVIRONMENTS


def get_missing_required_settings() -> list[str]:
    """現在の環境で不足している必須設定の環境変数名を返す。"""
    required: list[str] = []
    if is_production_environment():
        required.append("AZURE_AI_PROJECT_ENDPOINT")
    return [name for name in required if not os.environ.get(name)]
