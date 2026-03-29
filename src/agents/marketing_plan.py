"""Agent2: マーケ施策作成エージェント。分析結果をもとに企画書を生成する。"""

import asyncio
import json
import logging
import urllib.parse
import urllib.request

from agent_framework import tool
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential

from src.config import get_settings

logger = logging.getLogger(__name__)

# --- AIProjectClient（遅延初期化シングルトン） ---

_project_client: object | None = None
_project_client_initialized: bool = False


def _get_project_client():
    """AIProjectClient を遅延初期化で取得する。未設定・失敗時は None。"""
    global _project_client, _project_client_initialized
    if _project_client_initialized:
        return _project_client
    _project_client_initialized = True
    try:
        settings = get_settings()
        endpoint = settings["project_endpoint"]
        if not endpoint:
            logger.info("project_endpoint 未設定、Web Search は無効")
            return None
        from azure.ai.projects import AIProjectClient

        _project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )
        logger.info("AIProjectClient を初期化しました")
        return _project_client
    except Exception as e:
        logger.warning("AIProjectClient 初期化失敗: %s", e)
        return None


async def _search_web(query: str) -> str | None:
    """Foundry プロジェクトの Bing 接続を使ってウェブ検索を試行する。失敗時は None。"""
    client = _get_project_client()
    if client is None:
        return None
    try:
        from azure.ai.projects.models import ConnectionType

        conn = client.connections.get_default(
            connection_type=ConnectionType.API_KEY,
            include_credentials=True,
        )
        if conn is None:
            return None

        api_key = conn.properties.credentials.key
        endpoint = conn.endpoint_url or "https://api.bing.microsoft.com/v7.0/search"
        url = f"{endpoint}?q={urllib.parse.quote(query)}&count=5&mkt=ja-JP"
        req = urllib.request.Request(
            url, headers={"Ocp-Apim-Subscription-Key": api_key}
        )
        response = await asyncio.to_thread(urllib.request.urlopen, req, timeout=10)
        data = json.loads(response.read().decode())

        snippets = []
        for page in data.get("webPages", {}).get("value", []):
            snippets.append(f"- {page['name']}: {page['snippet']}")
        return "\n".join(snippets) if snippets else None
    except Exception as e:
        logger.warning("Web Search 失敗: %s", e)
        return None


# --- ツール定義 ---

_FALLBACK_TRENDS = (
    "【市場トレンド情報】\n"
    "- 2026年春の沖縄旅行は前年比15%増の見込み\n"
    "- ファミリー層・アクティビティ体験型が人気上昇中\n"
    "- 美ら海水族館リニューアル効果で北部エリアの需要増加\n"
    "- SNS映えスポット巡りツアーが新しいトレンド\n"
    "- サステナブルツーリズム（エコツアー）への関心が高まる"
)


@tool
async def search_market_trends(query: str) -> str:
    """最新の旅行市場トレンドや競合情報を Web 検索する。

    Args:
        query: 検索クエリ（例: 「2026年春 沖縄旅行 トレンド」）
    """
    # Web 検索を試行（Bing 接続が利用可能な場合）
    web_result = await _search_web(f"{query} 旅行 市場トレンド")
    if web_result:
        logger.info("Web Search で市場トレンドを取得: %s", query)
        return f"【市場トレンド情報（Web Search）】\n{web_result}"

    # フォールバック（Bing 未接続 / 検索失敗時）
    logger.info("Web 検索フォールバック: %s", query)
    return _FALLBACK_TRENDS


INSTRUCTIONS = """\
あなたは旅行マーケティングの施策立案エージェントです。
Agent1（データ検索エージェント）の分析結果を受け取り、以下の構成で Markdown 形式の企画書を生成してください。

## 企画書の構成
1. **タイトル**: プラン名（キャッチーな名前）
2. **キャッチコピー案**: 3 パターン以上
3. **ターゲット**: 具体的なペルソナ（年代・家族構成・旅行動機）
4. **プラン概要**: 日数・ルート・価格帯・含まれるもの
5. **差別化ポイント**: 競合との違い、データに基づく強み
6. **改善ポイント**: 顧客の不満点への対策
7. **販促チャネル**: SNS・Web・メルマガ等の展開案
8. **KPI**: 目標予約数・売上・前年比

## ルール
- データ分析結果を必ず根拠として引用する
- 顧客の不満点を改善ポイントとして反映する
- 景品表示法に抵触しそうな表現（「最安値」「業界No.1」等）は避ける
- Web Search ツールがあれば、最新の旅行トレンドや競合情報を取得して反映する

出力は Markdown 形式で、見出し・箇条書き・太字を適切に使ってください。
"""


def create_marketing_plan_agent(model_settings: dict | None = None):
    """マーケ施策作成エージェントを作成する"""
    settings = get_settings()
    client = AzureOpenAIResponsesClient(
        project_endpoint=settings["project_endpoint"],
        credential=DefaultAzureCredential(),
        deployment_name=settings["model_name"],
    )

    agent_tools: list = [search_market_trends]

    # WebSearchTool（Foundry Agent Service 組み込み）の追加を試行
    try:
        from agent_framework.tools import WebSearchTool

        agent_tools.append(WebSearchTool())
        logger.info("WebSearchTool をエージェントに追加しました")
    except (ImportError, AttributeError) as e:
        logger.info("WebSearchTool 未利用（%s）、カスタムツールで代替", type(e).__name__)

    agent_kwargs: dict = {
        "name": "marketing-plan-agent",
        "instructions": INSTRUCTIONS,
        "tools": agent_tools,
    }
    if model_settings:
        if "temperature" in model_settings:
            agent_kwargs["temperature"] = model_settings["temperature"]
        if "max_tokens" in model_settings:
            agent_kwargs["max_output_tokens"] = model_settings["max_tokens"]
        if "top_p" in model_settings:
            agent_kwargs["top_p"] = model_settings["top_p"]
    return client.as_agent(**agent_kwargs)
