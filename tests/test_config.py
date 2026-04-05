"""config モジュールのユニットテスト"""

from src.config import AppSettings, get_missing_required_settings, get_settings, is_production_environment


def test_get_settings_returns_all_fields(monkeypatch):
    """get_settings が AppSettings の全キーを返す"""
    # 環境変数をクリアして確実にデフォルト値を使う
    for key in [
        "AZURE_AI_PROJECT_ENDPOINT",
        "MODEL_NAME",
        "IMPROVEMENT_MCP_ENDPOINT",
        "IMPROVEMENT_MCP_API_KEY",
        "IMPROVEMENT_MCP_API_KEY_HEADER",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "ENVIRONMENT",
        "COSMOS_DB_ENDPOINT",
        "FABRIC_SQL_ENDPOINT",
        "ALLOWED_ORIGINS",
        "CONTENT_UNDERSTANDING_ENDPOINT",
        "SPEECH_SERVICE_ENDPOINT",
        "SPEECH_SERVICE_REGION",
        "LOGIC_APP_CALLBACK_URL",
        "MANAGER_APPROVAL_TRIGGER_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = get_settings()
    expected_keys = set(AppSettings.__annotations__.keys())
    assert set(settings.keys()) == expected_keys


def test_is_production_environment_true(monkeypatch):
    """ENVIRONMENT=production で True を返す"""
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert is_production_environment() is True


def test_is_production_environment_false(monkeypatch):
    """ENVIRONMENT=development で False を返す"""
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert is_production_environment() is False


def test_get_missing_required_settings(monkeypatch):
    """本番環境で project_endpoint 未設定時に不足リストに含まれる"""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)

    missing = get_missing_required_settings()
    assert "AZURE_AI_PROJECT_ENDPOINT" in missing
    assert len(missing) == 1


def test_default_values(monkeypatch):
    """model_name のデフォルト値が gpt-5-4-mini"""
    monkeypatch.delenv("MODEL_NAME", raising=False)
    settings = get_settings()
    assert settings["model_name"] == "gpt-5-4-mini"


def test_improvement_mcp_header_default(monkeypatch):
    """MCP API キーヘッダーは APIM 既定名を使う"""
    monkeypatch.delenv("IMPROVEMENT_MCP_API_KEY_HEADER", raising=False)

    settings = get_settings()

    assert settings["improvement_mcp_api_key_header"] == "Ocp-Apim-Subscription-Key"


def test_foundry_env_aliases(monkeypatch):
    """FOUNDRY_* エイリアス環境変数も解決できる"""
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/demo")
    monkeypatch.setenv("FOUNDRY_MODEL", "gpt-5-4-mini")

    settings = get_settings()

    assert settings["project_endpoint"] == "https://example.services.ai.azure.com/api/projects/demo"
    assert settings["model_name"] == "gpt-5-4-mini"
