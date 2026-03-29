# 旅行マーケティング AI マルチエージェントパイプライン

> Team D ハッカソン — 自然言語指示から企画書・販促物・バナー画像・紹介動画を全自動生成

## 概要

旅行会社のマーケ担当者が自然言語で指示すると、4 つの AI エージェントが順次処理し、**企画書 (Markdown)・販促ブローシャ (HTML)・バナー画像 (PNG)・紹介動画 (MP4)** を全自動で生成するパイプライン。

## 現在の実装状況

- **コアパイプライン**: FastAPI SSE + 4 エージェント (Agent Framework rc5) + Sequential Workflow — Azure 上で E2E 動作確認済み (Content Safety 有効)
- **インフラ**: Bicep 15 モジュール (Foundry, APIM, Functions, Logic Apps, Cosmos DB, VNet, Key Vault)
- **フロントエンド**: React 18 コンポーネント、i18n (日英中)、ダーク/ライトモード、レスポンシブ
- **CI/CD**: GitHub Actions 3 ワークフロー (CI ✅ / Security ✅ / Deploy ✅)
- **v3.7 機能**: Cosmos DB 会話履歴永続化、デモリプレイ API、VNet 統合
- **要件定義書**: [docs/requirements_v3.7.md](docs/requirements_v3.7.md)

## アーキテクチャ

