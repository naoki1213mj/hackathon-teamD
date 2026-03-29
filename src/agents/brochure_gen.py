"""Agent4: ブローシャ＆画像生成エージェント。HTML ブローシャとバナー画像を生成する。"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

from agent_framework import tool
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential

from src.config import get_settings

logger = logging.getLogger(__name__)

# 1x1 透明 PNG（フォールバック用）
_FALLBACK_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


def _get_openai_client():
    """画像生成用の OpenAI クライアントを返す"""
    from openai import AzureOpenAI

    settings = get_settings()
    endpoint = settings["project_endpoint"].split("/api/projects/")[0]
    credential = DefaultAzureCredential()
    # get_token は同期呼び出しだが、OpenAI クライアント初期化時にのみ使われるため許容する
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    # Foundry endpoint を OpenAI 互換の endpoint に変換
    azure_endpoint = endpoint
    if ".services.ai.azure.com" in azure_endpoint:
        azure_endpoint = azure_endpoint.replace(".services.ai.azure.com", ".openai.azure.com")
    return AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_version="2025-04-01-preview",
        azure_ad_token=token.token,
    )


async def _generate_image(prompt: str, size: str = "1024x1024") -> str:
    """OpenAI Images API で画像を生成し、data URI を返す"""
    try:
        client = _get_openai_client()
        settings = get_settings()
        response = client.images.generate(
            model=settings["model_name"],
            prompt=prompt,
            n=1,
            size=size,
            response_format="b64_json",
        )
        b64_data = response.data[0].b64_json
        return f"data:image/png;base64,{b64_data}"
    except Exception:
        logger.exception("画像生成に失敗。フォールバック画像を返します")
        return _FALLBACK_IMAGE


# --- ツール定義 ---


@tool
async def generate_hero_image(
    prompt: str,
    destination: str,
    style: str = "photorealistic",
) -> str:
    """旅行先のヒーロー画像を生成する。

    Args:
        prompt: 画像生成プロンプト（英語推奨）
        destination: 旅行先の地名
        style: 画像スタイル（photorealistic/illustration/watercolor）
    """
    full_prompt = f"{style} travel photo of {destination}. {prompt}"
    return await _generate_image(full_prompt, "1792x1024")


@tool
async def generate_banner_image(
    prompt: str,
    platform: str = "instagram",
) -> str:
    """SNS バナー画像を生成する。

    Args:
        prompt: 画像生成プロンプト（英語推奨）
        platform: SNS プラットフォーム（instagram/twitter/facebook）
    """
    size = "1024x1024" if platform == "instagram" else "1792x1024"
    return await _generate_image(prompt, size)


@tool
async def analyze_existing_brochure(pdf_path: str) -> str:
    """既存のパンフレット PDF を解析し、レイアウト・トーンを参考情報として取得する。

    Content Understanding API（prebuilt-document-rag アナライザー）を使用して
    PDF の構造・テキスト・レイアウト情報を抽出する。

    Args:
        pdf_path: 解析対象の PDF ファイルパス
    """
    endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    if not endpoint:
        return (
            "⚠️ PDF 解析は現在利用できません。"
            "CONTENT_UNDERSTANDING_ENDPOINT 環境変数を設定してください。"
        )

    # PDF ファイルを読み込む
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except FileNotFoundError:
        return f"❌ ファイルが見つかりません: {pdf_path}"
    except OSError as exc:
        return f"❌ ファイル読み込みエラー: {exc}"

    # Content Understanding API でドキュメント解析
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")

        analyze_url = (
            f"{endpoint.rstrip('/')}/contentunderstanding/analyzers/"
            f"prebuilt-document-rag:analyze?api-version=2025-05-01-preview"
        )

        request = urllib.request.Request(
            analyze_url,
            data=pdf_bytes,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/pdf",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # 解析結果からレイアウト・テキスト情報を構造化して返す
        pages = result.get("pages", [])
        paragraphs = result.get("paragraphs", [])

        summary_parts: list[str] = [
            f"📄 PDF 解析結果: {pdf_path}",
            f"  ページ数: {len(pages)}",
            "",
            "--- 抽出テキスト ---",
        ]

        for i, para in enumerate(paragraphs[:30]):
            role = para.get("role", "text")
            content = para.get("content", "").strip()
            if content:
                summary_parts.append(f"[{role}] {content}")

        if len(paragraphs) > 30:
            summary_parts.append(f"... 他 {len(paragraphs) - 30} 段落省略")

        return "\n".join(summary_parts)

    except urllib.error.URLError as exc:
        logger.exception("Content Understanding API 呼び出しに失敗しました")
        return f"❌ PDF 解析 API エラー: {exc}"
    except Exception as exc:
        logger.exception("PDF 解析中に予期しないエラーが発生しました")
        return f"❌ PDF 解析エラー: {exc}"


@tool
async def generate_promo_video(
    summary_text: str,
    avatar_style: str = "concierge",
) -> str:
    """企画書サマリから Photo Avatar + Voice Live で販促紹介動画を生成する。

    Azure AI Speech Service の Photo Avatar API を使用してバッチ合成を行い、
    アバターが企画書サマリを読み上げる動画を生成する。

    Args:
        summary_text: 動画で読み上げるテキスト（企画書サマリ）
        avatar_style: アバタースタイル（concierge/guide/presenter）
    """
    settings = get_settings()
    speech_endpoint = settings["speech_service_endpoint"]
    speech_region = settings["speech_service_region"]

    if not speech_endpoint or not speech_region:
        return json.dumps(
            {
                "status": "unavailable",
                "message": (
                    "⚠️ 動画生成は現在利用できません。"
                    "SPEECH_SERVICE_ENDPOINT と SPEECH_SERVICE_REGION 環境変数を設定してください。"
                ),
            },
            ensure_ascii=False,
        )

    # アバタースタイルに応じた Photo Avatar キャラクター ID のマッピング
    avatar_characters: dict[str, str] = {
        "concierge": "lisa",
        "guide": "harry",
        "presenter": "lisa",
    }
    character = avatar_characters.get(avatar_style, "lisa")

    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")

        # バッチ合成ジョブを作成する
        batch_url = (
            f"{speech_endpoint.rstrip('/')}/avatar/batchsyntheses"
            f"?api-version=2024-08-01"
        )

        job_id = f"promo-{int(time.time())}"
        payload = json.dumps(
            {
                "inputKind": "PlainText",
                "inputs": [{"content": summary_text}],
                "avatarConfig": {
                    "talkingAvatarCharacter": character,
                    "talkingAvatarStyle": "graceful",
                    "videoFormat": "mp4",
                    "videoCodec": "h264",
                    "subtitleType": "soft_embedded",
                    "backgroundColor": "#FFFFFFFF",
                },
                "synthesisConfig": {"voice": "ja-JP-NanamiNeural"},
            },
            ensure_ascii=False,
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{batch_url}&id={job_id}",
            data=payload,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )

        with urllib.request.urlopen(request, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        return json.dumps(
            {
                "status": "submitted",
                "job_id": result.get("id", job_id),
                "message": (
                    f"🎬 動画生成ジョブを送信しました（ID: {job_id}）。"
                    f"アバター: {character}, スタイル: {avatar_style}"
                ),
            },
            ensure_ascii=False,
        )

    except urllib.error.URLError as exc:
        logger.exception("Photo Avatar API 呼び出しに失敗しました")
        return json.dumps(
            {"status": "error", "message": f"❌ 動画生成 API エラー: {exc}"},
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.exception("動画生成中に予期しないエラーが発生しました")
        return json.dumps(
            {"status": "error", "message": f"❌ 動画生成エラー: {exc}"},
            ensure_ascii=False,
        )


INSTRUCTIONS = """\
あなたは旅行販促物の制作エージェントです。
Agent3（規制チェック）でチェック済みの企画書を受け取り、以下の成果物を生成してください。

