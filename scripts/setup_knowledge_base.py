"""Foundry IQ Knowledge Base セットアップスクリプト。

Azure AI Search に Knowledge Source + Knowledge Base を作成し（Agentic Retrieval）、
regulations/ ディレクトリの Markdown ファイルをインデックスにアップロードする。

手順:
    1. Search Index にドキュメントをアップロード
    2. Knowledge Source を作成（既存 Index を参照）
    3. Knowledge Base を作成（Knowledge Source + LLM を設定）

使い方:
    uv run python scripts/setup_knowledge_base.py

必要な環境変数:
    SEARCH_ENDPOINT: Azure AI Search エンドポイント
    SEARCH_API_KEY: Azure AI Search 管理キー
    AZURE_OPENAI_ENDPOINT: AI Services エンドポイント（KB の LLM 用）
"""

import json
import os
import sys
import urllib.request

# Foundry IQ 設定
INDEX_NAME = "regulations-index"
KNOWLEDGE_SOURCE_NAME = "regulations-ks"
KNOWLEDGE_BASE_NAME = "regulations-kb"
API_VERSION = "2025-11-01-preview"

REGULATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "regulations")


def _request(url: str, api_key: str, method: str = "GET", body: dict | None = None) -> dict:
    """Azure AI Search REST API 呼び出しヘルパー。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "api-key": api_key},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8")) if resp.status != 204 else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {error_body[:500]}")
        raise


def create_index(search_endpoint: str, api_key: str) -> None:
    """Search Index を作成/更新する。"""
    print(f"\n📋 Step 1: Search Index '{INDEX_NAME}' を作成...")
    index_def = {
        "name": INDEX_NAME,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "title", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "source_file", "type": "Edm.String", "filterable": True},
        ],
        "semantic": {
            "configurations": [{
                "name": "regulations-semantic",
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [{"fieldName": "content"}],
                },
            }],
            "defaultConfiguration": "regulations-semantic",
        },
    }

    url = f"{search_endpoint}/indexes/{INDEX_NAME}?api-version={API_VERSION}"
    _request(url, api_key, "PUT", index_def)
    print(f"  ✅ Index '{INDEX_NAME}' 作成/更新完了")


def upload_documents(search_endpoint: str, api_key: str) -> int:
    """regulations/ からドキュメントをアップロードする。"""
    print("\n📄 Step 2: ドキュメントをアップロード...")
    abs_dir = os.path.abspath(REGULATIONS_DIR)
    if not os.path.exists(abs_dir):
        print(f"  ❌ regulations/ が見つかりません: {abs_dir}")
        sys.exit(1)

    docs = []
    category_map = {
        "travel_industry_law.md": "旅行業法",
        "advertising_guidelines.md": "景品表示法・広告規制",
        "brand_guidelines.md": "ブランドガイドライン",
    }

    for filename in sorted(os.listdir(abs_dir)):
        if not filename.endswith(".md"):
            continue
        with open(os.path.join(abs_dir, filename), encoding="utf-8") as f:
            content = f.read()
        category = category_map.get(filename, "その他")
        for i, section in enumerate(content.split("\n## ")):
            title = section.split("\n")[0].strip("# ").strip() if section.strip() else filename
            docs.append({
                "@search.action": "mergeOrUpload",
                "id": f"{filename.replace('.md', '')}-{i}",
                "title": title,
                "content": section.strip()[:8000],
                "category": category,
                "source_file": filename,
            })

    url = f"{search_endpoint}/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"
    result = _request(url, api_key, "POST", {"value": docs})
    success = sum(1 for v in result.get("value", []) if v.get("status"))
    print(f"  ✅ {success}/{len(docs)} ドキュメントをアップロード")
    return len(docs)


def create_knowledge_source(search_endpoint: str, api_key: str) -> None:
    """Knowledge Source を作成する（既存 Index を参照）。"""
    print(f"\n🔗 Step 3: Knowledge Source '{KNOWLEDGE_SOURCE_NAME}' を作成...")
    ks_def = {
        "name": KNOWLEDGE_SOURCE_NAME,
        "kind": "searchIndex",
        "description": "旅行業法・景品表示法・ブランドガイドラインの規制文書",
        "searchIndexParameters": {
            "searchIndexName": INDEX_NAME,
            "semanticConfigurationName": "regulations-semantic",
            "sourceDataFields": [
                {"name": "id"},
                {"name": "title"},
                {"name": "content"},
                {"name": "category"},
            ],
        },
    }

    url = f"{search_endpoint}/knowledgesources/{KNOWLEDGE_SOURCE_NAME}?api-version={API_VERSION}"
    _request(url, api_key, "PUT", ks_def)
    print(f"  ✅ Knowledge Source '{KNOWLEDGE_SOURCE_NAME}' 作成完了")


def create_knowledge_base(search_endpoint: str, api_key: str, openai_endpoint: str) -> None:
    """Knowledge Base を作成する（Knowledge Source + LLM）。"""
    print(f"\n🧠 Step 4: Knowledge Base '{KNOWLEDGE_BASE_NAME}' を作成...")
    kb_def = {
        "name": KNOWLEDGE_BASE_NAME,
        "description": "旅行マーケティングの規制・法令チェック用ナレッジベース",
        "retrievalInstructions": "旅行業法、景品表示法、広告規制、ブランドガイドラインに関する質問に回答してください。",
        "answerInstructions": "検索結果に基づいて、具体的な法令名とチェック項目を含めて日本語で回答してください。",
        "outputMode": "answerSynthesis",
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE_NAME}],
        "models": [{
            "kind": "azureOpenAI",
            "azureOpenAIParameters": {
                "resourceUri": openai_endpoint,
                "deploymentId": "gpt-4-1-mini",
                "modelName": "gpt-4.1-mini",
            },
        }],
        "retrievalReasoningEffort": {"kind": "low"},
    }

    url = f"{search_endpoint}/knowledgebases/{KNOWLEDGE_BASE_NAME}?api-version={API_VERSION}"
    _request(url, api_key, "PUT", kb_def)
    print(f"  ✅ Knowledge Base '{KNOWLEDGE_BASE_NAME}' 作成完了")


def test_retrieval(search_endpoint: str, api_key: str) -> None:
    """Knowledge Base にテストクエリを送る。"""
    print("\n🔍 Step 5: テスト検索...")
    url = f"{search_endpoint}/knowledgebases/{KNOWLEDGE_BASE_NAME}/retrieve?api-version={API_VERSION}"
    request_body = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": "景品表示法の有利誤認とは？"}],
        }],
        "retrievalReasoningEffort": {"kind": "low"},
        "includeActivity": True,
    }

    result = _request(url, api_key, "POST", request_body)
    responses = result.get("response", [])
    if responses:
        content = responses[0].get("content", [])
        if content:
            text = content[0].get("text", "")
            print(f"  ✅ KB 応答: {text[:200]}...")
        else:
            print("  ⚠️ 応答は空です")
    else:
        print("  ⚠️ response がありません")


def main():
    search_endpoint = os.environ.get("SEARCH_ENDPOINT", "")
    api_key = os.environ.get("SEARCH_API_KEY", "")
    openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")

    if not search_endpoint or not api_key:
        print("❌ SEARCH_ENDPOINT と SEARCH_API_KEY 環境変数を設定してください")
        sys.exit(1)
    if not openai_endpoint:
        # project endpoint から AI Services endpoint を導出
        project_ep = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
        if project_ep and "/api/projects/" in project_ep:
            openai_endpoint = project_ep.split("/api/projects/")[0]
        else:
            print("❌ AZURE_OPENAI_ENDPOINT または AZURE_AI_PROJECT_ENDPOINT を設定してください")
            sys.exit(1)

    search_endpoint = search_endpoint.rstrip("/")
    print(f"🔍 Search: {search_endpoint}")
    print(f"🤖 OpenAI: {openai_endpoint}")

    # Step 1: Index 作成
    create_index(search_endpoint, api_key)

    # Step 2: ドキュメントアップロード
    upload_documents(search_endpoint, api_key)

    # Step 3: Knowledge Source 作成
    create_knowledge_source(search_endpoint, api_key)

    # Step 4: Knowledge Base 作成
    create_knowledge_base(search_endpoint, api_key, openai_endpoint)

    # Step 5: テスト検索
    test_retrieval(search_endpoint, api_key)

    print("\n✅ Foundry IQ セットアップ完了！")
    print(f"   Knowledge Base: {KNOWLEDGE_BASE_NAME}")
    print(f"   Knowledge Source: {KNOWLEDGE_SOURCE_NAME}")
    print(f"   Index: {INDEX_NAME}")
    print("\n   Foundry ポータルの IQ 画面に表示されます。")


if __name__ == "__main__":
    main()