```
ユーザー → React (Vite/Tailwind/i18n) + 🎤 Voice Live → FastAPI (SSE)
  → APIM AI Gateway → Content Safety (Prompt Shield)
  → Foundry Agent Service Workflows (Sequential + HiTL)
    → Agent1 (データ検索: Fabric Lakehouse + Code Interpreter)
    → Agent2 (施策生成: Web Search)
    → [承認ステップ]
    → Agent3 (規制チェック: Foundry IQ + Web Search)
    → Agent4 (販促物生成: GPT Image 1.5 + Content Understanding + Photo Avatar)
  → Content Safety (Text Analysis) → 成果物表示
  → Logic Apps (Teams 通知 + SharePoint 保存)
  → Foundry Evaluations (品質ダッシュボード)
  → Teams 公開
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
| AI Gateway | Azure API Management (BasicV2) |
| MCP サーバー | Azure Functions (Flex Consumption, Python 3.12) |
| 音声入力 | Voice Live API (Preview) |
| 文書解析 | Content Understanding (GA) |
| 販促動画 | Photo Avatar + Voice Live (Preview) |
| ワークフロー自動化 | Azure Logic Apps (Consumption) |
| デプロイ | Azure Container Apps + ACR リモートビルド + azd |
| CI/CD | GitHub Actions (DevSecOps) |

## クイックスタート

### 前提条件

- Python 3.14+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) (Python パッケージ管理)
- Azure サブスクリプション
- Azure Developer CLI (`azd`)

### セットアップ

```bash
# リポジトリクローン
git clone https://github.com/naoki1213mj/hackathon-teamD.git
cd hackathon-teamD

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
uv run pytest                         # バックエンドテスト
uv run pytest --cov=src               # カバレッジ付き
uv run ruff check src/                # Python リント
cd frontend && npx tsc --noEmit       # TypeScript 型チェック
```

### Azure デプロイ

```bash
azd auth login
azd up       # 初回: プロビジョニング + デプロイ
azd deploy   # 2回目以降: コードのみ
```

> **注**: Docker Desktop は不要です。`azd up` は ACR リモートビルド (`az acr build`) を使用します。

> **注**: 本番デプロイは CI 成功と readiness チェックを前提にしています。必須設定が不足している場合は deploy が失敗します。

*** Add File: c:\Users\nmatsumoto\projects\hackathon-teamD\docs\reviews\2026-03-29-comprehensive-review.md
# Comprehensive Review and Improvement Plan

## Scope

- Architecture review
- Security review
- Code review
- CI/CD review
- UI/UX review
- Test review
- Documentation review

## Findings Summary

### Critical

- The current runtime still does not fully enforce the target APIM and Foundry-managed execution path.
- Content Safety previously allowed fail-open behavior when configuration was missing.
- Production deployment could bypass CI through manual dispatch.

### High

- Theme and locale behavior in the frontend were inconsistent, and many visible strings were not localized.
- The voice input UI looked real even though it only sent placeholder text.
- Docker frontend dependency installation was not reproducible.
- Security audits in GitHub Actions did not fail the pipeline.
- Health checks were liveness-only and too weak for deployment gating.

### Medium

- Artifact tab selection could render an empty preview area.
- Exported brochure HTML was not sanitized before download.
- README files described target architecture without clearly separating current implementation state.
- Tests focused on imports and happy paths, but did not assert production-like configuration behavior.

## Implementation Plan

### Phase 1

- Harden backend runtime behavior for production-like environments.
- Add readiness reporting and fix approval parsing correctness.

### Phase 2

- Refresh the frontend shell for responsive layout, stronger hierarchy, and honest feature affordances.
- Sync theme and locale to the document root.

### Phase 3

- Strengthen CI/CD gates.
- Fail dependency audits, remove CI bypass, and validate readiness during deployment.
- Improve Docker build reproducibility.

### Phase 4

- Align README and review docs with the actual implementation state.
- Continue closing the gap between current runtime behavior and the v3.5 target architecture.

## Changes Implemented In This Iteration

- Production-aware fail-close behavior for Prompt Shield and Text Analysis when Content Safety is required.
- `GET /api/ready` endpoint for production configuration validation.
- Language-independent approval keyword handling.
- Fixed syntax-level correctness in the approval follow-up path.
- Responsive, more modern frontend shell with stronger theme behavior and broader translation coverage.
- Honest voice preview UI instead of sending placeholder text as if it were a transcript.
- Artifact tab fallback behavior and safer brochure HTML export.
- CI now runs frontend lint, deploy no longer bypasses CI through manual dispatch, security audits fail the workflow, and deploy includes readiness checks.
- Docker frontend stage now uses `npm ci` with the committed lock file.

## Next Recommended Work

1. Route runtime model traffic through APIM instead of direct project endpoint access.
2. Replace MCP placeholders with real Teams, SharePoint, and PDF flows.
3. Add component-level frontend tests and deploy smoke tests beyond readiness.
4. Wire production secrets and Content Safety endpoint delivery through Key Vault and IaC.
5. Continue reducing the gap between local SequentialBuilder execution and Foundry-managed workflow execution.

## プロジェクト構成

```
├── src/                    # バックエンド (Python 3.14)
│   ├── main.py             # FastAPI エントリポイント
│   ├── config.py           # 環境変数設定
│   ├── api/
│   │   ├── health.py       # GET /api/health
│   │   └── chat.py         # POST /api/chat (SSE)
│   ├── agents/             # 4 エージェント定義
│   │   ├── data_search.py  # Agent1: データ検索
│   │   ├── marketing_plan.py # Agent2: 施策生成
│   │   ├── regulation_check.py # Agent3: 規制チェック
│   │   └── brochure_gen.py # Agent4: 販促物生成
│   ├── workflows/          # Sequential Workflow
│   └── middleware/         # Content Safety
├── frontend/               # フロントエンド (React 19)
│   └── src/
│       ├── components/     # 16+ コンポーネント
│       ├── hooks/          # useSSE, useTheme, useI18n
│       └── lib/            # SSE client, i18n, export
├── functions/              # Azure Functions MCP サーバー (Python 3.12)
├── infra/                  # Bicep IaC
│   ├── main.bicep          # オーケストレーション
│   └── modules/            # 12 モジュール
├── tests/                  # pytest テスト
├── data/                   # デモデータ
├── docs/                   # ドキュメント
├── Dockerfile              # マルチステージビルド
├── azure.yaml              # azd 設定
└── .github/workflows/      # CI/CD (ci, deploy, security)
```

## チーム

| 担当 | ロール | 範囲 |
|------|--------|------|
| Tokunaga | Data SE | Fabric Lakehouse / デモデータ / Agent1 / Content Understanding |
| Matsumoto | App SE | Frontend / Backend / Agent2 / Agent4 / 販促動画 |
| mmatsuzaki | Infra SE | IaC / APIM / MCP / Agent3 / Content Safety / Observability / Voice Live / Logic Apps / Teams 公開 |

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

## ライセンス

このプロジェクトはハッカソン作品です。
