"""docs-tests-rollout のドキュメント整合性テスト。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_api_reference_documents_rollout_capabilities_and_sources():
    """API リファレンスが default-off gate と source ingestion API を説明している。"""
    content = _read_doc("docs/api-reference.md")

    for expected in [
        "GET /api/capabilities",
        "`source_ingestion`",
        "`mai_transcribe_1`",
        "POST /api/sources/text",
        "POST /api/sources/pdf",
        "POST /api/sources/audio",
        "GET /api/sources/limits",
        "ENABLE_SOURCE_INGESTION=true",
        "SOURCE_INGESTION_DISABLED",
        "AUDIO_TRANSCRIBE_UNAVAILABLE",
        "MAI_TRANSCRIBE_1_API_PATH",
        "raw audio URI を含めません",
        "estimated_cost_usd",
    ]:
        assert expected in content


def test_deployment_docs_keep_privacy_gates_default_off():
    """デプロイ文書が privacy / rollout gate を production-ready と誤記しない。"""
    content = _read_doc("docs/deployment-guide.md")

    for expected in [
        "`ENABLE_EVALUATION_LOGGING=true` なしでは Foundry へ送信せず",
        "`ENABLE_CONTINUOUS_MONITORING=true` だけでは有効になりません",
        "`ENABLE_COST_METRICS=true` で表示される cost は token usage からの推定",
        "`ENABLE_SOURCE_INGESTION=true`",
        "MAI Transcribe は `ENABLE_MAI_TRANSCRIBE_1=true`",
        "Work IQ の `foundry_tool` 経路は既定ですが",
        "owner-scoped API",
    ]:
        assert expected in content


def test_azure_setup_and_requirements_document_rollout_boundaries():
    """Azure / 要件文書が identity・monitoring・未完成 feature gate を明記している。"""
    azure_setup = _read_doc("docs/azure-setup.md")
    requirements = _read_doc("docs/requirements_v4.0.md")

    for expected in [
        "Source ingestion / MAI Transcribe / monitoring gates",
        "raw prompt / Work IQ content / transcript / bearer token / brochure HTML",
        "owner-scoped API",
        "請求確定値ではない",
    ]:
        assert expected in azure_setup

    for expected in [
        "/api/capabilities",
        "Source ingestion（ユーザー提供ソース）",
        "ENABLE_SOURCE_INGESTION=true",
        "MAI_TRANSCRIBE_1_API_PATH",
        "production-ready と表示しない",
        "approval diff",
    ]:
        assert expected in requirements
