# Travel Marketing AI Multi-Agent Pipeline

[日本語版 README はこちら](README.ja.md)

> Team D Hackathon — Auto-generate marketing plans, brochures, banner images, and promotional videos from natural language instructions

## Overview

A multi-agent pipeline where travel company marketing staff give natural language instructions and 4 AI agents sequentially produce **marketing plans (Markdown), promotional brochures (HTML), banner images (PNG), and promotional videos (MP4)**.

## Current Status

- **Core pipeline**: FastAPI SSE + 4 agents (Agent Framework rc5) + Sequential Workflow — E2E verified on Azure (Content Safety enabled)
- **Infrastructure**: 15 Bicep modules (Foundry, APIM, Functions, Logic Apps, Cosmos DB, VNet, Key Vault)
- **Frontend**: 18 React components, i18n (ja/en/zh), dark/light mode, responsive layout
- **CI/CD**: 3 GitHub Actions workflows (CI ✅ / Security ✅ / Deploy ✅)
- **v3.7 features**: Cosmos DB conversation history, demo replay API, VNet integration
- **Requirements**: [docs/requirements_v3.7.md](docs/requirements_v3.7.md)

## アーキテクチャ

```
ユーザー → React (Vite/Tailwind/i18n) → FastAPI (SSE)
  → APIM AI Gateway → Content Safety (Prompt Shield)
  → Foundry Agent Service Workflows (Sequential + HiTL)
    → Agent1 (データ検索: Fabric Lakehouse)
    → Agent2 (施策生成: Web Search)
    → [承認ステップ]
    → Agent3 (規制チェック: Foundry IQ + Web Search)
    → Agent4 (販促物生成: GPT Image 1.5 + MCP)
  → Content Safety (Text Analysis) → 成果物表示
```

## 技術スタック

| 層 | 技術 |
|---|------|
| フロントエンド | React 19 + TypeScript + Vite 8 + Tailwind CSS 4 |
| バックエンド | FastAPI + uvicorn (Python 3.14) |
| 推論モデル | gpt-5.4-mini (GA) |
| 画像生成 | GPT Image 1.5 (GA) |
| エージェント | Microsoft Agent Framework 1.0.0rc5 |
| オーケストレーション | Foundry Agent Service Workflows (Preview) |
| データ | Fabric Lakehouse (Delta Parquet + SQL EP) |
| ナレッジ | Foundry IQ Knowledge Base (Preview) |
| デプロイ | Azure Container Apps + Docker + azd |
| CI/CD | GitHub Actions (DevSecOps) |

## Quick Start

### 前提条件

- Python 3.14+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) (Python パッケージ管理)

### セットアップ

```bash
# Python 依存インストール
uv sync

# フロントエンド依存インストール
cd frontend && npm ci && cd ..

# 環境変数設定
cp .env.example .env
# .env を編集して Azure リソースの情報を設定
```

### ローカル開発

```bash
# バックエンド起動
uv run uvicorn src.main:app --reload --port 8000

# フロントエンド起動（別ターミナル）
cd frontend && npm run dev
# → http://localhost:5173 でアクセス（/api は :8000 に proxy）
```

### テスト

```bash
uv run python -m pytest tests/ -v   # バックエンドテスト
uv run ruff check src/               # Python リント
cd frontend && npx tsc --noEmit      # TypeScript 型チェック
```

### デモデータ生成

```bash
uv run python data/demo_data_generator.py
# → data/sales_history.csv (800件), customer_reviews.csv (400件), plan_master.csv (20件)
```

### Azure デプロイ

```bash
azd auth login
azd up       # 初回: プロビジョニング + デプロイ
azd deploy   # 2回目以降: コードのみ
```

Deployments are gated by CI and readiness checks. Production deploys now fail when required production settings are missing.

## プロジェクト構成

```
├── src/                    # バックエンド (Python)
│   ├── main.py             # FastAPI エントリポイント
│   ├── config.py           # 環境変数設定
│   ├── api/
│   │   ├── health.py       # GET /api/health
│   │   └── chat.py         # POST /api/chat (SSE)
│   ├── agents/             # 4 エージェント定義
│   ├── workflows/          # Sequential Workflow
│   └── middleware/         # Content Safety
├── frontend/               # フロントエンド (React)
│   └── src/
│       ├── components/     # 16 コンポーネント
│       ├── hooks/          # useSSE, useTheme, useI18n
│       └── lib/            # SSE client, i18n
├── data/                   # デモデータ
├── regulations/            # レギュレーション文書
├── infra/                  # Bicep IaC
├── tests/                  # pytest テスト
├── Dockerfile              # マルチステージビルド
├── azure.yaml              # azd 設定
└── .github/workflows/      # CI/CD (ci, deploy, security)
```

## チーム

| 担当 | 範囲 |
|------|------|
| Tokunaga | Fabric Lakehouse / デモデータ / Agent1 |
| Matsumoto | Frontend / Backend / Agent2 / Agent4 |
| mmatsuzaki | Infra / APIM / MCP / Agent3 / Content Safety |

## Azure 接続ステータス

| サービス | 接続方法 | フォールバック |
|---------|---------|-------------|
| Foundry (推論) | `AZURE_AI_PROJECT_ENDPOINT` | モックデモモード |
| Content Safety | `CONTENT_SAFETY_ENDPOINT` | 開発: スキップ / 本番: fail-close |
| Fabric Lakehouse | `FABRIC_SQL_ENDPOINT` (pyodbc) | CSV ファイル → ハードコードデータ |
| Cosmos DB | `COSMOS_DB_ENDPOINT` | インメモリストア |
| GPT Image 1.5 | Foundry 経由 (Images API) | 1x1 透明 PNG プレースホルダー |
| Web Search | Foundry Bing Grounding | ハードコードトレンドデータ |
| Foundry IQ | Azure AI Search | 静的レスポンス |
| Application Insights | `APPLICATIONINSIGHTS_CONNECTION_STRING` | テレメトリ無効 |

> **注**: 全環境変数が未設定でもモックデモモードで動作します。

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `AZURE_AI_PROJECT_ENDPOINT` | 本番 | Foundry プロジェクトエンドポイント |
| `CONTENT_SAFETY_ENDPOINT` | 本番 | Content Safety エンドポイント |
| `MODEL_NAME` | — | 推論モデル名（デフォルト: `gpt-5-4-mini`） |
| `ENVIRONMENT` | — | 環境名（デフォルト: `development`） |
| `COSMOS_DB_ENDPOINT` | — | Cosmos DB エンドポイント |
| `FABRIC_SQL_ENDPOINT` | — | Fabric Lakehouse SQL EP |
| `ALLOWED_ORIGINS` | — | CORS 許可オリジン |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | — | Application Insights 接続文字列 |

詳細は [.env.example](.env.example) を参照。

## ドキュメント

- [API リファレンス](docs/api-reference.md) — エンドポイント仕様・SSE イベント定義
- [デプロイガイド](docs/deployment-guide.md) — ローカル開発・Docker・Azure デプロイ手順
- [Azure セットアップガイド](docs/azure-setup.md) — Azure リソース構築手順
- [要件定義書](docs/requirements_v3.7.md) — v3.7 要件定義