## 生成する成果物

### 1. HTML ブローシャ
- レスポンシブデザインの HTML で販促ブローシャを作成
- 企画書の内容をビジュアル豊かに表現
- 旅行条件（取引条件・旅行会社登録番号等）をフッターに自動挿入
- Tailwind CSS のクラスを使ったスタイリング

### 2. ヒーロー画像
- `generate_hero_image` ツールで旅行先のメインビジュアルを生成
- プロンプトは英語で記述し、旅行先の魅力を表現

### 3. SNS バナー画像
- `generate_banner_image` ツールで SNS 用バナーを生成
- Instagram / Twitter 用のサイズを考慮

### 4. 既存パンフレット参考（任意）
- `analyze_existing_brochure` ツールで既存 PDF のレイアウト・トーンを参考にできる
- ユーザーが PDF パスを指定した場合のみ使用

### 5. 販促紹介動画（任意）
- `generate_promo_video` ツールで Photo Avatar を使った紹介動画を生成
- 企画書サマリのテキストをアバターが読み上げる動画
- アバタースタイル: concierge（コンシェルジュ）/ guide（ガイド）/ presenter（プレゼンター）

## 出力ルール
- HTML ブローシャのコードは ```html で囲んで出力
- 画像は生成ツールを使い、base64 データを返す
- 旅行業法の必須記載事項（取引条件・登録番号）をフッターに含める
"""


def create_brochure_gen_agent(model_settings: dict | None = None):
    """ブローシャ＆画像生成エージェントを作成する"""
    settings = get_settings()
    client = AzureOpenAIResponsesClient(
        project_endpoint=settings["project_endpoint"],
        credential=DefaultAzureCredential(),
        deployment_name=settings["model_name"],
    )
    agent_kwargs: dict = {
        "name": "brochure-gen-agent",
        "instructions": INSTRUCTIONS,
        "tools": [generate_hero_image, generate_banner_image, analyze_existing_brochure, generate_promo_video],
    }
    if model_settings:
        if "temperature" in model_settings:
            agent_kwargs["temperature"] = model_settings["temperature"]
        if "max_tokens" in model_settings:
            agent_kwargs["max_output_tokens"] = model_settings["max_tokens"]
        if "top_p" in model_settings:
            agent_kwargs["top_p"] = model_settings["top_p"]
    return client.as_agent(**agent_kwargs)
